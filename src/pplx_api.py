import json
import requests
import os
import sys
from dotenv import load_dotenv
from perplexity import Perplexity
import glob
import time
from urllib.parse import urlparse

load_dotenv()

# 導入集中配置
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import PATHS

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = 20

def is_official_site(url, company_name):
    """
    簡單判斷網址是否為公司官網
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    # 移除公司名稱中的常見後綴以便比對
    clean_name = company_name.lower().replace("股份有限公司", "").replace("corp", "").replace("inc", "").strip()
    
    # 判斷網域是否包含公司名稱關鍵字
    if clean_name in domain:
        return True
    return False

def verify_single_url(url):
    """驗證單一 URL 的有效性並提取標題"""
    try:
        if not url or not url.startswith('http'):
            return {"url": url, "is_valid": False, "page_title": None}
            
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


def search_with_perplexity(query, company_name):
    """使用 Perplexity 搜尋，並排除官網"""
    try:
        perplexity_client = Perplexity(api_key=os.environ.get("PERPLEXITY_API_KEY"))
        # 強化 Prompt：明確要求排除官方網站，尋找第三方新聞或報告
        prompt = (
            f"提供關於「{query}」的1個可靠第三方資訊來源網址，請務必排除「{company_name}」的官方網站或官方域名的網址，僅輸出JSON格式：{{\"urls\": [\"url1\"]}}"
        )
        
        response = perplexity_client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": prompt}]
        )
        
        usage = response.usage
        print(f"Perplexity API: Input={usage.prompt_tokens}, Output={usage.completion_tokens}, Total={usage.total_tokens}")

        content = response.choices[0].message.content
        clean_json = content.replace('```json', '').replace('```', '').strip()
        result = json.loads(clean_json)
        return result.get('urls', [])
    except Exception as e:
        print(f"Perplexity 失敗: {e}")
        return []

def find_alternative_url(company, year, evidence_summary, original_url):
    """尋找替代的有效第三方 URL"""
    search_query = f"{company} {year} ESG {evidence_summary[:50]}"
    print(f"  🔍 搜尋替代 URL (排除官網): {search_query}")

    pplx_urls = search_with_perplexity(search_query, company)
    for url in pplx_urls:
        # 檢查是否為官方網站
        if is_official_site(url, company):
            print(f"  ⚠️ 偵測到為官網，跳過: {url}")
            continue
            
        verification = verify_single_url(url)
        if verification["is_valid"]:
            print(f"  ✅ Perplexity 找到有效第三方 URL: {url}")
            return url
    
    return None # 若找不到則回傳 None

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
        input_folder = PATHS['P2_JSON']
        output_folder = PATHS['P3_JSON']
        os.makedirs(output_folder, exist_ok=True)
        
        input_file = os.path.join(input_folder, f'{year}_{company_code}_p2.json')
        output_file = os.path.join(output_folder, f'{year}_{company_code}_p3.json')
        
        # 2. 檢查輸入檔案是否存在
        if not os.path.exists(input_file):
            return {'success': False, 'message': f'輸入檔案不存在: {input_file}', 'error': 'Input file not found'}
        
        # 3. 檢查輸出檔案是否已存在
        if os.path.exists(output_file) and not force_regenerate:
            return {'success': True, 'message': '來源驗證結果已存在', 'output_path': output_file, 'skipped': True, 'statistics': {'execution_time': time.perf_counter() - start_time}}
        
        # 4. 讀取 P2 JSON
        print(f"📖 讀取檔案: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        processed_data = [] # 用於存儲有效的結果
        verified_count = 0
        updated_count = 0
        failed_count = 0
        perplexity_calls = 0
        
        print(f"\n開始驗證資料...\n")
        
        # 5. 逐筆驗證 URL
        for idx, item in enumerate(data, 1):
            url = item.get("external_evidence_url", "").strip()
            company = item.get("company", "")
            year_str = item.get("year", "")
            evidence = item.get("external_evidence", "")
            
            # --- 需求 1: 沒網址直接跳過 ---
            if not url:
                print(f"[{idx}] ⏭️ 項目無網址，直接跳過")
                continue

            print(f"[{idx}] 處理: {company} {year_str} - {item.get('esg_category')}")
            
            # 驗證原始 URL
            verification = verify_single_url(url)
            
            if verification["is_valid"]:
                print(f"  ✅ URL 有效")
                verified_count += 1
                item["is_verified"] = "True"
                processed_data.append(item)
            else:
                print(f"  ❌ URL 失效，尋找替代第三方來源...")
                perplexity_calls += 1
                new_url = find_alternative_url(company, year_str, evidence, url)
                
                if new_url:
                    item["external_evidence_url"] = new_url
                    item["is_verified"] = "True"
                    updated_count += 1
                    processed_data.append(item)
                    print(f"  🔄 已更新為第三方 URL")
                else:
                    failed_count += 1
                    print(f"  ⚠️ 無法找到替代來源，此項不產出")
            
        # 6. 寫入 P3 JSON (僅包含 processed_data)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        
        return {
            'success': True,
            'message': '來源驗證完成',
            'output_path': output_file,
            'statistics': {
                'processed_items': len(processed_data),
                'verified_count': verified_count,
                'updated_count': updated_count,
                'failed_count': failed_count,
                'execution_time': time.perf_counter() - start_time
            }
        }
    except Exception as e:
        return {'success': False, 'message': f'驗證失敗: {str(e)}', 'error': str(e)}

def process_json_file(input_file, output_file):
    """處理 JSON 檔案中的所有 URL (CLI 直接執行版本)"""
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    processed_data = []
    for item in data:
        url = item.get("external_evidence_url", "").strip()
        company = item.get("company", "")
        year = item.get("year", "")
        evidence = item.get("external_evidence", "")
        
        if not url:
            continue
            
        verification = verify_single_url(url)
        if verification["is_valid"]:
            item["is_verified"] = "True"
            processed_data.append(item)
        else:
            new_url = find_alternative_url(company, year, evidence, url)
            if new_url:
                item["external_evidence_url"] = new_url
                item["is_verified"] = "True"
                processed_data.append(item)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

def get_latest_file(folder_path, extension=".json"):
    files = glob.glob(os.path.join(folder_path, f"*{extension}"))
    return max(files, key=os.path.getmtime) if files else None

if __name__ == "__main__":
    # (time-1) 記錄程式開始的最早時間點
    script_start_time = time.perf_counter()

    # 1. 路徑設定
    INPUT_FOLDER = PATHS['P2_JSON']
    OUTPUT_FOLDER = PATHS['P3_JSON']
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # 2. 抓取最新檔案
    latest_path = get_latest_file(INPUT_FOLDER)
    if latest_path:
        # 3. 讀取內容以獲取動態命名資訊
        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 取得公司與年份 (移除空格以防檔名出錯)
            first_item = data[0] if isinstance(data, list) and data else {}
            company = str(first_item.get("company", "Unknown")).replace(" ", "")
            year = str(first_item.get("year", "Unknown")).replace(" ", "")

            # 4. 精簡定義輸出路徑
            # 直接在呼叫函式時組合路徑與檔名
            output_file = f"{OUTPUT_FOLDER}/{year}_{company}_p3.json"
            
            # 5. 執行核心驗證邏輯
            process_json_file(latest_path, output_file)
            print(f"⏱️ 執行總耗時: {time.perf_counter() - script_start_time:.2f} 秒")
        except Exception as e:
            print(f"❌ 錯誤: {e}")