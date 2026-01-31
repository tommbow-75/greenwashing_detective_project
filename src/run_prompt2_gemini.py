import json, os, re, sys, time
import pandas as pd
from dotenv import load_dotenv

# 支援 Vertex AI 和 GenAI SDK（向後相容）
import vertexai
from vertexai.generative_models import GenerativeModel

# 備用：保留 GenAI SDK 支援
try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

# 導入集中配置
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import PATHS, DATA_FILES

# 1. 載入 .env 檔案並判斷使用哪種 SDK
load_dotenv()

# 初始化 AI 客戶端（優先使用 Vertex AI）
project_id = os.getenv("GCP_PROJECT_ID")
location = os.getenv("GCP_LOCATION", "asia-northeast1")

if project_id:
    # 使用 Vertex AI（生產環境推薦）
    print(f"[CONFIG] 使用 Vertex AI (專案: {project_id}, 區域: {location})")
    vertexai.init(project=project_id, location=location)
    USE_VERTEX_AI = True
    client = None
    model = None  # 將在呼叫時創建
else:
    # 回退到 GenAI SDK（本地開發或備用）
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 請設定 GCP_PROJECT_ID（Vertex AI）或 GEMINI_API_KEY（GenAI SDK）")
    
    print(f"[CONFIG] 使用 GenAI SDK (API Key)")
    if not HAS_GENAI_SDK:
        raise RuntimeError("❌ GenAI SDK 未安裝，無法使用 API Key 模式")
    
    client = genai.Client(api_key=api_key)
    USE_VERTEX_AI = False
    model = None


