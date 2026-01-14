import json, os, re, tiktoken, time
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. 載入 .env 檔案並初始化 Client
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("找不到 GEMINI_API_KEY。請確保 .env 檔案存在且設定正確。")

client = genai.Client(api_key=api_key)

# ===== Token estimation utilities =====
enc = tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(enc.encode(text))


def process_esg_news_verification(input_json_path, news_json_path, msci_json_path, output_json_path):
    """
    處理 ESG 新聞驗證
    
    Args:
        input_json_path: 原檔路徑 (2024_1102_p1_keyword.json)
        news_json_path: 驗證資料路徑 (2024_1102_news_results.json)
        msci_json_path: MSCI 判斷標準路徑 (msci_flag.json)
        output_json_path: 輸出結果路徑
    """
    total_start_time = time.perf_counter()
    
    # 2. 讀取原檔
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
        print(f"✅ 成功讀取原檔：{len(original_data)} 筆資料")
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到輸入檔案 {input_json_path}")
        return
    except json.JSONDecodeError:
        print(f"❌ 錯誤：輸入檔案 {input_json_path} 格式並非正確的 JSON")
        return

    # 3. 使用 pandas 讀取驗證資料
    try:
        news_df = pd.read_json(news_json_path, encoding='utf-8')
        print(f"✅ 成功讀取驗證資料：{len(news_df)} 筆新聞")
    except Exception as e:
        print(f"❌ 錯誤：讀取驗證資料失敗 - {e}")
        return

    # 4. 使用 pandas 讀取 MSCI 判斷標準
    try:
        with open(msci_json_path, 'r', encoding='utf-8') as f:
            msci_flag = json.load(f)
        print(f"✅ 成功讀取 MSCI 判斷標準")
    except Exception as e:
        print(f"❌ 錯誤：讀取 MSCI 標準失敗 - {e}")
        return

    # 5. 準備 Prompt（將變數嵌入）
    prompt_template = f"""
你將扮演ESG審查員，負責進行外部新聞比對與風險調整。

【原檔說明】
原檔為該公司永續報告書的聲明與風險分數，包含以下欄位：
- company: 股票代號
- year: 年分
- esg_category: ESG分類 (E/S/G)
- sasb_topic: SASB主題
- page_number: 頁碼
- report_claim: 企業聲明
- greenwashing_factor: 漂綠風險因子
- risk_score: 風險分數
- key_word: 關鍵字

【驗證資料說明】
驗證資料包含 {len(news_df)} 筆新聞，欄位如下：
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
{json.dumps(msci_flag, ensure_ascii=False, indent=2)}

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
- 檢查驗證資料是否明確提及 'company' 或 'company_code'
- 如果是在講其他公司，請判定為無效
- 檢查新聞內容是否與 report_claim 的主題有實質關聯？
- 如果發現新聞與公司無關、主題完全不符、無新聞，請直接輸出：
  * consistency_status: "一致"
  * external_evidence: "無相關新聞證據"
  * external_evidence_url: ""
  * MSCI_flag: "Green"
  * adjustment_score: (維持原 risk_score)

【輸出格式】
輸出欄位要求 (嚴格執行)，不要添加任何前言、後語或說明文字。：
**company**: {original_data[0]['company']},
**year**: {original_data[0]['year']},
**esg_category**: {original_data[0]['esg_category']},
**sasb_topic**: {original_data[0]['sasb_topic']},
**page_number**: {original_data[0]['page_number']},
**report_claim**: {original_data[0]['report_claim']},
**greenwashing_factor**: {original_data[0]['greenwashing_factor']},
**risk_score**: {original_data[0]['risk_score']},
**external_evidence**: 驗證資料標題或'無相關新聞證據',
**external_evidence_url**: 驗證資料新聞連結或空字串,
**consistency_status**: 一致/部分一致/部分一致/不一致(對應MSCI_flag),
**MSCI_flag**: Green/Yellow/Orange/Red,
**adjustment_score**: "調整後分數（最低為0）"


絕對不要強行將無關的新聞連結到企業聲稱上。
請直接輸出 JSON Array。
"""

    # 6. 將原檔和驗證資料轉為字串
    user_input = f"""
    【原檔數據】
    {json.dumps(original_data, ensure_ascii=False, indent=2)}

    【驗證資料】
    {news_df.to_json(orient='records', force_ascii=False, indent=2)}
    """

    # ===== Token count (input) =====
    input_token_est = estimate_tokens(prompt_template + user_input)
    print(f"\n📊 估計輸入 Token 數：{input_token_est:,}")

    # 7. 呼叫 Gemini API（啟用 grounding with google search）
    print("\n🔄 正在呼叫 Gemini API 並檢索外部資訊，請稍候...")
    api_start_time = time.perf_counter()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=prompt_template,
                temperature=0,
                response_mime_type="application/json"
                # tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
    except Exception as e:
        print(f"❌ API 呼叫失敗: {e}")
        return

    api_end_time = time.perf_counter()
    api_elapsed = api_end_time - api_start_time
    print(f"✅ Gemini API 呼叫完成，耗時 {api_elapsed:.2f} 秒")

    # 8. 處理與儲存結果
    raw_text = response.text.strip()

    # ===== Token count (output) =====
    output_token_est = estimate_tokens(raw_text)
    total_token_est = input_token_est + output_token_est

    # 顯示原始回應前 500 字元用於調試
    print(f"\n📄 API 原始回應（前 500 字元）：\n{raw_text[:500]}\n")
    
    try:
        final_json = None
        
        # 方法 1: 檢測並移除 markdown 代碼塊標記（優先）
        if raw_text.startswith("```json") or raw_text.startswith("```"):
            print("🔍 檢測到 markdown 代碼塊格式，正在移除標記...")
            # 移除開頭的 ```json 或 ```
            clean_text = re.sub(r'^```(?:json)?\s*\n?', '', raw_text)
            # 移除結尾的 ```
            clean_text = re.sub(r'\n?```\s*$', '', clean_text)
            
            try:
                final_json = json.loads(clean_text.strip())
                print("✅ 使用方法 1（移除 markdown 標記）成功解析")
            except json.JSONDecodeError as e:
                print(f"⚠️  方法 1 失敗: {e}")
        
        # 方法 2: 使用正則表達式提取 JSON 代碼塊
        if not final_json and "```" in raw_text:
            print("🔍 嘗試使用正則表達式提取 JSON...")
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', raw_text, re.DOTALL)
            if json_match:
                try:
                    final_json = json.loads(json_match.group(1))
                    print("✅ 使用方法 2（正則提取 markdown）成功解析")
                except json.JSONDecodeError as e:
                    print(f"⚠️  方法 2 失敗: {e}")
        
        # 方法 3: 直接查找 JSON 陣列（無 markdown 標記）
        if not final_json:
            print("🔍 嘗試直接查找 JSON 陣列...")
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
                    print("✅ 使用方法 3（直接提取陣列）成功解析")
                except json.JSONDecodeError as e:
                    print(f"⚠️  方法 3 失敗: {e}")
        
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


if __name__ == "__main__":
    # 設定檔案路徑
    input_path = './temp_data/prompt1_json/2024_1102_p1_keyword.json'
    news_path = './news_search/news_output/2024_1102_news_results.json'
    msci_path = './static/data/msci_flag.json'
    output_path = './temp_data/prompt2_json/2024_1102_p2.json'
    
    process_esg_news_verification(input_path, news_path, msci_path, output_path)
