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
import sys
from typing import Dict, List, Any, Tuple

# ✅ 使用 Google 官方 GenAI SDK
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 導入集中配置
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import PATHS, DATA_FILES


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
    INPUT_DIR = PATHS['ESG_REPORTS']
    OUTPUT_DIR = PATHS['P1_JSON']
    SASB_MAP_FILE = DATA_FILES['SASB_WEIGHT_MAP']
    
    # ====== 模型設定 ======
    # 預設使用 Gemini 2.5 Flash，若異常則切換至備用模型
    DEFAULT_MODEL = "models/gemini-2.5-flash"
    FALLBACK_MODEL = "models/gemini-3-flash-preview"
    
    # 輸出異常偵測閾值：若項目數超過唯一主題數的此倍數，視為異常
    ABNORMAL_THRESHOLD = 2 

    def __init__(self, target_year: int, target_company_id: str, company_name: str = '', industry: str = ''):
        """
        初始化 ESG 報告書分析器
        
        Args:
            target_year: 報告年份（例如：2024）
            target_company_id: 公司代碼（例如："2330"）
            company_name: 公司名稱（例如："台積電"）
            industry: 產業類別（例如："半導體產業"）
        
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
        self.industry = industry or '其他'

        # 準備輸出目錄
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

        # 載入資料
        self.pdf_path, self.pdf_filename = self._find_target_pdf()
        self.sasb_map_content = self._load_sasb_map()

        # 設定輸出檔名：格式為 "{年份}_{公司代碼}_p1.json"
        self.output_json_name = f"{self.target_year}_{self.target_company_id}_p1.json"
        
        print(f"[CONFIG] 輸出檔名已設定為: {self.output_json_name}")
        print(f"[CONFIG] 產業類別: {self.industry}")

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

    def _is_abnormal_output(self, parsed_data: List[Dict[str, Any]]) -> Tuple[bool, int, int]:
        """
        偵測 AI 輸出是否異常（重複項目過多）
        
        Args:
            parsed_data: 解析後的 JSON 陣列
        
        Returns:
            Tuple[bool, int, int]: (是否異常, 總項目數, 唯一主題數)
        """
        if not parsed_data:
            return False, 0, 0
        
        # 計算唯一的 sasb_topic 數量
        unique_topics = set(item.get('sasb_topic', '') for item in parsed_data)
        total_items = len(parsed_data)
        unique_count = len(unique_topics)
        
        # 若項目數超過唯一主題數的 N 倍，視為異常
        is_abnormal = total_items > unique_count * self.ABNORMAL_THRESHOLD
        
        return is_abnormal, total_items, unique_count

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

    def _build_prompt(self) -> str:
        """
        建構 ESG 分析 Prompt
        
        Returns:
            str: 完整的分析提示詞
        """
        return f"""
你是一個專業的 ESG 稽核員。請分析我提供的 PDF 檔案 (ESG 報告書)。

**任務輸入資料：**
1. **SASB 產業權重表 (JSON)**: 
{self.sasb_map_content}

**分析核心任務：**
1. **目標**：請依據SASB 產業權重表，識別{self.industry}產業的SASB議題，從報告中找出每一項議題對應的宣稱report_claim，並依以下評分邏輯進行評分。
2. **評分邏輯 (基於 Clarkson et al. 2008)**：
   - 0分：未揭露。
   - 1分 (軟性)：僅有願景、口號或模糊承諾。
   - 2分 (定性)：有具體管理措施，但缺乏數據。
   - 3分 (硬性/定量)：具體量化數據、歷史趨勢。
   - 4分 (卓越揭露)：滿足下列 **任一條件** 即可得 4 分：
    - **條件 A (第三方確信)**：數據明確標註經過 ISAE 3000 或 AA1000 第三方查證。
    - **條件 B (完整透明度)**：雖無第三方查證，但同時滿足以下兩要素：
        1. **明確目標**：設定具體的未來量化目標 (Target)。
        2. **細節拆解**：數據有進行細項拆解 (例如：按性別、地區、範疇分類) **或** 清楚說明計算方法學/標準 (如 GRI 編號、計算公式)。
