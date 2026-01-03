"""
ESG 報告書評分系統（SQL Schema 對齊最終版）

SQL Schema：
company_id VARCHAR(4),
year INT,
ESG_category VARCHAR(5),
SASB_topic VARCHAR(20),
page_number VARCHAR(3),
report_claim TEXT(500),
greenwashing_factor TEXT(500),
risk_score VARCHAR(3)

特性：
- 每 20 頁切割 PDF
- 使用 google-genai SDK
- retry <= 3，429 直接切模型
- 斷點續跑
- 合併 ALL.json
- Prompt 固定欄位
- Python 後處理正規化（100% 可 INSERT SQL）
"""

import os
import json
import time
import math
import re
import configparser
from typing import Dict, List, Any, Optional
from collections import deque

import pdfplumber
from google import genai


# =========================
# Rate Limiter
# =========================
class RateLimiter:
    def __init__(self, max_per_minute: int = 10):
        self.max_per_minute = max_per_minute
        self._hits = deque()

    def wait(self):
        now = time.time()
        window_start = now - 60

        while self._hits and self._hits[0] < window_start:
            self._hits.popleft()

        if len(self._hits) >= self.max_per_minute:
            sleep_sec = 60 - (now - self._hits[0]) + 0.1
            print(f"[RATE] 等待 {sleep_sec:.1f}s")
            time.sleep(max(0.2, sleep_sec))

        self._hits.append(time.time())


