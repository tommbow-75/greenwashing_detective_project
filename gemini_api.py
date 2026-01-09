import os
import json
import time
import re
from typing import Dict, List, Any

# ✅ 使用 Google 官方 GenAI SDK
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. 載入環境變數
load_dotenv()

# 取得程式檔案所在的目錄
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

class ESGReportAnalyzer:
    # ====== 設定檔與路徑 ======
    INPUT_DIR = os.path.join(SCRIPT_DIR, 'ESG_Reports')
    OUTPUT_DIR = "output_json"
    
    # 修正 1: SASB_weightMap.json 的檔案路徑調整為 ./static/data/
    SASB_MAP_FILE = os.path.join(SCRIPT_DIR, 'static', 'data', 'SASB_weightMap.json')
    
    # ✅ 使用 Gemini 2.0 Flash
    MODEL_NAME = "models/gemini-2.0-flash" 

    def __init__(self, target_year: int, target_company_id: str):
        # 取得 API Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("❌ 找不到 GEMINI_API_KEY，請檢查 .env 檔案。")

        self.client = genai.Client(api_key=api_key)
        self.target_year = target_year
        self.target_company_id = str(target_company_id).strip()

        # 準備輸出目錄
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

        # 載入資料
        self.pdf_path, self.pdf_filename = self._find_target_pdf()
        self.sasb_map_content = self._load_sasb_map()

        # 設定輸出檔名
        base_name = os.path.splitext(self.pdf_filename)[0]
        self.output_json_name = f"{base_name}_Analysis_Result.json"

    def _find_target_pdf(self) -> (str, str):
        """在 temp_data/esgReport 資料夾中搜尋符合 年份_代碼 的 PDF"""
        if not os.path.exists(self.INPUT_DIR):
            raise FileNotFoundError(f"資料夾不存在: {self.INPUT_DIR}")
        
        prefix = f"{self.target_year}_{self.target_company_id}"
        print(f"[SEARCH] 正在搜尋包含 '{prefix}' 的 PDF 檔案...")
        
        for f in os.listdir(self.INPUT_DIR):
            if prefix in f and f.lower().endswith(".pdf"):
                print(f"[FOUND] 找到檔案: {f}")
                return os.path.join(self.INPUT_DIR, f), f
                
        raise FileNotFoundError(f"❌ 找不到符合 {prefix} 的 PDF 檔。")

    def _load_sasb_map(self) -> str:
        """讀取 SASB Weight Map JSON"""
        if not os.path.exists(self.SASB_MAP_FILE):
             raise FileNotFoundError(f"❌ 找不到 SASB 權重表檔案: {self.SASB_MAP_FILE}")
        with open(self.SASB_MAP_FILE, 'r', encoding='utf-8') as f:
            return f.read()

    def upload_file_to_gemini(self):
        """將 PDF 上傳至 Gemini 伺服器"""
        print(f"[UPLOAD] 準備上傳: {self.pdf_filename} ...")
        safe_display_name = f"Report_{self.target_year}_{self.target_company_id}"

        try:
            with open(self.pdf_path, "rb") as f:
                file_ref = self.client.files.upload(
                    file=f,
                    config=types.UploadFileConfig(
                        display_name=safe_display_name,
                        mime_type="application/pdf"
                    )
                )
        except Exception as e:
            raise RuntimeError(f"上傳失敗: {e}")
        
        print(f"[UPLOAD] 上傳成功，URI: {file_ref.uri}")
        print(f"[WAIT] 等待 Google 處理檔案中...", end="")

        while file_ref.state.name == "PROCESSING":
            time.sleep(2)
            file_ref = self.client.files.get(name=file_ref.name)
            print(".", end="", flush=True)
        
        print()
        if file_ref.state.name != "ACTIVE":
            raise RuntimeError(f"❌ 檔案處理失敗，狀態: {file_ref.state.name}")
            
        print(f"[READY] 檔案準備就緒。")
        return file_ref

    def run(self):
        # 1. 上傳 PDF
        uploaded_pdf = self.upload_file_to_gemini()

        # 2. 建構 Prompt (修正 2: greenwashing_factor 強制輸出英文)
        print(">>> 發送分析請求 (Gemini 2.0 Flash)...")
        
        prompt_text = f"""
你是一個專業的 ESG 稽核員。請分析我提供的 PDF 檔案 (ESG 報告書)。

**任務輸入資料：**
1. **SASB 產業權重表 (JSON)**: 
{self.sasb_map_content}

**分析核心任務：**
1. **識別產業**：請閱讀報告書，從 SASB 權重表中識別該公司所屬的產業。
2. **完整列出議題**：找出該產業在權重表中所有的 SASB 議題，每一項議題都必須輸出一筆資料。
3. **評分邏輯 (Clarkson et al. 2008)**：
   - 0分：未揭露。
   - 1分 (軟性)：願景、口號或模糊承諾。
   - 2分 (定性)：具體管理措施，但缺乏數據。
   - 3分 (硬性/定量)：具體量化數據、歷史趨勢。
   - 4分 (確信/查驗)：數據經過第三方查驗/確信 (需嚴格檢查附錄)。
4. **特殊規則**：若議題屬於高權重 (2.0) 且未提及，請填寫 "report_claim": "N/A", "risk_score": 1。

**輸出欄位要求 (嚴格執行)：**
- **company_id**: "{self.target_company_id}"
- **year**: "{self.target_year}"
- **ESG_category**: E / S / G
- **SASB_topic**: 議題名稱
- **page_number**: 證據來源頁碼
- **report_claim**: 完整摘錄報告書原文句子，不得改寫。
- **greenwashing_factor**: (MUST BE IN ENGLISH) Analyze the data loopholes or risks based on Clarkson theory.
- **risk_score**: 0~4 分
- **Internal_consistency**: (Boolean)

**輸出格式**：
請直接輸出 JSON Array。
"""

        # 3. 呼叫模型 (修正 3: 使用參數 temperature=0)
        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=[
                    uploaded_pdf,
                    prompt_text
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0  # 設定為 0 以獲得最穩定的輸出
                )
            )

            # 4. 處理結果
            raw_json = response.text
            output_path = os.path.join(self.OUTPUT_DIR, self.output_json_name)

            try:
                parsed_data = json.loads(raw_json)
            except json.JSONDecodeError:
                clean_text = re.sub(r"^```json|```$", "", raw_json.strip(), flags=re.MULTILINE).strip()
                parsed_data = json.loads(clean_text)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                
            print(f"\n[SUCCESS] 分析完成！結果已儲存至: {output_path}")
            print(f"提取項目數: {len(parsed_data)}")

        except Exception as e:
            print(f"\n[ERROR] 分析過程發生錯誤: {e}")


# =========================
# 程式進入點
# =========================

if __name__ == "__main__":
    print("=== ESG 報告書自動分析系統 (Gemini 2.0 Flash) ===")
    
    t_year = input(f"請輸入年份 (預設 2024): ").strip() or "2024"
    t_id = input(f"請輸入公司代碼 (預設 2330): ").strip() or "2330"
    
    try:
        analyzer = ESGReportAnalyzer(int(t_year), t_id)
        analyzer.run()
    except Exception as e:
        print(f"\n❌ 程式執行中斷: {e}")