from flask import Flask, render_template, request, jsonify
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