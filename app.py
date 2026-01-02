from flask import Flask, render_template, request, jsonify
import pymysql
from pymysql.cursors import DictCursor
import os
import json
from dotenv import load_dotenv

load_dotenv()

#===================ESG運算邏輯區===================
# 載入 SASB 權重設定
# 確保 JSON 檔案位於專案根目錄
def load_sasb_weights():
    json_path = os.path.join(os.path.dirname(__file__), 'static\data\SASB_weightMap.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 轉換為更容易查詢的字典結構: weights[topic][industry] = weight
    weights = {}
    for item in data:
        topic = item.get('議題')
        if topic:
            weights[topic] = item
    return weights

SASB_WEIGHTS = load_sasb_weights()

def calculate_esg_scores(company_industry, esg_records):
    """
    計算 E, S, G 分數以及總風險分數
    :param company_industry: 公司產業別 (字串)
    :param esg_records: 資料庫撈出的詳細 list (dict)
    :return: dict 包含 e_score, s_score, g_score, total_score
    """
    
    # 初始化累加器
    scores = {
        'E': {'numerator': 0, 'denominator': 0},
        'S': {'numerator': 0, 'denominator': 0},
        'G': {'numerator': 0, 'denominator': 0},
        'Total': {'numerator': 0, 'denominator': 0}
    }

    # --- Python 運算段落 ---
    for row in esg_records:
        category = row['category'] # E, S, or G
        topic = row['sasb_topic']
        
        # 1. 取得權重 W (如果 JSON 沒定義該產業，預設為 1)
        # 注意：SASB JSON 鍵值可能與資料庫不完全一致，需確保資料一致性
        topic_info = SASB_WEIGHTS.get(topic, {})
        weight = topic_info.get(company_industry, 1) 
        
        # 2. 計算淨分數 S_net (Risk - Adjustment)
        # 確保分數不低於 0 (視業務邏輯而定，這裡設為 0)
        raw_risk = row['risk_score']
        adjustment = row['adjustment_score']
        net_score = max(0, raw_risk - adjustment)
        
        # 3. 累加分子與分母
        # 分子 += S_net * W
        weighted_score = net_score * weight
        # 分母 += 4 * W (滿分基準)
        max_weighted_score = 4 * weight
        
        # 寫入分項
        if category in scores:
            scores[category]['numerator'] += weighted_score
            scores[category]['denominator'] += max_weighted_score
            
        # 寫入總分
        scores['Total']['numerator'] += weighted_score
        scores['Total']['denominator'] += max_weighted_score

    # 4. 計算最終百分比
    final_results = {}
    for key in ['E', 'S', 'G', 'Total']:
        num = scores[key]['numerator']
        den = scores[key]['denominator']
        if den > 0:
            final_results[key] = round((num / den) * 100, 1)
        else:
            final_results[key] = 0 # 避免除以零，若無資料則為 0

    return final_results

#===============

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