import json
import requests
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from perplexity import Perplexity

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
        prompt = f"提供關於「{query}」的2個可靠資訊來源網址。僅輸出JSON格式：{{\"urls\": [\"url1\", \"url2\"]}}"
        
        response = perplexity_client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": prompt}]
        )
        
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
            item["url_verification_status"] = "valid"
            item["url_verification_date"] = "2026-01-06"
        else:
            print(f"  ❌ URL 失效，開始尋找替代...")
            new_url = find_alternative_url(company, year, evidence, url)
            
            if new_url != url:
                item["external_evidence_url"] = new_url
                item["url_verification_status"] = "updated"
                item["original_url"] = url
                updated_count += 1
                print(f"  🔄 已更新為新 URL")
            else:
                item["url_verification_status"] = "failed"
            
            item["url_verification_date"] = "2026-01-06"
        
        print()
    
    # 儲存結果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 處理完成！")
    print(f"📊 統計結果:")
    print(f"  - 總共處理: {total} 筆")
    print(f"  - 有效 URL: {verified_count} 筆")
    print(f"  - 已更新 URL: {updated_count} 筆")
    print(f"  - 失敗: {total - verified_count - updated_count} 筆")
    print(f"📁 輸出檔案: {output_file}")

if __name__ == "__main__":
    input_file = "1229亞泥P2_test1.json"
    output_file = "1229亞泥P2_test1_verified.json"
    
    # 執行驗證與更新
    process_json_file(input_file, output_file)
