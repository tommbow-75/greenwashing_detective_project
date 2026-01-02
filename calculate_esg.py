import os
import json

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