3. **重大議題檢核**：
   - **權重判斷**：根據 SASB 產業權重表，每個議題都有對應的權重值（1 或 2）。
   - **權重 1（低重大性）+ 未揭露**：若該議題的權重為 1，且報告書完全未提及，則**不需要輸出此條目**。
   - **權重 2（高重大性）+ 未揭露**：若該議題的權重為 2，但報告書完全未提及，屬於重大資訊缺失。請務必填寫 "report_claim": "N/A", "risk_score": 1。
4. **邏輯一致性檢查**：請檢查報告前後文。若同一議題的數據或宣稱出現矛盾 (例如不同章節數字不符)，請將 "Internal_consistency": false，並在 "greenwashing_factor" 具體指出矛盾點，同時將最終 risk_score 扣減 1 分 (最低為 0)；若一致則 "Internal_consistency": true。
5. **漂綠因子分析(greenwashing_factor)**：(必須使用中文輸出，嚴禁填寫「無」或任何空泛內容)
    - 請依據以下框架進行分析，必須輸出實質內容：
      **A. 內部一致性檢查**（若 internal_consistency 為 false）
      - 格式：「[數據矛盾] 第X頁提及數值為Y，但第Z頁卻為W，存在差異」
      **B. 透明度評估**（若 risk_score ≤ 2）
      - 格式：「[資訊不足] 僅提及願景/口號，未披露具體措施/執行時程/責任單位」
      - 或：「[定性描述] 雖有管理措施說明，但缺乏基準年/目標值/歷史趨勢數據」
      **C. 量化程度評估**（若 risk_score = 3）
      - 格式：「[待加強] 已揭露具體數據，但未取得第三方查驗，可信度有限」
      **D. 低風險說明**（若 risk_score = 4）
      - 格式：「[已查驗] 數據經查驗機構依標準確信，資訊透明度高」
      **E. 重大缺漏**（若為 N/A）
      - 格式：「[重大缺漏] 該議題為高重大性（權重2），但報告書完全未提及」
    - 每個項目必須選擇上述至少一個分析角度，嚴禁使用「無漂綠風險」、「無」、「無明顯問題」等籠統描述。
6. **一議題一條目**：每個 sasb_topic 在 JSON Array 中最多只能出現一次。
7. **選擇原則**：若同一議題在報告中多處提及，必須選取「數據最完整、風險評分最高」的那一處，不得全部輸出。

**輸出欄位要求 (嚴格執行)：**
- **company**: "{self.company_name}"
- **company_id**: "{self.target_company_id}"
- **year**: "{self.target_year}"
- **esg_category**: 必須嚴格依據以下 SASB 議題分類對照表填寫，僅能使用 E、S、G 其中一個英文字母：
  **E（環境）**：溫室氣體排放、空氣品質、能源管理、水資源與廢水處理管理、廢棄物與有害物質管理、生態影響、材料採購與效率、氣候變遷的實質影響
  **S（社會）**：人權與社區關係、勞工法規、員工健康與安全、員工忠誠度、多元化和包容性、供應鏈管理、產品設計與生命週期管理、產品品質與安全、顧客權益、行銷策略與產品標示
  **G（治理）**：顧客隱私、資訊安全、通路與價格、商業模式韌性、商業道德、競爭行為、法規遵循、重大事件風險管理、系統性風險管理
  嚴禁使用 E、S、G 以外的任何字元。
- **sasb_topic**: 議題名稱（必須與 SASB 權重表中的議題名稱完全一致）
- **page_number**: 證據來源頁碼
- **report_claim**: 針對該議題，僅選取「最具數據代表性」的一段話。必須完整摘錄報告書原文，不得改寫。
- **greenwashing_factor**: 根據漂綠因子分析，填寫具體分析說明。
- **risk_score**: 0~4 分
- **internal_consistency**: (Boolean)
- **key_word**: 根據 report_claim 內容，產生 3-5 個適合 Google News 搜尋的繁體中文關鍵字，以空格分隔。格式為：「公司名稱 + 核心指標/事件 + ESG相關詞」，例如「2024 台積電 淨零排放 RE100」或「 鴻海 碳排放強度 永續」。避免過長或抽象的詞彙。