def process_esg_news_verification(input_json_path, news_json_path, msci_json_path, output_json_path):
    """
    處理 ESG 新聞驗證
    
    Args:
        input_json_path: 原檔路徑 (2024_1102_p1.json)
        news_json_path: 驗證資料路徑 (2024_1102_news.json)
        msci_json_path: MSCI 判斷標準路徑 (msci_flag.json)
        output_json_path: 輸出結果路徑
    
    Returns:
        dict: {
            'success': bool,
            'processed_items': int,
            'input_tokens': int,
            'output_tokens': int,
            'total_tokens': int,
            'api_time': float,
            'total_time': float
        }
    """

    # 2. 讀取原檔
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
        print(f"✅ 成功讀取原檔：{len(original_data)} 筆資料")
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到輸入檔案 {input_json_path}")
        return {'success': False, 'error': 'FileNotFoundError'}
    except json.JSONDecodeError:
        print(f"❌ 錯誤：輸入檔案 {input_json_path} 格式並非正確的 JSON")
        return {'success': False, 'error': 'JSONDecodeError'}

    # 3. 直接讀取驗證資料
    try:
        with open(news_json_path, 'r', encoding='utf-8') as f:
            news_data = json.load(f)
        print(f"✅ 成功讀取驗證資料：{len(news_data)} 筆新聞")
    except Exception as e:
        print(f"❌ 錯誤：讀取驗證資料失敗 - {e}")
        return {'success': False, 'error': f'News data read error: {e}'}

    # 4. 使用 pandas 讀取 MSCI 判斷標準
    try:
        with open(msci_json_path, 'r', encoding='utf-8') as f:
            msci_flag = json.load(f)
        print(f"✅ 成功讀取 MSCI 判斷標準")
    except Exception as e:
        print(f"❌ 錯誤：讀取 MSCI 標準失敗 - {e}")
        return {'success': False, 'error': f'MSCI data read error: {e}'}

    # 5. 使用 pandas 提取公司資訊
    df_original = pd.DataFrame(original_data)
    company_name = df_original.iloc[0]['company']
    company_code = df_original.iloc[0]['company_id']

    # 6. 準備 Prompt（將變數嵌入）
    prompt_template = f"""
你將扮演ESG審查員，負責進行外部新聞比對與風險調整。

【原檔說明】
原檔為該公司永續報告書的聲明與風險分數，包含以下欄位：
- company: 公司名稱（例如："亞泥"）
- company_id: 公司代碼（例如："1102"）
- year: 年分
- esg_category: ESG分類 (E/S/G)
- sasb_topic: SASB主題
- page_number: 頁碼
- report_claim: 企業聲明
- greenwashing_factor: 漂綠風險因子
- risk_score: 風險分數
- key_word: 關鍵字

【驗證資料說明】
驗證資料包含 {len(news_data)} 筆新聞，欄位如下：
- news_id: 新聞編號
- stock_code: 股票代號
- company_name: 公司名稱
- sasb_topic: SASB主題
- search_query: 搜尋關鍵字
- title: 新聞標題
- url: 新聞連結
- published_date: 發布日期
- publisher: 發布者

【MSCI 風險旗號判斷標準】
  **Environment**: 
    "Red": "大規模生態浩劫",
    "Orange": "重大違規但可控",
    "Yellow": "反覆發生的合規問題",
    "Green": "無重大裁罰、符合當地法規，僅有零星排放超標紀錄"
  ,
  **HumanCapital**: 
    "Red": "系統性人權侵犯",
    "Orange": "結構性歧視或嚴重職災",
    "Yellow": "單一勞資糾紛",
    "Green": "零星的勞資爭議、一般性的離職率波動，或已解決的單一罰單"
  ,
  **SocialCapital**: 
    "Red": "災難性產品風險或隱私崩潰",
    "Orange": "重大產品召回或集體訴訟",
    "Yellow": "局部性投訴",
    "Green": "一般性的客戶服務投訴、零星的退貨問題"
  ,
  **LeadershipAndGovernance**: 
    "Red": "核心系統崩潰或大規模貪腐",
    "Orange": "重大治理缺陷",
    "Yellow": "行政處分或單一案件",
    "Green": "正常的董事會改選、微小的行政疏失補正"

【處理邏輯】
1. 風險調整邏輯依照上述 MSCI 標準
2. 使用鏈式思考，先判斷「受影響人數」、「是否涉及死亡」、「是否違反法規」，最後再輸出旗號
3. 扣分機制：red = -4, orange = -2, yellow = -1, green = 0
4. 特別注意「橘旗」與「紅旗」的邊界：
   - Red 通常涉及「系統性、長期、不可逆」
   - Orange 則多為「大規模、嚴重、但已開始修復」
5. 先比對 sasb_topic 一致，再依據原檔 report_claim 從驗證資料選出一筆最具代表性的新聞
6. 若原檔輸入 X 筆聲稱，就要輸出 X 筆結果

【相關性檢查】
比對前，請先執行相關性檢查：
- **目標公司**: {company_name} (股票代號: {company_code})
- **核心原則**: 新聞內容必須明確提及「{company_name}」**或**「{company_code}」
- **只有在以下情況才輸出「無相關新聞證據」**:
  1. 新聞完全沒有提到公司名稱「{company_name}」也沒有提到股票代號「{company_code}」
  2. 該 SASB 議題確實沒有任何相關新聞
- 若符合以上任一條件，請輸出：
  * consistency_status: "一致"
  * external_evidence: "無相關新聞證據"
  * external_evidence_url: ""
  * msci_flag: "Green"
  * adjustment_score: (維持原 risk_score)

【輸出格式】
輸出欄位要求 (嚴格執行)，不要添加任何前言、後語或說明文字。

重要：請保持原檔欄位名稱不變，特別是：
- **company** 必須維持原檔的公司名稱格式（例如 "亞泥"），不要轉換為代碼
- **company_id** 必須維持原檔的公司代碼（例如 "1102"）
- **report_claim** 欄位名稱維持不變，不要改為 disclosure_claim

輸出範例：
**company**: {company_name},  # 必須是名稱，例如 "南亞"
**company_id**: {company_code},  # 必須是代號，例如 "1303"
**year**: {original_data[0]['year']},
**esg_category**: {original_data[0]['esg_category']},
**sasb_topic**: {original_data[0]['sasb_topic']},
**page_number**: {original_data[0]['page_number']},
**report_claim**: {original_data[0]['report_claim']},  # 維持此欄位名稱
**greenwashing_factor**: {original_data[0]['greenwashing_factor']},
**risk_score**: {original_data[0]['risk_score']},
**external_evidence**: 驗證資料標題或'無相關新聞證據',
**external_evidence_url**: 驗證資料新聞連結或空字串,
**consistency_status**: 一致/部分符合/部分符合/不一致(分別對應Green/Yellow/Orange/Red),
**msci_flag**: Green/Yellow/Orange/Red(分別對應一致/部分符合/部分符合/不一致),
**adjustment_score**: 調整後分數（最低為0）


絕對不要強行將無關的新聞連結到企業聲稱上。
請直接輸出 JSON Array。
"""

    # 6. 將原檔和驗證資料轉為字串
    user_input = f"""
    【原檔數據】
    {json.dumps(original_data, ensure_ascii=False, indent=2)}

    【驗證資料】
    {json.dumps(news_data, ensure_ascii=False, indent=2)}
    """

    # 7. 呼叫 Gemini API
    print("\n🔄 正在呼叫 Gemini API，請稍候...")
    
    # 記錄開始時間
    total_start_time = time.perf_counter()
    api_start_time = time.perf_counter()


    try:
        if USE_VERTEX_AI:
            # Vertex AI API - 在創建模型時設定 system_instruction
            model_instance = GenerativeModel(
                "gemini-2.0-flash-exp",
                system_instruction=prompt_template
            )
            response = model_instance.generate_content(
                contents=user_input,
                generation_config={
                    "temperature": 0,
                    "response_mime_type": "application/json"
                }
            )
        else:
            # GenAI SDK API
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_input,
                config=types.GenerateContentConfig(
                    system_instruction=prompt_template,
                    temperature=0,
                    response_mime_type="application/json"
                )
            )
    except Exception as e:
        print(f"❌ API 呼叫失敗: {e}")
        return {'success': False, 'error': f'API call failed: {e}'}

    
    api_elapsed = time.perf_counter() - api_start_time
    print(f"✅ Gemini API 呼叫完成 (耗時: {api_elapsed:.2f} 秒)")
    
    # 簡易 token 估算（實際值需從 API response 取得，這裡使用估算）
    input_token_est = len(user_input) // 4  # 粗估: 1 token ≈ 4 字元
    output_token_est = len(response.text) // 4
    total_token_est = input_token_est + output_token_est


    # 8. 處理與儲存結果
    raw_text = response.text.strip()

    # 8. 處理與儲存結果 - 直接查找 JSON 陣列
    print("\n🔍 正在解析 JSON 回應...")
    
    try:
        final_json = None
        all_arrays = re.findall(r'(\[.*\])', raw_text, re.DOTALL)
        if all_arrays:
            clean_json_str = all_arrays[0]
            # 處理可能的多個陣列
            if "][" in clean_json_str:
                clean_json_str = clean_json_str.split("][")[0] + "]"
            elif "] [" in clean_json_str:
                clean_json_str = clean_json_str.split("] [")[0] + "]"
            
            try:
                final_json = json.loads(clean_json_str)
                print("✅ JSON 解析成功")
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 解析失敗: {e}")
        
        # 儲存結果
        if final_json:
            os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(final_json, f, ensure_ascii=False, indent=2)
            print(f"✅ 成功！結果已儲存至 {output_json_path}，共 {len(final_json)} 筆")
        else:
            raise ValueError("無法從回應中提取 JSON 結構")

    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析錯誤: {e}")
        print("⚠️  正在嘗試修復模式...")
        try:
            # 使用括號計數法提取完整 JSON
            start = raw_text.find('[')
            if start == -1:
                raise ValueError("找不到 JSON 陣列起始標記 '['")
            
            count = 0
            end_pos = -1
            for i in range(start, len(raw_text)):
                if raw_text[i] == '[':
                    count += 1
                elif raw_text[i] == ']':
                    count -= 1
                if count == 0:
                    end_pos = i + 1
                    break
            
            if end_pos > start:
                extreme_clean = raw_text[start:end_pos]
                final_json = json.loads(extreme_clean)
                os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(final_json, f, ensure_ascii=False, indent=2)
                print(f"✅ 修復成功！結果儲存至 {output_json_path}，共 {len(final_json)} 筆")
            else:
                raise ValueError("無法找到完整的 JSON 陣列")
        except Exception as repair_error:
            print(f"❌ 修復失敗：{repair_error}")
            # 將原始回應儲存到文件以便調試
            debug_path = output_json_path.replace('.json', '_debug_response.txt')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(raw_text)
            print(f"💾 已將完整原始回應儲存至：{debug_path}")
    except Exception as e:
        print(f"❌ 發生非預期錯誤: {e}")
        # 將原始回應儲存到文件以便調試
        debug_path = output_json_path.replace('.json', '_debug_response.txt')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        print(f"💾 已將完整原始回應儲存至：{debug_path}")

    # ===== TOKEN USAGE & TIME COST =====
    total_end_time = time.perf_counter()
    total_elapsed = total_end_time - total_start_time

    print("\n" + "="*50)
    print("📊 Token 使用統計")
    print("="*50)
    print(f"輸入 Token 數 : {input_token_est:,}")
    print(f"輸出 Token 數 : {output_token_est:,}")
    print(f"總計 Token 數 : {total_token_est:,}")
    print("\n" + "="*50)
    print("⏱️  執行時間統計")
    print("="*50)
    print(f"API 呼叫時間  : {api_elapsed:.2f} 秒")
    print(f"總執行時間    : {total_elapsed:.2f} 秒")
    print("="*50)
    
    # 返回統計資訊供模組化接口使用
    return {
        'success': True,
        'processed_items': len(final_json) if final_json else 0,
        'input_tokens': input_token_est,
        'output_tokens': output_token_est,
        'total_tokens': total_token_est,
        'api_time': api_elapsed,
        'total_time': total_elapsed
    }


