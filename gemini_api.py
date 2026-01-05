import os
import json
import time
import re
from typing import Dict, List, Any
from collections import deque

import pdfplumber
from google import genai
from dotenv import load_dotenv

# ✅ 讀取 .env（建議放在程式一開始）
load_dotenv()


# =========================
# Rate Limiter (API 限流器)
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
            print(f"[RATE] 觸發限流，等待 {sleep_sec:.1f} 秒...")
            time.sleep(max(0.2, sleep_sec))
        self._hits.append(time.time())


# =========================
# 主處理類別
# =========================
class ESGReportScorer:
    # 設定參數
    INPUT_DIR = "ESG_Reports"       # PDF 所在資料夾
    OUTPUT_DIR = "output_chunks"    # 結果輸出資料夾
    MAX_CHARS_TOTAL = 20000         # 切分大小

    # Gemini 模型設定
    MODEL_DEFAULT = "models/gemini-2.0-flash"
    MODEL_FALLBACKS = [
        "models/gemini-2.0-flash-001",
        "models/gemini-2.0-flash-lite",
        "models/gemini-1.5-flash",
    ]
    MAX_ATTEMPTS = 3

    def __init__(self, target_year: int, target_company_id: str):
        # ✅ 從 .env 取得 GEMINI_API_KEY
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "❌ 找不到 GEMINI_API_KEY。\n"
                "請確認專案根目錄有 .env 檔，內容例如：\n"
                "GEMINI_API_KEY=你的key"
            )

        self.client = genai.Client(api_key=api_key)
        self.limiter = RateLimiter(max_per_minute=10)

        self.target_year = target_year
        self.target_company_id = str(target_company_id).strip()

        # ✅ 根據使用者輸入，自動尋找對應檔案
        self.pdf_path, self.pdf_filename = self._find_target_pdf()

        # 設定輸出檔名 (基於找到的檔案名稱)
        base_name = os.path.splitext(self.pdf_filename)[0]
        self.output_json_name = f"{base_name}_sasb_score_ALL.json"

        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    def _find_target_pdf(self) -> (str, str):
        """
        在 ESG_Reports 中尋找符合 {Year}_{ID}_*.pdf 的檔案
        """
        if not os.path.exists(self.INPUT_DIR):
            raise FileNotFoundError(f"找不到資料夾：{self.INPUT_DIR}")

        # 搜尋前綴：例如 "2024_2330_"
        prefix = f"{self.target_year}_{self.target_company_id}_"

        print(f"[SEARCH] 正在尋找開頭為 '{prefix}' 的 PDF...")

        for f in os.listdir(self.INPUT_DIR):
            if f.startswith(prefix) and f.lower().endswith(".pdf"):
                full_path = os.path.join(self.INPUT_DIR, f)
                print(f"[FOUND] 找到目標檔案：{f}")
                return full_path, f

        raise FileNotFoundError(
            f"❌ 在 {self.INPUT_DIR} 找不到符合條件的檔案。\n"
            f"搜尋條件: {prefix}...\n"
            f"請確認檔名是否為：年份_代碼_公司名稱.pdf (例如: 2024_2330_台積電.pdf)"
        )

    # --- PDF 處理 ---
    def extract_pdf_text(self) -> str:
        text_parts = []
        print(f"[PDF] 讀取中: {self.pdf_path}")
        with pdfplumber.open(self.pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"[PDF] 總頁數: {total_pages}")
            for i, page in enumerate(pdf.pages, start=1):
                txt = page.extract_text()
                if txt:
                    text_parts.append(f"[頁碼: {i}]\n{txt.strip()}")
                if i % 20 == 0:
                    print(f"      ...已讀取 {i} 頁")
        return "\n\n".join(text_parts)

    def _split_text(self, full_text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(full_text):
            chunks.append(full_text[start: start + self.MAX_CHARS_TOTAL])
            start += self.MAX_CHARS_TOTAL
        return chunks

    # --- Gemini API ---
    def _call_gemini(self, prompt: str) -> str:
        last_error = None
        for model in [self.MODEL_DEFAULT] + self.MODEL_FALLBACKS:
            for _ in range(self.MAX_ATTEMPTS):
                try:
                    self.limiter.wait()
                    resp = self.client.models.generate_content(model=model, contents=prompt)
                    return resp.text or ""
                except Exception as e:
                    last_error = e
                    if "429" in str(e) or "404" in str(e):
                        print(f"[WARN] 模型 {model} 忙碌或錯誤，切換中...")
                        break
                    print(f"[RETRY] {model} 發生錯誤: {e}")
        raise RuntimeError(f"所有模型嘗試皆失敗: {last_error}")

    # --- 資料正規化 ---
    def _normalize_json(self, raw_text: str) -> List[Dict]:
        try:
            clean_text = re.sub(r"^```json|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
            start = clean_text.find("[")
            end = clean_text.rfind("]")
            if start != -1 and end != -1:
                clean_text = clean_text[start: end + 1]

            data = json.loads(clean_text)
            if isinstance(data, dict):
                data = [data]

            normalized = []
            for item in data:
                normalized.append({
                    "company_id": str(item.get("company_id", self.target_company_id))[:4],
                    "year": int(item.get("year", self.target_year)),
                    "ESG_category": str(item.get("ESG_category", ""))[:5],
                    "SASB_topic": str(item.get("SASB_topic", ""))[:20],
                    "page_number": str(item.get("page_number", ""))[:3],
                    "report_claim": str(item.get("report_claim", ""))[:500],
                    "greenwashing_factor": str(item.get("greenwashing_factor", ""))[:500],
                    "risk_score": str(item.get("risk_score", "0"))[:3]
                })
            return normalized
        except Exception as e:
            print(f"[PARSE ERROR] JSON 解析失敗 (跳過此段): {e}")
            return []

    # --- 執行主邏輯 ---
    def run(self):
        output_path = os.path.join(self.OUTPUT_DIR, self.output_json_name)

        if os.path.exists(output_path):
            print(f"[SKIP] 結果檔案已存在，不再重複執行: {output_path}")
            return

        full_text = self.extract_pdf_text()
        chunks = self._split_text(full_text)
        print(f"[INFO] 文本長度: {len(full_text)} 字, 切分為 {len(chunks)} 段處理")

        all_results = []
        for i, chunk in enumerate(chunks, 1):
            print(f"   >>> 正在分析第 {i}/{len(chunks)} 段...")
            prompt = f"""
你是一個專業的 ESG 稽核員。請分析以下報告片段，提取符合 SASB 標準的聲明與漂綠風險。

輸出需求 (JSON Array Only):
- company_id: "{self.target_company_id}"
- year: {self.target_year}
- ESG_category: "E"/"S"/"G"
- SASB_topic: (String)
- page_number: (String)
- report_claim: (摘要公司聲明)
- greenwashing_factor: (分析是否誇大或缺乏數據支持)
- risk_score: (0=低風險, 4=極高風險)

內容片段:
{chunk}
"""
            raw_resp = self._call_gemini(prompt)
            parsed_data = self._normalize_json(raw_resp)
            all_results.extend(parsed_data)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        print(f"\n[SUCCESS] 完成！結果已儲存至: {output_path}")
        print(f"總提取筆數: {len(all_results)}")


# =========================
# 使用者互動介面
# =========================
def main():
    print("=== ESG 報告書評分系統 (指定模式) ===")
    print("說明：系統將自動在 ESG_Reports 資料夾中搜尋符合 [年份]_[代碼] 的 PDF 檔。")
    print("-" * 50)

    while True:
        year_input = input("請輸入年份 (例如 2024): ").strip()
        if year_input.isdigit() and len(year_input) == 4:
            break
        print("❌ 年份格式錯誤，請輸入 4 位數字。")

    while True:
        id_input = input("請輸入公司代碼 (例如 2330): ").strip()
        if id_input:
            break
        print("❌ 公司代碼不能為空。")

    try:
        print(f"\n🚀 正在啟動分析程序: {year_input} 年, 公司代碼 {id_input}")
        scorer = ESGReportScorer(target_year=int(year_input), target_company_id=id_input)
        scorer.run()
    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"❌ 發生未預期的錯誤: {e}")


if __name__ == "__main__":
    main()