**輸出格式**：
請直接輸出 JSON Array，不要包含 Markdown 標記。
"""

    def _call_gemini_api(self, uploaded_pdf, prompt_text: str, model_name: str, temperature: float) -> str:
        """
        呼叫 Gemini API 進行分析
        
        Args:
            uploaded_pdf: 已上傳的 PDF 檔案參考
            prompt_text: 分析提示詞
            model_name: Gemini 模型名稱
            temperature: 生成溫度參數
        
        Returns:
            str: API 回傳的原始 JSON 字串
        """
        response = self.client.models.generate_content(
            model=model_name,
            contents=[uploaded_pdf, prompt_text],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature
            )
        )
        return response.text

    def run(self):
        """
        執行完整的 ESG 報告書分析流程（含自動重試機制）
        
        重試策略：
            1. 預設使用 gemini-2.5-flash + temperature=0.1
            2. 若偵測到輸出異常，提高 temperature 至 0.2 重試
            3. 若仍異常，切換至 gemini-3-flash-preview 重試
        
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
        # 重試策略配置
        retry_configs = [
            {"model": self.DEFAULT_MODEL, "temperature": 0.1, "desc": "gemini-2.5-flash (temp=0.1)"},
            {"model": self.DEFAULT_MODEL, "temperature": 0.2, "desc": "gemini-2.5-flash (temp=0.2)"},
            {"model": self.FALLBACK_MODEL, "temperature": 0.1, "desc": "gemini-3-flash-preview (temp=0.1)"},
        ]
        
        # 1. 上傳 PDF
        uploaded_pdf = self.upload_file_to_gemini()
        
        # 2. 建構 Prompt
        prompt_text = self._build_prompt()
        
        output_path = os.path.join(self.OUTPUT_DIR, self.output_json_name)
        best_result = None  # 保存最佳結果（項目數最接近預期的）
        
        # 3. 嘗試各種配置
        for attempt, config in enumerate(retry_configs, 1):
            model_name = config["model"]
            temperature = config["temperature"]
            desc = config["desc"]
            
            print(f"\n>>> 嘗試 #{attempt}: {desc}")
            
            try:
                # 呼叫 API
                raw_json = self._call_gemini_api(uploaded_pdf, prompt_text, model_name, temperature)
                print(f"[DEBUG] 原始回應長度: {len(raw_json)} 字元")
                
                # 解析 JSON
                parsed_data = self._parse_json_with_recovery(raw_json)
                
                # 偵測異常
                is_abnormal, total_items, unique_count = self._is_abnormal_output(parsed_data)
                
                if is_abnormal:
                    print(f"⚠️ 偵測到異常輸出：{total_items} 筆項目，但只有 {unique_count} 個唯一主題")
                    
                    # 保存最佳結果（選擇項目數最少的）
                    if best_result is None or total_items < len(best_result):
                        best_result = parsed_data
                    
                    if attempt < len(retry_configs):
                        print(f"🔄 準備重試...")
                        continue
                    else:
                        print(f"❌ 所有重試配置都失敗，使用最佳結果（{len(best_result)} 筆）")
                        parsed_data = best_result
                else:
                    print(f"✅ 輸出正常：{total_items} 筆項目，{unique_count} 個唯一主題")
                
                # 存檔
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                
                print(f"\n[SUCCESS] 分析完成！結果已儲存至: {output_path}")
                print(f"提取項目數: {len(parsed_data)}")
                return  # 成功完成
                
            except Exception as e:
                print(f"[ERROR] 嘗試 #{attempt} 發生錯誤: {e}")
                if attempt >= len(retry_configs):
                    raise RuntimeError(f"所有重試配置都失敗: {e}")


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
            company_name=company_name,
            industry=industry
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