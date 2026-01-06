import json
import os
import re
from dotenv import load_dotenv # 新增：導入載入工具
from google import genai
from google.genai import types

# 1. 載入 .env 檔案並初始化 Client
load_dotenv() # 自動尋找並載入同目錄下的 .env
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("找不到 GEMINI_API_KEY。請確保 .env 檔案存在且設定正確。")

client = genai.Client(api_key=api_key)

def process_esg_news_verification(input_json_path, output_json_path):
    # 2. 讀取第一個 JSON 檔 (原檔)
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
    except FileNotFoundError:
        print(f"錯誤：找不到輸入檔案 {input_json_path}")
        return
    except json.JSONDecodeError:
        print(f"錯誤：輸入檔案 {input_json_path} 格式並非正確的 JSON")
        return

    # 3. 準備 Prompt 2 (更新格式要求)
    prompt_template = """
    檔案為該公司永續報告書的聲明與風險分數，以下稱為"原檔"。
    請針對原檔企業聲稱，進行「外部驗證與風險評分調整」。

    【搜尋指引 - 解決查無新聞的策略】：
    1. **精確關鍵字搜尋**：請使用「公司名稱 + 2024 + 關鍵字」進行搜尋。
       - 環境(E)：裁罰、污染、超標、環境部裁罰紀錄、違規、大火。
       - 社會(S)：勞檢、職災、工安、裁罰、抗議、罷工、勞動部違反勞動法令紀錄。
       - 治理(G)：公平交易法、聯合行為、收賄、判決書、最高行政法院、金管會裁罰。
    2. **政府公開資料優先**：若查無媒體報導，請優先查核環境部、勞動部、司法院判決書系統、證交所公開資訊觀測站(MOPS)的 2024 年紀錄。
    3. **數據合理性判斷**：若外部查無負面資訊，但原檔數據顯示「指標退步」（如：受傷率 FR 增加、水回收率下降、裁罰筆數增加），即便無新聞，也應視為「管理失效」，不得給予 Green 旗。

    【旗號與扣分邏輯 (MSCI 爭議監測系統)】：
    1. 使用鏈式思考：先判斷「受影響人數」、「是否涉及死亡」、「是否違反法規」，最後再輸出旗號。
    2. 旗號定義：
       - Red (紅旗): 系統性、長期、不可逆之重大違規。扣 4 分。
       - Orange (橘旗): 大規模嚴重事件但已開始修復。扣 2 分。
       - Yellow (黃旗): 涉及行政裁罰、法律訴訟、或數據顯示管理退步。扣 1 分。
       - Green (綠旗): 查核後符合聲稱，且無外部負面證據或數據退步。扣 0 分。
    3. **調整分數 (adjustment_score) 計算**：
       計算公式 = [原檔 risk_score] - [上述扣分值]。最低分為 0。

    【格式要求】：
    請嚴格依照以下 JSON 格式輸出，X 筆輸入必須對應 X 筆輸出：
    [
      {{
        "company": "公司名稱",
        "year": "2024",
        "esg_category": "E/S/G (繼承自原檔)",
        "disclosure_claim": "原檔原文 (繼承自原檔)",
        "page_number": "頁碼 (繼承自原檔)",
        "external_evidence": "具體描述搜尋了哪個政府資料庫/新聞，以及發現了什麼(或查核了什麼沒發現)",
        "external_evidence_url": "具體來源網址，若無新聞則填寫相關政府機關首頁",
        "consistency_status": "符合 / 部分符合 / 不符合",
        "msci_flag": "Green / Yellow / Orange / Red",
        "adjustment_score": 數字
      }}
    ]

    【輸出規則】：僅輸出單一 JSON 陣列，嚴禁任何 Markdown 標籤（如 ```json）或額外解釋。
    """

    # 將 JSON1 的內容轉為字串放進 Prompt
    user_input = f"以下為原檔數據：\n{json.dumps(original_data, ensure_ascii=False)}"

    # 4. 呼叫 Gemini API
    print("正在呼叫 Gemini API 並檢索外部資訊，請稍候...")
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=prompt_template,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json"
            )
        )
    except Exception as e:
        print(f"API 呼叫失敗: {e}")
        return

    # 5. 處理與儲存結果 (沿用強效解析版)
    raw_text = response.text.strip()
    
    try:
        all_arrays = re.findall(r'(\[.*\])', raw_text, re.DOTALL)
        if all_arrays:
            clean_json_str = all_arrays[0]
            if "][" in clean_json_str:
                clean_json_str = clean_json_str.split("][")[0] + "]"
            elif "] [" in clean_json_str:
                clean_json_str = clean_json_str.split("] [")[0] + "]"

            final_json = json.loads(clean_json_str)
            
            os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(final_json, f, ensure_ascii=False, indent=2)
            print(f"成功！結果已儲存至 {output_json_path}")
        else:
            raise ValueError("模型回傳內容中找不到任何 JSON 陣列結構")

    except json.JSONDecodeError:
        print("正在嘗試極端修復模式...")
        try:
            start = raw_text.find('[')
            count = 0
            for i in range(start, len(raw_text)):
                if raw_text[i] == '[': count += 1
                elif raw_text[i] == ']': count -= 1
                if count == 0:
                    extreme_clean = raw_text[start:i+1]
                    final_json = json.loads(extreme_clean)
                    with open(output_json_path, 'w', encoding='utf-8') as f:
                        json.dump(final_json, f, ensure_ascii=False, indent=2)
                    print(f"極端修復成功！結果儲存至 {output_json_path}")
                    break
        except Exception as e:
            print(f"解析失敗：{e}")
    except Exception as e:
        print(f"發生非預期錯誤: {e}")

if __name__ == "__main__":
    # 設定檔案路徑
    input_path = './data/1229亞泥P1_test11.json'
    output_path = './data/1229亞泥P2_test1.json'
    
    process_esg_news_verification(input_path, output_path)