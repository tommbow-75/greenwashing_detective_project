import json
import requests
import os
from dotenv import load_dotenv
from perplexity import Perplexity
import glob
import time

load_dotenv()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = 20

def verify_single_url(url):
    """驗證單一 URL 的有效性並提取標題"""
    try:
        url = url.strip().strip('"').strip("'")
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        
        if response.status_code in [200, 403]:
            text = response.text
            title_start = text.find('<title>') + 7
            title_end = text.find('</title>', title_start)
            page_title = text[title_start:title_end].strip() if title_start > 6 else "ESG Evidence"
            
            return {
                "url": url,
                "is_valid": True,
                "page_title": page_title,
                "status_code": response.status_code
            }
    except Exception as e:
        print(f"  ❌ 驗證錯誤 ({type(e).__name__}): {url}")
    return {"url": url, "is_valid": False, "page_title": None}


def search_with_perplexity(query):
    """使用 Perplexity 搜尋"""
    try:
        perplexity_client = Perplexity(api_key=os.environ.get("PERPLEXITY_API_KEY"))
        prompt = f"提供關於「{query}」的1個可靠資訊來源網址。僅輸出JSON格式：{{\"urls\": [\"url1\"]}}"
        
        response = perplexity_client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": prompt}]
        )
        
        usage = response.usage  # Access prompt_tokens, completion_tokens, total_tokens
        print(f"Perplexity API: Input={usage.prompt_tokens}, Output={usage.completion_tokens}, Total={usage.total_tokens}")

        content = response.choices[0].message.content
        clean_json = content.replace('```json', '').replace('```', '').strip()
        result = json.loads(clean_json)
        return result.get('urls', [])
    except Exception as e:
        print(f"Perplexity 失敗: {e}")
        return []

def find_alternative_url(company, year, evidence_summary, original_url):
    """尋找替代的有效 URL"""
    # 構建搜尋關鍵字
    search_query = f"{company} {year} ESG {evidence_summary[:50]}"
    
    print(f"  🔍 搜尋替代 URL: {search_query}")


    # 備援：Perplexity搜尋新聞
    pplx_urls = search_with_perplexity(search_query)
    for url in pplx_urls:
        verification = verify_single_url(url)
        if verification["is_valid"]:
            print(f"  ✅ Perplexity 找到有效 URL: {url}")
            return url
    
    print(f"  ⚠️ 無法找到替代 URL，保留原網址")
    return original_url

