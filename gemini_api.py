"""
ESG 報告書自動分析模組

提供使用 Gemini AI 分析 ESG 永續報告書的功能。

主要類別：
    ESGReportAnalyzer: 核心分析器，使用 Gemini 2.0 Flash 模型分析 PDF 報告書

使用範例：
    # 基本使用
    from gemini_api import ESGReportAnalyzer
    
    analyzer = ESGReportAnalyzer(target_year=2024, target_company_id="2330")
    analyzer.run()  # 產生分析結果 JSON
"""

import os
import json
import time
import re
from typing import Dict, List, Any, Tuple

# ✅ 使用 Google 官方 GenAI SDK
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 取得程式檔案所在的目錄
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =========================
# 核心分析類別
# =========================

class ESGReportAnalyzer:
    """
    ESG 報告書分析器
    
    使用 Gemini 2.0 Flash AI 模型分析 ESG 永續報告書 PDF，
    根據 SASB 框架與 Clarkson 理論進行評分，產生結構化的 JSON 分析結果。
    
    屬性：
        INPUT_DIR: PDF 報告書輸入目錄
        OUTPUT_DIR: JSON 分析結果輸出目錄
        SASB_MAP_FILE: SASB 產業權重對照表路徑
        MODEL_NAME: 使用的 Gemini 模型名稱
    
    使用範例：
        analyzer = ESGReportAnalyzer(target_year=2024, target_company_id="2330")
        analyzer.run()  # 執行分析並儲存結果
    """
    
    # ====== 設定檔與路徑 ======
    INPUT_DIR = os.path.join(SCRIPT_DIR, 'temp_data', 'esgReport')
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'temp_data', 'prompt1_json')
    SASB_MAP_FILE = os.path.join(SCRIPT_DIR, 'static', 'data', 'SASB_weightMap.json')
    
    # ✅ 使用 Gemini 2.5 Flash Lite
    MODEL_NAME = "models/gemini-2.5-flash-lite" 

    def __init__(self, target_year: int, target_company_id: str, company_name: str = ''):
        """
        初始化 ESG 報告書分析器
        
        Args:
            target_year: 報告年份（例如：2024）
            target_company_id: 公司代碼（例如："2330"）
            company_name: 公司名稱（例如："台積電"）
        
        Raises:
            RuntimeError: 若找不到 GEMINI_API_KEY 環境變數
            FileNotFoundError: 若找不到符合條件的 PDF 檔案或 SASB 權重表
        """
        # 取得 API Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("❌ 找不到 GEMINI_API_KEY，請檢查 .env 檔案。")

        self.client = genai.Client(api_key=api_key)
        self.target_year = target_year
        self.target_company_id = str(target_company_id).strip()
        self.company_name = company_name or f'公司{target_company_id}'

        # 準備輸出目錄
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

        # 載入資料
        self.pdf_path, self.pdf_filename = self._find_target_pdf()
        self.sasb_map_content = self._load_sasb_map()

        # 設定輸出檔名：格式為 "{年份}_{公司代碼}_p1.json"
        self.output_json_name = f"{self.target_year}_{self.target_company_id}_p1.json"
        
        print(f"[CONFIG] 輸出檔名已設定為: {self.output_json_name}")

    def _parse_json_with_recovery(self, raw_json: str) -> List[Dict[str, Any]]:
        """
        嘗試解析 JSON，並在失敗時使用多重修復策略
        
        修復策略順序：
            1. 直接解析
            2. 清除 Markdown 標記後解析
            3. 修復被截斷的 JSON Array
        
        Args:
            raw_json: Gemini API 回傳的原始 JSON 字串
        
        Returns:
            List[Dict]: 解析後的 JSON 陣列
        
        Raises:
            RuntimeError: 若所有修復策略都失敗
        """
        # 策略 1: 直接解析
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as e:
            print(f"[WARN] 直接解析失敗: {e}")
        
        # 策略 2: 清除 Markdown 標記後解析
        clean_text = re.sub(r"^```json|```$", "", raw_json.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            print(f"[WARN] 清除 Markdown 後解析失敗: {e}")
        
        # 策略 3: 修復被截斷的 JSON Array
        print("[INFO] 嘗試修復被截斷的 JSON...")
        repaired_json = self._repair_truncated_json(clean_text)
        
        if repaired_json:
            try:
                parsed = json.loads(repaired_json)
                print(f"[SUCCESS] JSON 修復成功！保留 {len(parsed)} 筆完整資料")
                return parsed
            except json.JSONDecodeError as e:
                print(f"[ERROR] 修復後仍無法解析: {e}")
        
        # 所有策略都失敗
        raise RuntimeError(f"無法解析 Gemini 回應的 JSON (原始長度: {len(raw_json)} 字元)")

    def _repair_truncated_json(self, text: str) -> str:
        """
        修復被截斷的 JSON Array
        
        尋找最後一個完整的 JSON 物件，並重新封閉陣列。
        
        Args:
            text: 可能被截斷的 JSON 字串
        
        Returns:
            str: 修復後的 JSON 字串，若無法修復則回傳空字串
        """
        if not text.strip().startswith('['):
            return ""
        
        # 找到所有 "}," 的位置，這些是完整物件的結尾
        last_complete_obj = text.rfind('},')
        
        if last_complete_obj == -1:
            # 嘗試找單一物件結尾 "}"
            last_complete_obj = text.rfind('}')
            if last_complete_obj == -1:
                return ""
            # 檢查這個 } 後面是否是 ]
            remaining = text[last_complete_obj + 1:].strip()
            if remaining == ']':
                return text  # 原本就是完整的
            # 否則嘗試直接封閉
            return text[:last_complete_obj + 1] + ']'
        
        # 截取到最後一個完整物件
        repaired = text[:last_complete_obj + 1] + ']'
        return repaired

    def _find_target_pdf(self) -> Tuple[str, str]:
        """
        在輸入目錄中搜尋符合條件的 PDF 檔案
        
        Returns:
            Tuple[str, str]: (完整檔案路徑, 檔案名稱)
        
        Raises:
            FileNotFoundError: 若資料夾不存在或找不到符合條件的 PDF
        """
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
        """
        讀取 SASB 產業權重對照表
        
        Returns:
            str: SASB 權重表的 JSON 字串內容
        
        Raises:
            FileNotFoundError: 若找不到 SASB 權重表檔案
        """
        if not os.path.exists(self.SASB_MAP_FILE):
             raise FileNotFoundError(f"❌ 找不到 SASB 權重表檔案: {self.SASB_MAP_FILE}")
        with open(self.SASB_MAP_FILE, 'r', encoding='utf-8') as f:
            return f.read()

    def upload_file_to_gemini(self):
        """
        將 PDF 檔案上傳至 Gemini 伺服器
        
        Returns:
            Gemini 檔案參考物件
        
        Raises:
            RuntimeError: 若上傳失敗或檔案處理失敗
        """
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
        """
        執行完整的 ESG 報告書分析流程
        
        流程：
            1. 上傳 PDF 至 Gemini
            2. 建構分析 Prompt
            3. 呼叫 Gemini AI 模型進行分析
            4. 解析並儲存 JSON 結果
        
        產生的 JSON 格式：
            [
                {
                    "company": "台積電",
                    "company_id": "2330",
                    "year": "2024",
                    "esg_category": "E|S|G",
                    "sasb_topic": "議題名稱",
                    "page_number": "頁碼",
                    "report_claim": "報告書原文摘錄",
                    "greenwashing_factor": "中文漂綠風險分析",
                    "risk_score": "0-4",
                    "internal_consistency": true|false,
                    "key_word": "適合新聞搜尋的關鍵字"
                },
                ...
            ]
        """
        # 1. 上傳 PDF
        uploaded_pdf = self.upload_file_to_gemini()

        # 2. 建構 Prompt
        print(">>> 發送分析請求 (Gemini 2.0 Flash)...")
        
        prompt_text = f"""
你是一個專業的 ESG 稽核員。請分析我提供的 PDF 檔案 (ESG 報告書)。

**任務輸入資料：**
1. **SASB 產業權重表 (JSON)**: 
{self.sasb_map_content}

**分析核心任務：**
1. **識別產業**：請閱讀報告書，從 SASB 權重表中識別該公司所屬的產業。
2. **完整列出議題**：找出該產業在權重表中所有的 SASB 議題，每一項議題都必須輸出一筆資料，不可遺漏。
3. **評分邏輯 (基於 Clarkson et al. 2008)**：
   - 0分：未揭露。
   - 1分 (軟性)：僅有願景、口號或模糊承諾。
   - 2分 (定性)：有具體管理措施，但缺乏數據。
   - 3分 (硬性/定量)：具體量化數據、歷史趨勢。
   - 4分 (確信/查驗)：數據經過 ISAE 3000 或 AA1000 第三方查驗/確信 (須嚴格檢查附錄查證聲明)。
4. **特殊規則**：若議題屬於高權重 (2.0) 且報告書完全未提及，請填寫 "report_claim": "N/A", "risk_score": 1。

**輸出欄位要求 (嚴格執行)：**
- **company**: "{self.company_name}"
- **company_id**: "{self.target_company_id}"
- **year**: "{self.target_year}"
- **esg_category**: E / S / G
- **sasb_topic**: 議題名稱
- **page_number**: 證據來源頁碼
- **report_claim**: 針對該議題，僅選取「最具數據代表性」的一段話。必須完整摘錄報告書原文，不得改寫。
- **greenwashing_factor**: (必須使用中文輸出) 基於 Clarkson 理論分析該數據的漏洞、漂綠疑慮或揭露風險。
- **risk_score**: 0~4 分
- **internal_consistency**: (Boolean)
- **key_word**: 根據 report_claim 內容，產生 3-5 個適合 Google News 搜尋的繁體中文關鍵字，以空格分隔。格式為：「公司名稱 + 核心指標/事件 + ESG相關詞」，例如「2024 台積電 淨零排放 RE100」或「 鴻海 碳排放強度 永續」。避免過長或抽象的詞彙。

**輸出格式**：
請直接輸出 JSON Array，不要包含 Markdown 標記。
"""

        # 3. 呼叫模型
        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=[
                    uploaded_pdf,
                    prompt_text
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0  # 設定為 0 以確保分析結果的嚴謹與穩定
                )
            )

            # 4. 處理結果
            raw_json = response.text
            output_path = os.path.join(self.OUTPUT_DIR, self.output_json_name)
            
            # 記錄原始回應長度，用於偵錯
            print(f"[DEBUG] 原始回應長度: {len(raw_json)} 字元")

            # 嘗試解析 JSON，使用多重修復策略
            parsed_data = self._parse_json_with_recovery(raw_json)
            
            # 存檔
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                
            print(f"\n[SUCCESS] 分析完成！結果已儲存至: {output_path}")
            print(f"提取項目數: {len(parsed_data)}")

        except Exception as e:
            print(f"\n[ERROR] 分析過程發生錯誤: {e}")


