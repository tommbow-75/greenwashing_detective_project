"""
新聞爬蟲模組

提供從 P1 JSON 分析結果搜尋相關新聞的功能。

主要函數：
    search_news_for_report: 針對 ESG 報告搜尋相關新聞

使用範例：
    from news_search.crawler_news import search_news_for_report
    
    result = search_news_for_report(year=2024, company_code="1102")
    if result['success']:
        print(f"找到 {result['news_count']} 則新聞")
"""

import json
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from gnews import GNews
from dateutil import parser as date_parser

# === 模組常數 ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_P1_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "temp_data", "prompt1_json"))
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "news_output")
COMPANY_MAP_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "static", "data", "tw_listed_companies.json"))
SASB_KEYWORD_PATH = os.path.join(SCRIPT_DIR, "sasb_keyword.json")

# API 設定
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒
SEARCH_DELAY = 2  # 每次搜尋後延遲
MAX_RESULTS_PER_TOPIC = 10


# === 輔助函數 ===

def _load_company_map() -> Dict[str, str]:
    """
    載入上市公司代號對照表
    
    Returns:
        Dict[公司代號, 公司名稱]
    """
    try:
        with open(COMPANY_MAP_PATH, 'r', encoding='utf-8') as f:
            companies = json.load(f)
            stock_map = {}
            for company in companies:
                code = company.get('公司代號')
                name = company.get('公司簡稱', company.get('公司名稱', ''))
                if code:
                    stock_map[code] = name
            return stock_map
    except FileNotFoundError:
        print(f"⚠️ 找不到公司對照表: {COMPANY_MAP_PATH}")
        return {}
    except Exception as e:
        print(f"⚠️ 載入公司對照表失敗: {e}")
        return {}