# =========================
# Main Class
# =========================
class ESGReportScorer:
    # ---------- 基本設定 ----------
    PDF_PATH = "2330_台積電_2024年永續報告書.pdf"
    OUTPUT_DIR = "output_chunks"
    OUTPUT_PREFIX = "2330_台積電_2024年永續報告書_sasb_score"

    CHUNK_PAGES = 20
    MAX_CHARS_PER_CHUNK = 20000

    # ---------- 模型 ----------
    MODEL_DEFAULT = "models/gemini-2.0-flash"
    MODEL_FALLBACKS = [
        "models/gemini-2.0-flash-001",
        "models/gemini-2.0-flash-lite",
        "models/gemini-flash-lite-latest",
        "models/gemini-flash-latest",
        "models/gemini-2.5-flash",
        "models/gemini-3-flash-preview",
    ]

    MAX_ATTEMPTS_PER_MODEL = 3
    MAX_REQ_PER_MINUTE = 10

    def __init__(self, config_path: str = "config.ini"):
        self.config = self._load_config(config_path)
        self.client = genai.Client(api_key=self.config["gemini"]["api_key"])
        self.limiter = RateLimiter(self.MAX_REQ_PER_MINUTE)

        # 固定寫入 SQL 欄位
        self.company_id = "2330"
        self.year = 2024

        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    # =========================
    # Config
    # =========================
    def _load_config(self, path: str) -> configparser.ConfigParser:
        if not os.path.exists(path):
            raise FileNotFoundError(f"找不到 {path}")

        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")

        if "gemini" not in cfg or "api_key" not in cfg["gemini"]:
            raise ValueError("config.ini 缺少 [gemini] api_key")

        cfg["gemini"]["api_key"] = cfg["gemini"]["api_key"].strip().strip('"').strip("'")
        return cfg

    # =========================
    # PDF
    # =========================
    def extract_pdf_text(self) -> Dict[int, str]:
        text_by_page = {}
        with pdfplumber.open(self.PDF_PATH) as pdf:
            total = len(pdf.pages)
            print(f"[PDF] 共 {total} 頁")

            for i, page in enumerate(pdf.pages, start=1):
                txt = page.extract_text()
                if txt:
                    text_by_page[i] = txt.strip()

                if i % 10 == 0 or i == total:
                    print(f"[PDF] 已讀取 {i}/{total}")

        return text_by_page

    def _build_chunk(self, pdf_text: Dict[int, str], start: int, end: int) -> str:
        parts = []
        for p in range(start, end + 1):
            if p in pdf_text:
                parts.append(f"[頁碼: {p}]\n{pdf_text[p]}")
        return "\n\n".join(parts)[: self.MAX_CHARS_PER_CHUNK]

    # =========================
    # Gemini Call
    # =========================
    def _call_gemini_once(self, model: str, prompt: str) -> str:
        self.limiter.wait()
        resp = self.client.models.generate_content(model=model, contents=prompt)
        return resp.text or ""

    def _call_gemini(self, prompt: str) -> str:
        last_err = None
        for model in [self.MODEL_DEFAULT] + self.MODEL_FALLBACKS:
            for _ in range(self.MAX_ATTEMPTS_PER_MODEL):
                try:
                    return self._call_gemini_once(model, prompt)
                except Exception as e:
                    msg = str(e)
                    last_err = e
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "404" in msg:
                        print(f"[WARN] {model} 不可用，切換模型")
                        break
                    print(f"[ERROR] {model}: {msg}")
        raise Exception(f"Gemini API 失敗：{last_err}")

    # =========================
    # Prompt（固定 SQL schema）
    # =========================
    def _create_prompt(self, text: str) -> str:
        return f"""
請依 SASB 與 Clarkson et al. (2008) 分析 ESG 報告內容。

【輸出格式】
請只輸出 JSON array，不要任何其他文字。

每個物件必須完全符合以下 SQL schema：
- company_id: STRING (VARCHAR(4))，固定 "{self.company_id}"
- year: INTEGER (INT)，固定 {self.year}
- ESG_category: STRING ("E","S","G")
- SASB_topic: STRING (VARCHAR(20))
- page_number: STRING (VARCHAR(3))
- report_claim: STRING (TEXT <=500)
- greenwashing_factor: STRING (TEXT <=500)
- risk_score: STRING ("0"~"4")

【內容】
{text}
"""

    # =========================
    # JSON Parse
    # =========================
    def _safe_json(self, txt: str) -> List[Dict[str, Any]]:
        """
        安全解析 LLM 回傳的 JSON：
        - 支援 ```json ``` 包裹
        - 支援 array / 單一 object
        - 若完全無法解析，丟出「可讀錯誤」
        """
        if not txt or not txt.strip():
            raise ValueError("LLM 回傳為空字串，無法解析 JSON")

        txt = txt.strip()
        txt = re.sub(r"^```(?:json)?", "", txt, flags=re.I)
        txt = re.sub(r"```$", "", txt)

        # 嘗試擷取 array
        a0, a1 = txt.find("["), txt.rfind("]")
        if a0 != -1 and a1 != -1 and a1 > a0:
            candidate = txt[a0:a1 + 1]
        else:
            # 嘗試整段直接 parse（可能是單一 object）
            candidate = txt

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as e:
            # 把前 300 字丟出來，方便 debug
            preview = candidate[:300].replace("\n", " ")
            raise ValueError(
                f"JSON 解析失敗：{e}. 回傳內容前 300 字：{preview}"
            )

        # 若模型回傳的是單一 object，包成 array
        if isinstance(parsed, dict):
            return [parsed]

        if not isinstance(parsed, list):
            raise ValueError(f"JSON 解析結果不是 array / object，而是 {type(parsed)}")

        return parsed

    # =========================
    # Normalize → SQL Safe
    # =========================
    def _normalize(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for r in rows:
            out.append({
                "company_id": str(r.get("company_id", self.company_id)).zfill(4)[:4],
                "year": int(r.get("year", self.year)),
                "ESG_category": str(r.get("ESG_category", ""))[:5],
                "SASB_topic": str(r.get("SASB_topic", ""))[:20],
                "page_number": str(r.get("page_number", ""))[:3],
                "report_claim": str(r.get("report_claim", ""))[:500],
                "greenwashing_factor": str(r.get("greenwashing_factor", ""))[:500],
                "risk_score": str(r.get("risk_score", ""))[:3],
            })
        return out

    # =========================
    # Main Flow
    # =========================
    def score_report(self):
        pdf_text = self.extract_pdf_text()
        max_page = max(pdf_text.keys())
        total_chunks = math.ceil(max_page / self.CHUNK_PAGES)

        all_rows = []

        for i in range(total_chunks):
            start = i * self.CHUNK_PAGES + 1
            end = min((i + 1) * self.CHUNK_PAGES, max_page)

            out_path = os.path.join(
                self.OUTPUT_DIR,
                f"{self.OUTPUT_PREFIX}_p{start:04d}-{end:04d}.json"
            )

            if os.path.exists(out_path):
                print(f"[SKIP] {start}-{end}")
                with open(out_path, "r", encoding="utf-8") as f:
                    all_rows.extend(json.load(f))
                continue

            print(f"[RUN] 頁碼 {start}-{end}")
            prompt = self._create_prompt(self._build_chunk(pdf_text, start, end))

            raw = self._call_gemini(prompt)
            data = self._normalize(self._safe_json(raw))

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            all_rows.extend(data)

        all_path = os.path.join(self.OUTPUT_DIR, f"{self.OUTPUT_PREFIX}_ALL.json")
        with open(all_path, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, ensure_ascii=False, indent=2)

        print(f"\n完成！合併檔案：{all_path}")


def main():
    ESGReportScorer().score_report()


if __name__ == "__main__":
    main()
