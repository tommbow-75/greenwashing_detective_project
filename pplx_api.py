import json
import os
import requests
from dotenv import load_dotenv
from perplexity import Perplexity
import time
import glob

load_dotenv()

PROMPT_TEMPLATE = """
檔案為該公司永續報告書的聲明與風險分數,以下稱為"原檔"
請幫我針對原檔企業聲稱,進行"外部新聞比對與風險調整"

要求:
1. 比對原檔企業聲稱 與 '外部新聞報導、第三方評級、或產業負面/正面資訊、實際裁罰紀錄(不要參照該公司自己官網的新聞)'
2. 外部資訊年份必須與原檔內年份一致,不需要以未來一年的事件去回推本年份的真實性
3. 風險調整邏輯依照msci_flag.json
4. 使用鏈式思考,先判斷「受影響人數」、「是否涉及死亡」、「是否違反法規」,最後再輸出旗號
5. red=-4, orange=-2, yellow=-1, green=0
6. 特別注意「橘旗」與「紅旗」的邊界。red通常涉及「系統性、長期、不可逆」;orange則多為「大規模、嚴重、但已開始修復」
7. 若原檔輸入X筆聲稱,就要輸出X筆結果
8. 最低分為0分

輸出JSON格式(嚴格執行),每筆資料包含:
- company: 公司股票代碼
- year: 年份
- original_claim: 原始聲明
- original_score: 原始分數
- external_evidence: 外部新聞資料
- external_evidence_url: 外部新聞資料連結
- consistency_status: 外部驗證結果(一致/部分一致/不一致)
- MSCI_flag: 風險分級(red/orange/yellow/green)
- adjustment_score: 調整後分數
- reasoning: 調整理由

【原檔資料】
{data}
"""

def analyze_with_perplexity(data):
    """使用 Perplexity 進行 ESG 風險分析"""
    try:
        perplexity_client = Perplexity(api_key=os.environ.get("PERPLEXITY_API_KEY"))
        
        # 將資料轉換為 JSON 字串並整合到 prompt
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        prompt = PROMPT_TEMPLATE.format(data=data_str)
        
        print("🔍 正在呼叫 Perplexity API 進行分析...")
        
        response = perplexity_client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 顯示 token 使用量
        usage = response.usage
        print(f"📊 Perplexity API 使用量:")
        print(f"  - Input tokens: {usage.prompt_tokens}")
        print(f"  - Output tokens: {usage.completion_tokens}")
        print(f"  - Total tokens: {usage.total_tokens}")
        
        # 解析回應內容
        content = response.choices[0].message.content
        
        # 清理 JSON 格式 (移除可能的 markdown 標記)
        clean_json = content.replace('```json', '').replace('```', '').strip()
        
        # 解析 JSON
        result = json.loads(clean_json)
        
        return result if isinstance(result, list) else [result]
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析錯誤: {e}")
        print(f"原始回應內容:\n{content}")
        return None
    except Exception as e:
        print(f"❌ Perplexity API 錯誤: {e}")
        return None

def process_json_file(input_file, output_file):
    """處理 ESG 分析流程"""
    print(f"📖 讀取檔案: {input_file}")
    
    # 讀取輸入檔案
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {input_file}")
        return
    except json.JSONDecodeError:
        print(f"❌ JSON 格式錯誤: {input_file}")
        return
    
    total = len(data)
    print(f"✅ 成功讀取 {total} 筆資料")
    
    # 使用 Perplexity 進行分析
    analysis_start = time.perf_counter()
    results = analyze_with_perplexity(data)
    analysis_duration = time.perf_counter() - analysis_start
    
    if results is None:
        print("❌ 分析失敗,無法產生結果")
        return
    
    print(f"⏱️ 分析耗時: {analysis_duration:.2f} 秒")
    print(f"✅ 成功分析 {len(results)} 筆資料")
    
    # 儲存結果
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"📁 結果已儲存至: {output_file}")
    except Exception as e:
        print(f"❌ 儲存檔案時發生錯誤: {e}")
        return
    
    # 顯示統計資訊
    print("\n📊 分析結果統計:")
    flag_counts = {}
    for item in results:
        flag = item.get('MSCI_flag', 'unknown')
        flag_counts[flag] = flag_counts.get(flag, 0) + 1
    
    for flag, count in sorted(flag_counts.items()):
        print(f"  - {flag}: {count} 筆")


def get_latest_file(folder_path, extension=".json"):
    """自動偵測資料夾中最新的 JSON 檔案"""
    files = glob.glob(os.path.join(folder_path, f"*{extension}"))
    return max(files, key=os.path.getmtime) if files else None


if __name__ == "__main__":
    # 記錄開始時間
    script_start_time = time.perf_counter()
    
    # 設定檔案路徑
    INPUT_FOLDER = "./temp_data/prompt1_json"
    OUTPUT_FOLDER = "./temp_data/prompt2_json"
    
    # 確保輸出資料夾存在
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # 2. 抓取最新檔案
    latest_path = get_latest_file(INPUT_FOLDER)

    if latest_path:
        # 3. 讀取內容以獲取動態命名資訊
        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 取得公司與年份 (移除空格以防檔名出錯)
            first_item = data[0] if isinstance(data, list) else data
            company = str(first_item.get("company", "Unknown")).replace(" ", "")
            year = str(first_item.get("year", "Unknown")).replace(" ", "")

            # 4. 精簡定義輸出路徑
            # 直接在呼叫函式時組合路徑與檔名
            output_file = f"{OUTPUT_FOLDER}/{year}_{company}_P2.json"

            # 5. 執行核心驗證邏輯
            process_json_file(latest_path, output_file)

        except Exception as e:
            print(f"❌ 解析檔案內容時發生錯誤: {e}")

        # (time-2) 計算總耗時
        total_duration = time.perf_counter() - script_start_time
        print(f"⏱️ 執行總耗時: {total_duration:.2f} 秒")    
