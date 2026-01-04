from flask import Flask, render_template, request, jsonify, send_from_directory
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
    """
    conn = get_db_connection()
    companies_data = []
    
    try:
        with conn.cursor() as cursor:
            # --- [Update] 資料庫讀取段落 (取得所有公司) ---
            # 資料表名稱變更: companies -> company
            # 欄位對應: id -> ESG_id (或忽略), name -> company_name, stock_id -> company_code
            sql_companies = "SELECT * FROM company"
            cursor.execute(sql_companies)
            companies_basic = cursor.fetchall()
            
            for comp in companies_basic:
                # 取得關聯用的 Key
                stock_code = comp['company_code'] # 對應 company_report.company_id
                report_year = comp['Report_year'] # 對應 company_report.year
                industry = comp['industry']
                
                # --- [Update] 資料庫讀取段落 (取得該公司該年度所有 ESG 細項) ---
                # 資料表名稱變更: esg_details -> company_report
                # 我們撈出所有欄位，包含新增的 external_evidence, MSCI_flag 等，供前端顯示
                sql_details = """
                    SELECT ESG_category, SASB_topic, risk_score, adjustment_score, 
                           report_claim, page_number, greenwashing_factor,
                           external_evidence, external_evidence_url, 
                           consistency_status, MSCI_flag
                    FROM company_report 
                    WHERE company_id = %s AND year = %s
                """
                cursor.execute(sql_details, (stock_code, report_year))
                details = cursor.fetchall()
                
                # --- Python 運算段落 (呼叫計算引擎) ---
                # 計算邏輯不變，但 details 內的 key 變了，需由 calculate_esg.py 處理或在此轉換
                # 這裡我們維持直接傳入，讓 calculate_esg.py 去適應新的 key 名稱
                scores = calculate_esg_scores(industry, details)
                
                # 組合最終物件
                company_obj = {
                    'id': comp['ESG_id'],     # 使用新的 PK
                    'name': comp['company_name'],
                    'stockId': comp['company_code'],
                    'industry': comp['industry'],
                    'year': comp['Report_year'],
                    'url': comp['URL'],       # 新增: 報告連結
                    'greenwashingScore': scores['Total'], # 總風險分
                    'eScore': scores['E'],
                    'sScore': scores['S'],
                    'gScore': scores['G'],
                    'layer4Data': details     # 傳遞給前端做詳細列表顯示 (包含 Layer 4 和 Layer 5 所需資料)
                }
                companies_data.append(company_obj)
                
    finally:
        conn.close()

    return render_template('index.html', companies=companies_data)

# Serve word cloud JSON files
@app.route('/wordcloud/<filename>')
def serve_wordcloud(filename):
    return send_from_directory('word_cloud/wc_output', filename)

# 如果需要 API 格式 (Optional)
@app.route('/api/companies')
def api_companies():
    pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)