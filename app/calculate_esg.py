import os
import json

# 載入 SASB 權重設定
def load_sasb_weights():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'static', 'data', 'SASB_weightMap.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
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
    :param esg_records: 資料庫撈出的詳細 list (dict)，欄位名稱已變更
    :return: dict 包含 e_score, s_score, g_score, total_score
    """
    
    scores = {
        'E': {'numerator': 0, 'denominator': 0},
        'S': {'numerator': 0, 'denominator': 0},
        'G': {'numerator': 0, 'denominator': 0},
        'Total': {'numerator': 0, 'denominator': 0}
    }

    for row in esg_records:
        # [Update] 欄位名稱對應 SQL_table_new.txt
        category = row['ESG_category'] # 舊: category
        topic = row['SASB_topic']      # 舊: sasb_topic
        
        # 1. 取得權重
        topic_info = SASB_WEIGHTS.get(topic, {})
        weight = topic_info.get(company_industry, 1) 
        
        # 2. 計算淨分數 S_net (Risk - Adjustment)
        # [Important] 資料庫中 risk_score 定義為 VARCHAR(3)，需轉型
        try:
            raw_risk = float(row['risk_score']) if row['risk_score'] else 0
        except ValueError:
            raw_risk = 0 # 若資料庫存了非數字字元，預設為 0
            
        # adjustment_score 定義為 DECIMAL，Python通常會自動轉為 Decimal 或 float
        adjustment = float(row['adjustment_score']) if row['adjustment_score'] else 0
        
        net_score = max(0, raw_risk - adjustment)
        
        # 3. 累加
        weighted_score = net_score * weight
        max_weighted_score = 4 * weight
        
        # 防呆：避免資料庫 category 欄位有大小寫或額外空白
        clean_cat = category.strip().upper() if category else 'E'
        
        if clean_cat in scores:
            scores[clean_cat]['numerator'] += weighted_score
            scores[clean_cat]['denominator'] += max_weighted_score
            
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
            final_results[key] = 0

    return final_results