def verify_esg_with_news(year, company_code, force_regenerate=False):
    """
    模組化接口：執行 ESG 新聞驗證與評分調整
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        force_regenerate: 是否強制重新生成（預設 False）
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'output_path': str,  # P2.json 路徑
            'skipped': bool,     # 是否跳過生成
            'statistics': {      # 執行統計
                'processed_items': int,
                'input_tokens': int,
                'output_tokens': int,
                'total_tokens': int,
                'api_time': float,
                'total_time': float
            },
            'error': str  # 錯誤訊息（若失敗）
        }
    """
    import time
    start_time = time.perf_counter()
    
    try:
        # 1. 自動構建檔案路徑
        base_filename = f"{year}_{company_code}"
        
        input_path = os.path.join(PATHS['P1_JSON'], f'{base_filename}_p1.json')
        news_path = os.path.join(PATHS['NEWS_SEARCH_OUTPUT'], f'{base_filename}_news.json')
        msci_path = DATA_FILES['MSCI_FLAG']
        output_path = os.path.join(PATHS['P2_JSON'], f'{base_filename}_p2.json')
        
        # 2. 檔案存在性檢查（跳過重複執行）
        if os.path.exists(output_path) and not force_regenerate:
            # 讀取已存在的檔案以獲取統計資訊
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                
                return {
                    'success': True,
                    'message': 'AI 驗證結果已存在，跳過生成',
                    'output_path': output_path,
                    'skipped': True,
                    'statistics': {
                        'processed_items': len(existing_data),
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'api_time': 0,
                        'total_time': time.perf_counter() - start_time
                    }
                }
            except Exception as e:
                # 檔案存在但無法讀取，刪除並重新生成
                print(f"⚠️ 現有檔案無法讀取，將重新生成: {e}")
                os.remove(output_path)
        
        # 3. 檢查必要輸入檔案
        missing_files = []
        if not os.path.exists(input_path):
            missing_files.append(f"P1 檔案: {input_path}")
        if not os.path.exists(news_path):
            missing_files.append(f"新聞檔案: {news_path}")
        if not os.path.exists(msci_path):
            missing_files.append(f"MSCI 標準: {msci_path}")
        
        if missing_files:
            return {
                'success': False,
                'message': '缺少必要輸入檔案',
                'error': ', '.join(missing_files),
                'output_path': None,
                'skipped': False
            }
        
        # 4. 執行 AI 驗證（獲取統計資訊）
        print(f"\n{'='*60}")
        print(f"開始 AI 驗證與評分調整: {year} 年 {company_code}")
        print(f"{'='*60}")
        
        # 呼叫原有函數並獲取統計資訊
        stats = process_esg_news_verification(input_path, news_path, msci_path, output_path)
        
        # 檢查執行結果
        if not stats or not stats.get('success'):
            error_msg = stats.get('error', 'Unknown error') if stats else 'Function returned None'
            return {
                'success': False,
                'message': 'AI 驗證執行失敗',
                'error': error_msg,
                'output_path': output_path,
                'skipped': False
            }
        
        total_time = time.perf_counter() - start_time
        
        # 5. 驗證輸出檔案
        if not os.path.exists(output_path):
            return {
                'success': False,
                'message': 'AI 驗證執行完成但未產生輸出檔案',
                'error': '輸出檔案不存在',
                'output_path': output_path,
                'skipped': False
            }
        
        # 6. 返回結果（使用從 process_esg_news_verification 獲得的統計資訊）
        return {
            'success': True,
            'message': 'AI 驗證完成',
            'output_path': output_path,
            'skipped': False,
            'statistics': {
                'processed_items': stats.get('processed_items', 0),
                'input_tokens': stats.get('input_tokens', 0),
                'output_tokens': stats.get('output_tokens', 0),
                'total_tokens': stats.get('total_tokens', 0),
                'api_time': stats.get('api_time', 0),
                'total_time': total_time
            }
        }
    
    except FileNotFoundError as e:
        return {
            'success': False,
            'message': '檔案不存在',
            'error': str(e),
            'output_path': None,
            'skipped': False
        }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'message': 'JSON 解析失敗',
            'error': str(e),
            'output_path': None,
            'skipped': False
        }
    except Exception as e:
        return {
            'success': False,
            'message': 'AI 驗證執行失敗',
            'error': str(e),
            'output_path': None,
            'skipped': False
        }


if __name__ == "__main__":
    year = "2024"
    company = "1102"
    # 設定檔案路徑
    input_path = os.path.join(PATHS['P1_JSON'], f'{year}_{company}_p1.json')
    news_path = os.path.join(PATHS['NEWS_SEARCH_OUTPUT'], f'{year}_{company}_news.json')
    msci_path = DATA_FILES['MSCI_FLAG']
    output_path = os.path.join(PATHS['P2_JSON'], f'{year}_{company}_p2.json')
    
    process_esg_news_verification(input_path, news_path, msci_path, output_path)