def verify_evidence_sources(year, company_code, force_regenerate=False):
    """
    驗證 ESG 分析外部證據來源的可靠度
    
    這是 T5 整合的模組化接口函數，用於 app.py Step 6
    
    參數:
        year (int): 報告年度
        company_code (str): 公司代碼
        force_regenerate (bool): 是否強制重新驗證，預設 False
    
    返回:
        dict: {
            'success': bool,
            'message': str,
            'output_path': str,
            'skipped': bool,
            'statistics': {
                'processed_items': int,
                'verified_count': int,
                'updated_count': int,
                'failed_count': int,
                'perplexity_calls': int,
                'execution_time': float
            },
            'error': str  # 若失敗
        }
    """
    start_time = time.perf_counter()
    
    try:
        # 1. 構建檔案路徑
        input_folder = "./temp_data/prompt2_json"
        output_folder = "./temp_data/prompt3_json"
        os.makedirs(output_folder, exist_ok=True)
        
        input_file = f"{input_folder}/{year}_{company_code}_p2.json"
        output_file = f"{output_folder}/{year}_{company_code}_p3.json"
        
        # 2. 檢查輸入檔案是否存在
        if not os.path.exists(input_file):
            return {
                'success': False,
                'message': f'輸入檔案不存在: {input_file}',
                'error': 'Input file not found'
            }
        
        # 3. 檢查輸出檔案是否已存在
        if os.path.exists(output_file) and not force_regenerate:
            execution_time = time.perf_counter() - start_time
            return {
                'success': True,
                'message': '來源驗證結果已存在',
                'output_path': output_file,
                'skipped': True,
                'statistics': {
                    'execution_time': execution_time
                }
            }
        
        # 4. 讀取 P2 JSON
        print(f"📖 讀取檔案: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total = len(data)
        verified_count = 0
        updated_count = 0
        failed_count = 0
        perplexity_calls = 0
        
        print(f"\n開始驗證 {total} 筆資料...\n")
        
        # 5. 逐筆驗證 URL
        for idx, item in enumerate(data, 1):
            url = item.get("external_evidence_url", "")
            company = item.get("company", "")
            year_str = item.get("year", "")
            evidence = item.get("external_evidence", "")
            
            print(f"[{idx}/{total}] 處理: {company} {year_str} - {item.get('esg_category')}")
            print(f"  原始 URL: {url}")
            
            # 驗證原始 URL
            verification = verify_single_url(url)
            
            if verification["is_valid"]:
                print(f"  ✅ URL 有效 (狀態碼: {verification['status_code']})")
                verified_count += 1
                item["is_verified"] = "True"
            else:
                print(f"  ❌ URL 失效，開始尋找替代...")
                perplexity_calls += 1
                new_url = find_alternative_url(company, year_str, evidence, url)
                
                if new_url != url:
                    item["external_evidence_url"] = new_url
                    item["is_verified"] = "True"
                    updated_count += 1
                    print(f"  🔄 已更新為新 URL")
                else:
                    item["is_verified"] = "Failed"
                    failed_count += 1
            
            print()
        
        # 6. 寫入 P3 JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        execution_time = time.perf_counter() - start_time
        
        # 7. 返回結果
        print(f"✅ 處理完成！")
        print(f"📊 統計結果:")
        print(f"  - 總共處理: {total} 筆")
        print(f"  - 有效 URL: {verified_count} 筆")
        print(f"  - 已更新 URL: {updated_count} 筆")
        print(f"  - 失敗: {failed_count} 筆")
        print(f"📁 輸出檔案: {output_file}")
        
        return {
            'success': True,
            'message': '來源驗證完成',
            'output_path': output_file,
            'skipped': False,
            'statistics': {
                'processed_items': total,
                'verified_count': verified_count,
                'updated_count': updated_count,
                'failed_count': failed_count,
                'perplexity_calls': perplexity_calls,
                'execution_time': execution_time
            }
        }
    
    except Exception as e:
        execution_time = time.perf_counter() - start_time
        error_msg = str(e)
        print(f"❌ 驗證過程發生錯誤: {error_msg}")
        
        return {
            'success': False,
            'message': f'驗證失敗: {error_msg}',
            'error': error_msg,
            'statistics': {
                'execution_time': execution_time
            }
        }

def process_json_file(input_file, output_file):
    """處理 JSON 檔案中的所有 URL"""
    print(f"📖 讀取檔案: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total = len(data)
    verified_count = 0
    updated_count = 0
    
    print(f"\n開始驗證 {total} 筆資料...\n")
    
    for idx, item in enumerate(data, 1):
        url = item.get("external_evidence_url", "")
        company = item.get("company", "")
        year = item.get("year", "")
        evidence = item.get("external_evidence", "")
        
        print(f"[{idx}/{total}] 處理: {company} {year} - {item.get('esg_category')}")
        print(f"  原始 URL: {url}")
        
        # 驗證原始 URL
        verification = verify_single_url(url)
        
        if verification["is_valid"]:
            print(f"  ✅ URL 有效 (狀態碼: {verification['status_code']})")
            verified_count += 1
            item["is_verified"] = "True"
        else:
            print(f"  ❌ URL 失效，開始尋找替代...")
            new_url = find_alternative_url(company, year, evidence, url)
            
            if new_url != url:
                item["external_evidence_url"] = new_url
                item["is_verified"] = "True"
                updated_count += 1
                print(f" 🔄 已更新為新 URL")
            else:
                item["is_verified"] = "Failed"
            
        print()
    
    
    print(f"✅ 處理完成！")
    print(f"📊 統計結果:")
    print(f"  - 總共處理: {total} 筆")
    print(f"  - 有效 URL: {verified_count} 筆")
    print(f"  - 已更新 URL: {updated_count} 筆")
    print(f"  - 失敗: {total - verified_count - updated_count} 筆")
    print(f"📁 輸出檔案: {output_file}")

def get_latest_file(folder_path, extension=".json"):
    """自動偵測資料夾中最新的 JSON 檔案"""
    files = glob.glob(os.path.join(folder_path, f"*{extension}"))
    return max(files, key=os.path.getmtime) if files else None

if __name__ == "__main__":
    # (time-1) 記錄程式開始的最早時間點
    script_start_time = time.perf_counter()

    # 1. 路徑設定
    INPUT_FOLDER = "./temp_data/prompt2_json"
    OUTPUT_FOLDER = "./temp_data/prompt3_json"
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
            output_file = f"{OUTPUT_FOLDER}/{year}_{company}_p3.json"

            # 5. 執行核心驗證邏輯
            process_json_file(latest_path, output_file)

        except Exception as e:
            print(f"❌ 解析檔案內容時發生錯誤: {e}")

        # (time-2) 計算總耗時
        total_duration = time.perf_counter() - script_start_time
        print(f"⏱️ 執行總耗時: {total_duration:.2f} 秒")    
