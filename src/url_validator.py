"""
URL 驗證模組
提供單一 URL 和批次 URL 的驗證功能
"""

import requests
from typing import Optional


# === 常數設定 ===
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = 20


def verify_single_url(url: str) -> dict:
    """
    驗證單一 URL 的有效性並提取標題
    
    Args:
        url: 要驗證的 URL
        
    Returns:
        dict: {
            'url': str,
            'is_valid': bool,
            'page_title': str or None,
            'status_code': int or None
        }
    """
    try:
        # 簡單清理 URL 可能帶有的引號或空白
        url = url.strip().strip('"').strip("'")
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        
        if response.status_code in [200, 403]:
            text = response.text
            title_start = text.find('<title>') + 7
            title_end = text.find('</title>', title_start)
            page_title = text[title_start:title_end].strip() if title_start > 6 else "ESG News Link"
            
            return {
                "url": url,
                "is_valid": True,
                "page_title": page_title,
                "status_code": response.status_code
            }
    except Exception:
        pass
    
    return {"url": url, "is_valid": False, "page_title": None, "status_code": None}


def verify_urls_batch(urls: list[str]) -> list[dict]:
    """
    批次驗證並篩選有效 URL
    
    Args:
        urls: URL 列表
        
    Returns:
        list: 有效 URL 的列表，每個元素為 {'url': str, 'title': str}
    """
    valid_list = []
    
    for url in urls:
        if not url:
            continue
            
        try:
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code in [200, 403]:
                valid_list.append({"url": url, "title": "Verified"})
            else:
                print(f"  ❌ 網址失效 ({res.status_code}): {url}")
        except Exception as e:
            print(f"  ❌ 請求錯誤 ({type(e).__name__}): {url}")
    
    return valid_list


if __name__ == '__main__':
    # 測試用範例
    print("=== URL 驗證模組測試 ===\n")
    
    test_url = "https://www.google.com"
    print(f"測試單一 URL: {test_url}")
    result = verify_single_url(test_url)
    print(f"結果: {result}")
