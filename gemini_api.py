"""
ESG 報告書評分系統
- 依 SASB + Clarkson et al. (2008)
- 每 20 頁切割 PDF
- 使用 Google 官方 google-genai SDK
- 自動 retry / fallback 模型
"""

import os
import json
import time
import math
import re
import configparser
from typing import Dict, List, Any

import pdfplumber
from google import genai


# =========================
# 主類別
# =========================
class ESGReportScorer:

    # ---------- 基本設定 ----------
    PDF_PATH = "2330_台積電_2024年永續報告書.pdf"
    OUTPUT_DIR = "output_chunks"
    OUTPUT_PREFIX = "2330_台積電_2024年永續報告書_sasb_score"
    CHUNK_PAGES = 20

    # ---------- 模型設定（依你實際可用清單） ----------
    MODEL_PRIMARY = "models/gemini-2.5-flash"
    MODEL_FALLBACKS = [
        "models/gemini-2.0-flash",
        "models/gemini-flash-latest",
        "models/gemini-pro-latest",
    ]

    # ---------- token 保險 ----------
    MAX_CHARS_PER_CHUNK = 50000

    def __init__(self, config_path: str = "config.ini"):
        self.config = self._load_config(config_path)
        self.client = self._init_llm()
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    # =========================
    # 初始化
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

    def _init_llm(self):
        key = self.config["gemini"]["api_key"]
        print("[INIT] 使用 google-genai SDK")
        print("[INIT] Primary model:", self.MODEL_PRIMARY)
        return genai.Client(api_key=key)

    # =========================
    # PDF 處理
    # =========================
    def extract_pdf_text(self) -> Dict[int, str]:
        if not os.path.exists(self.PDF_PATH):
            raise FileNotFoundError(f"找不到 PDF：{self.PDF_PATH}")

        text_by_page = {}
        with pdfplumber.open(self.PDF_PATH) as pdf:
            total = len(pdf.pages)
            print(f"[PDF] 共 {total} 頁")

            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    text_by_page[i] = text.strip()

                if i % 10 == 0 or i == total:
                    print(f"[PDF] 已讀取 {i}/{total} 頁")

        return text_by_page

    def _build_text_chunk(self, pdf_text: Dict[int, str], start: int, end: int) -> str:
        parts = []
        for p in range(start, end + 1):
            if p in pdf_text:
                parts.append(f"[頁碼: {p}]\n{pdf_text[p]}")
        joined = "\n\n".join(parts)
        return joined[: self.MAX_CHARS_PER_CHUNK]

    # =========================
    # Gemini 呼叫（含 retry / fallback）
    # =========================
    def _call_gemini(self, prompt: str) -> str:
        models = [self.MODEL_PRIMARY] + self.MODEL_FALLBACKS
        last_err = None

        for model in models:
            for attempt in range(1, 6):
                try:
                    resp = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    return resp.text or ""

                except Exception as e:
                    msg = str(e)
                    last_err = e

                    # 404：模型不可用
                    if "NOT_FOUND" in msg or "404" in msg:
                        print(f"  [WARN] {model} 不支援，切換模型")
                        break

                    # 429 / quota
                    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                        if "limit: 0" in msg:
                            print(f"  [WARN] {model} 配額=0，切換模型")
                            break

                        m = re.search(r"Please retry in\s+([\d\.]+)s", msg)
                        wait = int(float(m.group(1))) if m else 10
                        print(f"  [429] {model} retry {attempt}/5，等待 {wait}s")
                        time.sleep(wait)
                        continue

                    print(f"  [ERROR] {model}: {msg}")
                    break

        raise Exception(f"Gemini API 呼叫失敗：{last_err}")

    # =========================
    # Prompt
    # =========================
    def _create_prompt(self, text: str) -> str:
        return f"""
請分析以下 ESG 永續報告內容，依 SASB 與 Clarkson et al. (2008) 評分。

評分：
0 未揭露
1 軟性承諾
2 定性措施
3 定量數據
4 第三方確信

請輸出 JSON array，每個物件包含：
- esg_category ("E","S","G")
- sasb_topic
- page_number
- report_claim
- greenwashing_factor
- risk_score (0-4)

內容：
{text}

只輸出 JSON，不要其他文字。
"""

    # =========================
    # JSON 安全解析
    # =========================
    def _safe_json(self, txt: str) -> List[Dict[str, Any]]:
        txt = txt.strip()
        txt = re.sub(r"^```(?:json)?", "", txt, flags=re.I)
        txt = re.sub(r"```$", "", txt)

        a0, a1 = txt.find("["), txt.rfind("]")
        if a0 != -1 and a1 != -1:
            return json.loads(txt[a0 : a1 + 1])
        return json.loads(txt)

    # =========================
    # 主流程：分段分析
    # =========================
    def score_report(self):
        pdf_text = self.extract_pdf_text()
        max_page = max(pdf_text.keys())
        chunks = math.ceil(max_page / self.CHUNK_PAGES)

        all_results = []
        errors = []

        for i in range(chunks):
            start = i * self.CHUNK_PAGES + 1
            end = min((i + 1) * self.CHUNK_PAGES, max_page)
            print(f"\n[批次 {i+1}/{chunks}] 頁碼 {start}-{end}")

            chunk_text = self._build_text_chunk(pdf_text, start, end)
            print(f"[DEBUG] chunk pages {start}-{end}, chars={len(chunk_text)}")
            prompt = self._create_prompt(chunk_text)

            out_name = f"{self.OUTPUT_PREFIX}_p{start:04d}-{end:04d}.json"
            out_path = os.path.join(self.OUTPUT_DIR, out_name)

            try:
                result_text = self._call_gemini(prompt)
                data = self._safe_json(result_text)

                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                print(f"  ✓ 輸出 {out_path}")
                all_results.extend(data)

            except Exception as e:
                print(f"  ✗ 錯誤：{e}")
                err = {"page_range": f"{start}-{end}", "error": str(e)}
                errors.append(err)

                err_path = os.path.join(
                    self.OUTPUT_DIR,
                    f"{self.OUTPUT_PREFIX}_p{start:04d}-{end:04d}_ERROR.json",
                )
                with open(err_path, "w", encoding="utf-8") as f:
                    json.dump(err, f, ensure_ascii=False, indent=2)

        # 合併輸出
        all_path = os.path.join(self.OUTPUT_DIR, f"{self.OUTPUT_PREFIX}_ALL.json")
        with open(all_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        print("\n完成！")
        print(f"成功項目數：{len(all_results)}")
        print(f"合併檔案：{all_path}")

        if errors:
            print(f"⚠️ 有 {len(errors)} 個批次失敗，請查看 *_ERROR.json")


# =========================
# main
# =========================
def main():
    scorer = ESGReportScorer()
    scorer.score_report()


if __name__ == "__main__":
    main()