import json
import time
import os
from datetime import datetime
from gnews import GNews
from dateutil import parser as date_parser

# --- 1. 設定檔案路徑 ---
P1_JSON_PATH = '2024_1102_P1.json'
SASB_KEYWORD_PATH = 'sasb_keyword.json'
OUTPUT_DIR = './news_output/'

# --- 2. 股票代碼對照表 ---
# 根據實際需求擴充
stock_map = {
    "1102": "亞泥",
    "1101": "台泥",
    "2330": "台積電",
    "2317": "鴻海",
}

# --- 3. 讀取輸入檔案 ---
print("正在讀取輸入檔案...")

# 讀取 P1.json
with open(P1_JSON_PATH, 'r', encoding='utf-8') as f:
    p1_data_list = json.load(f)
print(f"✓ 已載入 {len(p1_data_list)} 筆 P1 資料")

# 讀取 SASB 關鍵字對照表
with open(SASB_KEYWORD_PATH, 'r', encoding='utf-8') as f:
    sasb_keywords_map = json.load(f)
print(f"✓ 已載入 {len(sasb_keywords_map)} 個 SASB 議題關鍵字")

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
    
    print(f"[{idx}/{len(p1_data_list)}] 查核: {company_name} - {topic} ({year_str})")
    
    # 設定 GNews 時間範圍
    try:
        target_year = int(year_str)
        # 搜索範圍限制在 f"{year}0101~{year}1231"
        google_news = GNews(language='zh-TW', country='TW', max_results=5)
        google_news.start_date = (target_year, 1, 1)
        google_news.end_date = (target_year, 12, 31)
        date_range = f"{target_year}0101~{target_year}1231"
        print(f"  📅 搜索範圍: {date_range}")
    except ValueError:
        print(f"  ⚠️  日期格式錯誤，跳過此筆")
        search_results["results"].append(result_item)
        continue
    
    # 查找對應的關鍵字
    keywords = None
    
    # 先嘗試完全匹配
    if topic in sasb_keywords_map:
        keywords = sasb_keywords_map[topic]
    else:
        # 嘗試模糊匹配（處理名稱差異）
        for key in sasb_keywords_map.keys():
            if topic in key or key in topic:
                keywords = sasb_keywords_map[key]
                print(f"  ℹ️  使用模糊匹配: '{topic}' -> '{key}'")
                break
    
    if keywords:
        # 組合搜尋字串
        keyword_str = " OR ".join(keywords)
        query = f'{company_name} ({keyword_str})'
        
        print(f"  🔍 搜尋: {query[:60]}...")
        
        try:
            # 執行搜尋
            news_results = google_news.get_news(query)
            
            if news_results:
                # 過濾：只保留目標年份內的新聞
                filtered_news = []
                filtered_out_count = 0
                
                for news in news_results:
                    published_date = news.get('published date', '')
                    
                    # 檢查日期是否在目標年份內
                    if is_date_in_year(published_date, target_year):
                        # 添加到總結果列表，包含流水號
                        all_news_articles.append({
                            "news_id": news_id_counter,
                            "sasb_topic": topic,
                            "title": news.get('title', ''),
                            "url": news.get('url', ''),
                            "published_date": published_date,
                            "publisher": news.get('publisher', {}).get('title', '') if isinstance(news.get('publisher'), dict) else ''
                        })
                        news_id_counter += 1
                        filtered_news.append(news)  # 用於計數
                    else:
                        filtered_out_count += 1
                
                if filtered_news:
                    print(f"  ✓ 找到 {len(news_results)} 則新聞，過濾後保留 {len(filtered_news)} 則（排除 {filtered_out_count} 則非{target_year}年新聞）")
                else:
                    print(f"  ℹ️  找到 {len(news_results)} 則新聞，但全部不在 {target_year} 年範圍內")
            else:
                print("  ℹ️  無相關新聞")
                
        except Exception as e:
            print(f"  ❌ 搜尋失敗: {str(e)}")
        
        # 避免請求太快被擋
        time.sleep(2)
        
    else:
        print(f"  ⚠️  警告: 議題 '{topic}' 未在關鍵字對照表中找到")
    
    print("-" * 60)

# --- 7. 儲存結果 ---
output_filename = os.path.join(OUTPUT_DIR, f'news_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

with open(output_filename, 'w', encoding='utf-8') as f:
    json.dump(all_news_articles, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print(f"✅ 查核完成！")
print(f"📁 結果已儲存至: {output_filename}")
print(f"📊 統計:")
print(f"   - 總查核筆數: {len(p1_data_list)}")
print(f"   - 新聞總數: {len(all_news_articles)}")
print("=" * 60)