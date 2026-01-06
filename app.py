from flask import Flask, render_template, request, jsonify
import requests
import pymysql
from pymysql.cursors import DictCursor
import os
import json
from dotenv import load_dotenv
from app.calculate_esg import calculate_esg_scores

load_dotenv()

# ==============Flask 部分========================
app = Flask(__name__)

# --- 資料庫連線設定 ---
# 使用環境變數，請參考 .env.example，然後在專案根目錄建立 .env
# 目前用於測試的SQL table 參考 SQL_table_test.txt
def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT')),
        user=os.getenv('DB_USER'), 
        password=os.getenv('DB_PASSWORD'), 
        db=os.getenv('DB_NAME'), 
        charset='utf8mb4',
        cursorclass=DictCursor
    )

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = 20

def verify_single_url(url):
    """驗證單一 URL 的有效性並提取標題"""
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
    return {"url": url, "is_valid": False, "page_title": None}

def verify_urls_batch(urls):
    """批次驗證並篩選有效 URL"""
    valid_list = []
    for url in urls:
        if not url: continue

        try:
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code in [200, 403]:
                valid_list.append({"url": url, "title": "Verified"})
            else:
                print(f"  ❌ 網址失效 ({res.status_code}): {url}")
        except Exception as e:
            print(f"  ❌ 請求錯誤 ({type(e).__name__}): {url}")
    return valid_list

@app.route('/')
def index():
    """
    主頁路由：渲染儀表板首頁
    這裡僅回傳 HTML 結構，資料透過 API 非同步加載或直接 Jinja2 渲染
    本範例採用：後端算出所有資料 -> Jinja2 渲染到 HTML (Server-Side Rendering)
    """
    conn = get_db_connection()
    companies_data = []
    
    try:
        with conn.cursor() as cursor:
            # --- 資料庫讀取段落 (取得所有公司) ---
            sql_companies = "SELECT * FROM companies"
            cursor.execute(sql_companies)
            companies_basic = cursor.fetchall()
            
            for comp in companies_basic:
                comp_id = comp['id']
                industry = comp['industry']
                
                # --- 資料庫讀取段落 (取得該公司所有 ESG 細項) ---
                sql_details = """
                    SELECT category, sasb_topic, risk_score, adjustment_score, 
                           report_claim, page_number
                    FROM esg_details 
                    WHERE company_id = %s
                """
                cursor.execute(sql_details, (comp_id,))
                details = cursor.fetchall()
                
                # --- Python 運算段落 (呼叫計算引擎) ---
                scores = calculate_esg_scores(industry, details)
                
                # 組合最終物件
                company_obj = {
                    'id': comp['id'],
                    'name': comp['name'],
                    'stockId': comp['stock_id'],
                    'industry': comp['industry'],
                    'year': comp['year'],
                    'greenwashingScore': scores['Total'], # 總風險分
                    'eScore': scores['E'],
                    'sScore': scores['S'],
                    'gScore': scores['G'],
                    'layer4Data': details # 傳遞給前端做詳細列表顯示
                }
                companies_data.append(company_obj)
                
    finally:
        conn.close()

    return render_template('index.html', companies=companies_data)

# 如果需要 API 格式 (Optional)
@app.route('/api/companies')
def api_companies():
    # ... (同上邏輯，只是 return jsonify(companies_data))
    pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)