def _load_sasb_keywords() -> Dict[str, List[str]]:
    """
    載入 SASB 議題關鍵字對照表
    
    Returns:
        Dict[SASB議題, 關鍵字列表]
    """
    try:
        with open(SASB_KEYWORD_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 找不到 SASB 關鍵字檔案: {SASB_KEYWORD_PATH}")
        return {}
    except Exception as e:
        print(f"⚠️ 載入 SASB 關鍵字失敗: {e}")
        return {}


def _get_keywords_from_sasb(sasb_topic: str, company_name: str, sasb_keywords: Dict) -> str:
    """
    從 SASB 關鍵字表生成搜尋關鍵字
    
    Args:
        sasb_topic: SASB 議題名稱
        company_name: 公司名稱
        sasb_keywords: SASB 關鍵字字典
    
    Returns:
        組合後的搜尋關鍵字
    """
    keywords = sasb_keywords.get(sasb_topic, [])
    if keywords:
        # 取前 3 個關鍵字
        selected_keywords = ' '.join(keywords[:3])
        return f"{company_name} {sasb_topic} {selected_keywords}"
    else:
        return f"{company_name} {sasb_topic}"


def _find_p1_json(year: int, company_code: str, p1_dir: str = DEFAULT_P1_DIR) -> Optional[str]:
    """
    尋找 P1 JSON 檔案
    
    Args:
        year: 年份
        company_code: 公司代碼
        p1_dir: P1 JSON 目錄
    
    Returns:
        P1 JSON 檔案路徑，若找不到則返回 None
    """
    # 嘗試標準檔名格式
    standard_name = f"{year}_{company_code}_p1.json"
    standard_path = os.path.join(p1_dir, standard_name)
    
    if os.path.exists(standard_path):
        return standard_path
    
    # 嘗試小寫 p1
    lowercase_name = f"{year}_{company_code}_p1.json"
    lowercase_path = os.path.join(p1_dir, lowercase_name)
    
    if os.path.exists(lowercase_path):
        return lowercase_path
    
    # 嘗試搜尋符合格式的檔案
    if os.path.exists(p1_dir):
        prefix = f"{year}_{company_code}"
        for filename in os.listdir(p1_dir):
            if filename.startswith(prefix) and filename.lower().endswith('.json'):
                return os.path.join(p1_dir, filename)
    
    return None


def _is_date_in_year(date_str: str, target_year: int) -> bool:
    """
    檢查新聞發布日期是否在目標年份內
    
    Args:
        date_str: 新聞發布日期字串
        target_year: 目標年份
    
    Returns:
        True 如果在目標年份內，否則 False
    """
    if not date_str:
        return False
    
    try:
        parsed_date = date_parser.parse(date_str)
        return parsed_date.year == target_year
    except Exception:
        return False


# === 主要函數 ===

def search_news_for_report(
    year: int,
    company_code: str,
    p1_json_path: Optional[str] = None,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    針對 ESG 報告搜尋相關新聞
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        p1_json_path: P1 JSON 路徑（選填，預設自動尋找）
        force_regenerate: 是否強制重新生成（預設 False）
    
    Returns:
        {
            'success': bool,              # 是否成功
            'output_file': str,           # 輸出檔案路徑
            'news_count': int,            # 新聞總數
            'processed_items': int,       # 處理的 P1 項目數
            'failed_items': int,          # 搜尋失敗的項目數
            'skipped': bool,              # 是否跳過生成
            'error': str                  # 錯誤訊息（可選）
        }
    """
    start_time = time.time()
    
    # === 1. 建立輸出目錄 ===
    if not os.path.exists(DEFAULT_OUTPUT_DIR):
        os.makedirs(DEFAULT_OUTPUT_DIR)
    
    # 輸出檔名（無時間戳）
    output_filename = os.path.join(DEFAULT_OUTPUT_DIR, f"{year}_{company_code}_news.json")
    
    # === 2. 檔案存在性檢查 ===
    if not force_regenerate and os.path.exists(output_filename):
        try:
            with open(output_filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            if isinstance(existing_data, list) and len(existing_data) > 0:
                return {
                    'success': True,
                    'output_file': output_filename,
                    'news_count': len(existing_data),
                    'processed_items': 0,
                    'failed_items': 0,
                    'skipped': True
                }
        except (json.JSONDecodeError, IOError):
            print(f"⚠️ 現有檔案格式錯誤，將重新生成")
    
    # === 3. 尋找 P1 JSON ===
    if p1_json_path is None:
        p1_json_path = _find_p1_json(year, company_code)
    
    if p1_json_path is None or not os.path.exists(p1_json_path):
        return {
            'success': False,
            'error': f'找不到 P1 JSON 檔案: {year}_{company_code}_p1.json'
        }
    
    # === 4. 載入資源 ===
    try:
        with open(p1_json_path, 'r', encoding='utf-8') as f:
            p1_data_list = json.load(f)
    except Exception as e:
        return {
            'success': False,
            'error': f'讀取 P1 JSON 失敗: {str(e)}'
        }
    
    stock_map = _load_company_map()
    sasb_keywords = _load_sasb_keywords()
    
    # === 5. 執行新聞搜尋 ===
    all_news_articles = []
    news_id_counter = 1
    processed_items = 0
    failed_items = 0
    failure_details = []
    
    print(f"\n開始執行新聞搜尋，共 {len(p1_data_list)} 筆資料...")
    print("=" * 60)
    
    for idx, item in enumerate(p1_data_list, 1):
        # 取得基本資訊
        company_name = item.get("company", "")  # 現在直接是公司名稱
        stock_code = item.get("company_id", company_code)  # 從 company_id 取得代碼
        topic = item.get("sasb_topic", "")
        year_str = item.get("year", str(year))
        
        print(f"[{idx}/{len(p1_data_list)}] 查核: {company_name} ({stock_code}) - {topic}")
        
        processed_items += 1
        
        # === 關鍵字三層級 Fallback ===
        # 層級 1: 優先使用 P1 提供的 key_word
        key_word = item.get("key_word", "")
        
        # 層級 2: 從 SASB 關鍵字表生成
        if not key_word and topic:
            key_word = _get_keywords_from_sasb(topic, company_name, sasb_keywords)
            print(f"  🔧 使用 SASB 關鍵字生成: {key_word}")
        
        # 層級 3: 基本組合
        if not key_word:
            key_word = f"{company_name} {topic}"
            print(f"  🔧 使用基本組合: {key_word}")
        
        # 設定 GNews 時間範圍
        try:
            target_year = int(year_str)
            google_news = GNews(language='zh-TW', country='TW', max_results=MAX_RESULTS_PER_TOPIC)
            google_news.start_date = (target_year, 1, 1)
            google_news.end_date = (target_year, 12, 31)
            print(f"  📅 搜索範圍: {target_year}/01/01 ~ {target_year}/12/31")
        except ValueError:
            print(f"  ⚠️ 日期格式錯誤，跳過此筆")
            failed_items += 1
            failure_details.append({'topic': topic, 'reason': '日期格式錯誤'})
            continue
        
        # === 搜尋策略（三階段） ===
        news_results = None
        final_query = key_word
        
        try:
            # 策略 1: 使用完整關鍵字
            print(f"  🔍 搜尋策略1: {key_word}")
            for attempt in range(MAX_RETRIES):
                try:
                    news_results = google_news.get_news(key_word)
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f"  ⚠️ 搜尋失敗，{RETRY_DELAY}秒後重試...")
                        time.sleep(RETRY_DELAY)
                    else:
                        raise e
            
            # 策略 2: 簡化關鍵字（取前3個詞）
            if not news_results or len(news_results) < 3:
                key_words_list = key_word.split()
                if len(key_words_list) >= 3:
                    query2 = ' '.join(key_words_list[:3])
                    print(f"  🔍 搜尋策略2: {query2}")
                    news_results2 = google_news.get_news(query2)
                    if news_results2 and len(news_results2) > len(news_results or []):
                        news_results = news_results2
                        final_query = query2
            
            # 策略 3: 公司名稱 + 主題
            if not news_results or len(news_results) < 2:
                query3 = f"{company_name} {topic}"
                print(f"  🔍 搜尋策略3: {query3}")
                news_results3 = google_news.get_news(query3)
                if news_results3 and len(news_results3) > len(news_results or []):
                    news_results = news_results3
                    final_query = query3
            
            # 過濾新聞
            if news_results:
                print(f"  📰 共找到 {len(news_results)} 則新聞，開始過濾...")
                filtered_count = 0
                filtered_out_count = 0
                
                for news in news_results:
                    published_date = news.get('published date', '')
                    
                    if _is_date_in_year(published_date, target_year):
                        all_news_articles.append({
                            "news_id": news_id_counter,
                            "stock_code": stock_code,
                            "company_name": company_name,
                            "sasb_topic": topic,
                            "search_query": final_query,
                            "title": news.get('title', ''),
                            "url": news.get('url', ''),
                            "published_date": published_date,
                            "publisher": news.get('publisher', {}).get('title', '') if isinstance(news.get('publisher'), dict) else ''
                        })
                        news_id_counter += 1
                        filtered_count += 1
                    else:
                        filtered_out_count += 1
                
                if filtered_count > 0:
                    print(f"  ✓ 保留 {filtered_count} 則 {target_year} 年新聞（排除 {filtered_out_count} 則）")
                else:
                    print(f"  ⚠️ 找到 {len(news_results)} 則新聞，但全部不在 {target_year} 年範圍內")
            else:
                print(f"  ❌ 無相關新聞")
                
        except Exception as e:
            print(f"  ❌ 搜尋失敗: {str(e)}")
            failed_items += 1
            failure_details.append({'topic': topic, 'reason': str(e)})
        
        # 避免請求太快
        time.sleep(SEARCH_DELAY)
        print("-" * 60)
    
    # === 6. 儲存結果 ===
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(all_news_articles, f, ensure_ascii=False, indent=2)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print(f"✅ 新聞搜尋完成！")
        print(f"📁 結果已儲存至: {output_filename}")
        print(f"📊 統計:")
        print(f"   - 處理項目數: {processed_items}")
        print(f"   - 成功項目數: {processed_items - failed_items}")
        print(f"   - 失敗項目數: {failed_items}")
        print(f"   - 新聞總數: {len(all_news_articles)}")
        print(f"   - 執行時間: {elapsed_time:.1f} 秒")
        print("=" * 60)
        
        return {
            'success': True,
            'output_file': output_filename,
            'news_count': len(all_news_articles),
            'processed_items': processed_items,
            'failed_items': failed_items,
            'skipped': False,
            'failure_details': failure_details if failure_details else None
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'儲存檔案失敗: {str(e)}'
        }


# === 命令列執行 ===

def main():
    """命令列執行的主函數"""
    print("=== ESG 報告書新聞爬蟲 ===\n")
    
    year = input("請輸入年份 (預設 2024): ").strip() or "2024"
    company_code = input("請輸入公司代碼 (預設 1102): ").strip() or "1102"
    force = input("是否強制重新生成？(y/N): ").strip().lower() == 'y'
    
    result = search_news_for_report(
        year=int(year),
        company_code=company_code,
        force_regenerate=force
    )
    
    if result['success']:
        if result.get('skipped'):
            print(f"\nℹ️ 新聞資料已存在，跳過生成")
            print(f"📁 檔案位置: {result['output_file']}")
            print(f"📊 新聞數量: {result['news_count']}")
        else:
            print(f"\n✅ 執行成功！")
    else:
        print(f"\n❌ 執行失敗: {result.get('error')}")


if __name__ == "__main__":
    main()