# =========================
# 主要分析接口
# =========================

def analyze_esg_report(pdf_path: str, year: int, company_code: str, company_name: str = '', industry: str = '') -> dict:
    """
    使用 Gemini AI 分析 ESG 永續報告書
    
    調用 ESGReportAnalyzer 進行真實的 AI 分析，產生結構化的分析結果。
    
    Args:
        pdf_path: PDF 檔案的絕對路徑（目前為參考用，實際使用 ESGReportAnalyzer 搜尋機制）
        year: 報告年份
        company_code: 公司代碼
        company_name: 公司名稱（選填）
        industry: 產業類別（選填）
    
    Returns:
        dict: 分析結果
        {
            'company_name': str,
            'industry': str,
            'url': str,
            'analysis_items': [...],  # P1 JSON 格式
            'output_path': str,       # 產生的 JSON 檔案路徑
            'item_count': int         # 分析項目數
        }
    
    Raises:
        RuntimeError: 若 AI 分析過程發生錯誤
        FileNotFoundError: 若找不到 PDF 或必要的設定檔
    """
    print(f"\n=== 啟動 AI 分析 (Gemini 2.0 Flash) ===")
    print(f"    年份: {year}, 公司代碼: {company_code}")
    
    try:
        # 1. 初始化分析器
        analyzer = ESGReportAnalyzer(
            target_year=int(year),
            target_company_id=str(company_code),
            company_name=company_name
        )
        
        # 2. 執行 AI 分析（會產生 P1 JSON 檔案）
        analyzer.run()
        
        # 3. 讀取產生的 P1 JSON
        output_path = os.path.join(analyzer.OUTPUT_DIR, analyzer.output_json_name)
        
        if not os.path.exists(output_path):
            raise RuntimeError(f"AI 分析完成但找不到輸出檔案: {output_path}")
        
        with open(output_path, 'r', encoding='utf-8') as f:
            analysis_items = json.load(f)
        
        print(f"✅ AI 分析完成，讀取 {len(analysis_items)} 筆分析項目")
        
        # 4. 回傳結果（與 app.py 相容的格式）
        return {
            'company_name': company_name or f'公司{company_code}',
            'industry': industry or '其他',
            'url': f'https://mops.twse.com.tw/mops/web/t100sb07_{year}',
            'analysis_items': analysis_items,
            'output_path': output_path,
            'item_count': len(analysis_items)
        }
        
    except FileNotFoundError as e:
        raise FileNotFoundError(f"找不到必要檔案: {e}")
    except Exception as e:
        raise RuntimeError(f"AI 分析失敗: {e}")


# =========================
# 命令列執行入口
# =========================

def main():
    """
    命令列執行的主函數
    
    提供互動式界面，讓使用者輸入年份和公司代碼來執行分析。
    """
    print("=== ESG 報告書自動分析系統 (Gemini 2.0 Flash) ===")
    
    t_year = input(f"請輸入年份 (預設 2024): ").strip() or "2024"
    t_id = input(f"請輸入公司代碼 (預設 2330): ").strip() or "2330"
    
    try:
        analyzer = ESGReportAnalyzer(int(t_year), t_id)
        analyzer.run()
    except Exception as e:
        print(f"\n❌ 程式執行中斷: {e}")


if __name__ == "__main__":
    main()