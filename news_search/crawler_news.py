import json
import time
import os
from datetime import datetime
from gnews import GNews
from dateutil import parser as date_parser

# --- 1. 設定檔案路徑 ---
P1_JSON_PATH = './temp_data/prompt1_json/2024_1102_p1.json'  # json1要有keyword
OUTPUT_DIR = './news_search/news_output/'

# --- 2. 讀取上市公司對照表 ---
print("正在讀取上市公司代號對照表...")
stock_map = {}
try:
    with open('./static/data/tw_listed_companies.json', 'r', encoding='utf-8') as f:
        companies = json.load(f)
        for company in companies:
            code = company.get('公司代號')
            name = company.get('公司簡稱', company.get('公司名稱', ''))
            if code:
                stock_map[code] = name
    print(f"✓ 已載入 {len(stock_map)} 家上市公司對照資料")
except FileNotFoundError:
    print("❌ 錯誤：找不到上市公司對照表檔案 './static/data/tw_listed_companies.json'")
    print("請確認檔案路徑是否正確。")
    exit(1)
except Exception as e:
    print(f"❌ 讀取對照表失敗: {e}")
    exit(1)

# --- 3. 讀取輸入檔案 ---
print("正在讀取輸入檔案...")

# 讀取 P1 keyword JSON
with open(P1_JSON_PATH, 'r', encoding='utf-8') as f:
    p1_data_list = json.load(f)
print(f"✓ 已載入 {len(p1_data_list)} 筆 P1 關鍵字資料")

# --- 4. 建立輸出目錄 ---
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"✓ 已建立輸出目錄: {OUTPUT_DIR}")

# --- 5. 日期驗證函數 ---
def is_date_in_year(date_str, target_year):
    """
    檢查新聞發布日期是否在目標年份內
    :param date_str: 新聞發布日期字串
    :param target_year: 目標年份 (int)
    :return: True 如果在目標年份內，否則 False
    """
    if not date_str:
        return False
    
    try:
        # 解析日期字串
        parsed_date = date_parser.parse(date_str)
        # 檢查年份是否匹配
        return parsed_date.year == target_year
    except Exception as e:
        # 如果無法解析日期，保守起見排除該新聞
        print(f"  ⚠️  無法解析日期: {date_str}")
        return False

# --- 6. 初始化結果容器 ---
# 簡化輸出格式：只保留必要欄位
all_news_articles = []
news_id_counter = 1

# --- 6. 執行搜尋主程序 ---
print(f"\n開始執行外部查核，共 {len(p1_data_list)} 筆資料...\n")
print("=" * 60)

for idx, item in enumerate(p1_data_list, 1):
    # 取得基本資訊
    stock_code = item.get("company")
    company_name = stock_map.get(stock_code, stock_code)
    topic = item.get("sasb_topic")
    year_str = item.get("year")
    esg_category = item.get("esg_category")
    risk_score = item.get("risk_score")
    report_claim = item.get("report_claim", "")
    
    print(f"[{idx}/{len(p1_data_list)}] 查核: {company_name} ({stock_code}) - {topic} ({year_str})")
    
    # 設定 GNews 時間範圍
    try:
        target_year = int(year_str)
        # 設定搜索結果數量
        google_news = GNews(language='zh-TW', country='TW', max_results=10)
        google_news.start_date = (target_year, 1, 1)
        google_news.end_date = (target_year, 12, 31)
        date_range = f"{target_year}0101~{target_year}1231"
        print(f"  📅 搜索範圍: {date_range}")
    except ValueError:
        print(f"  ⚠️  日期格式錯誤，跳過此筆")
        continue
    
    # 取得關鍵字
    key_word = item.get("key_word", "")
    
    if key_word:
        # === 搜尋策略（keyword已包含公司名稱） ===
        # 策略1: 使用完整關鍵字（已含公司名稱）
        query = key_word
        
        print(f"  🔍 搜尋策略1: {query}")
        
        try:
            # 執行搜尋策略1
            news_results = google_news.get_news(query)
            
            # 如果結果太少，嘗試策略2：簡化關鍵字（取前3個詞）
            if not news_results or len(news_results) < 3:
                key_words_list = key_word.split()
                if len(key_words_list) >= 3:
                    # 取前面較重要的關鍵字
                    query2 = ' '.join(key_words_list[:3])
                    print(f"  🔍 搜尋策略2: {query2}")
                    news_results2 = google_news.get_news(query2)
                    if news_results2 and len(news_results2) > len(news_results or []):
                        news_results = news_results2
                        query = query2
            
            # 如果還是沒有，嘗試策略3：公司名稱 + 主題
            if not news_results or len(news_results) < 2:
                query3 = f'{company_name} {topic}'
                print(f"  🔍 搜尋策略3: {query3}")
                news_results3 = google_news.get_news(query3)
                if news_results3 and len(news_results3) > len(news_results or []):
                    news_results = news_results3
                    query = query3
            
            if news_results:
                print(f"  📰 共找到 {len(news_results)} 則新聞，開始過濾...")
                # 過濾：只保留目標年份內的新聞
                filtered_news = []
                filtered_out_count = 0
                
                for news in news_results:
                    published_date = news.get('published date', '')
                    
                    # 檢查日期是否在目標年份內
                    if is_date_in_year(published_date, target_year):
                        # 添加到總結果列表，包含流水號和完整資訊
                        all_news_articles.append({
                            "news_id": news_id_counter,
                            "stock_code": stock_code,
                            "company_name": company_name,
                            "sasb_topic": topic,
                            "search_query": query,
                            "title": news.get('title', ''),
                            "url": news.get('url', ''),
                            "published_date": published_date,
                            "publisher": news.get('publisher', {}).get('title', '') if isinstance(news.get('publisher'), dict) else '',
                        })
                        news_id_counter += 1
                        filtered_news.append(news)  # 用於計數
                    else:
                        filtered_out_count += 1
                
                if filtered_news:
                    print(f"  ✓ 過濾後保留 {len(filtered_news)} 則 {target_year} 年新聞（排除 {filtered_out_count} 則）")
                else:
                    print(f"  ⚠️  找到 {len(news_results)} 則新聞，但全部不在 {target_year} 年範圍內")
            else:
                print("  ❌ 無相關新聞")
                
        except Exception as e:
            print(f"  ❌ 搜尋失敗: {str(e)}")
            import traceback
            print(f"  詳細錯誤: {traceback.format_exc()}")
        
        # 避免請求太快被擋
        time.sleep(2)
        
    else:
        print(f"  ⚠️  警告: 此筆資料未包含 key_word 欄位")
    
    print("-" * 60)

# --- 7. 儲存結果 ---
output_filename = os.path.join(OUTPUT_DIR, f'{year}_{stock_code}_news_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

with open(output_filename, 'w', encoding='utf-8') as f:
    json.dump(all_news_articles, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print(f"✅ 查核完成！")
print(f"📁 結果已儲存至: {output_filename}")
print(f"📊 統計:")
print(f"   - 總查核筆數: {len(p1_data_list)}")
print(f"   - 新聞總數: {len(all_news_articles)}")
print("=" * 60)