"""
ESG 分析系統 - Flask 主應用程式

職責：
- Flask 應用程式初始化
- URL 路由定義與請求處理
- 流程控制與模組協調

業務邏輯已抽離至 src/ 目錄下的各模組
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

from config import PATHS
from src.db_service import get_db_connection, query_company_data, insert_company_basic, update_analysis_status
from src.calculate_esg import calculate_esg_scores
from src.response_builder import (
    build_company_response,
    build_processing_response,
    build_validation_needed_response,
    build_not_found_response,
    build_error_response,
    build_progress_response
)
from src.analysis_pipeline import run_full_analysis

load_dotenv()

# ==============Flask 應用程式========================
app = Flask(__name__)


@app.route('/')
def index():
    """
    主頁路由：渲染儀表板首頁
    """
    companies_data = []
    
    try:
        with get_db_connection() as conn:
            # 強制同步資料庫狀態
            conn.commit()
            with conn.cursor() as cursor:
                # 取得所有公司
                cursor.execute("SELECT * FROM company")
                companies_basic = cursor.fetchall()
                
                for comp in companies_basic:
                    stock_code = comp['company_code']
                    report_year = comp['Report_year']
                    industry = comp['industry']
                    
                    # 取得該公司該年度所有 ESG 細項
                    sql_details = """
                        SELECT ESG_category, SASB_topic, risk_score, adjustment_score, 
                               report_claim, page_number, greenwashing_factor,
                               external_evidence, external_evidence_url, 
                               consistency_status, MSCI_flag, is_verified
                        FROM company_report 
                        WHERE company_id = %s AND year = %s
                    """
                    cursor.execute(sql_details, (stock_code, report_year))
                    details = cursor.fetchall()
                    
                    # 計算 ESG 分數
                    scores = calculate_esg_scores(industry, details)
                    
                    # 組合公司物件
                    company_obj = {
                        'id': comp['ESG_id'],
                        'name': comp['company_name'],
                        'stockId': comp['company_code'],
                        'industry': comp['industry'],
                        'year': comp['Report_year'],
                        'url': comp['URL'],
                        'greenwashingScore': scores['Total'],
                        'eScore': scores['E'],
                        'sScore': scores['S'],
                        'gScore': scores['G'],
                        'layer4Data': details
                    }
                    companies_data.append(company_obj)
                    
    except Exception as e:
        print(f"首頁載入錯誤: {e}")

    return render_template('index.html', companies=companies_data)


# ==================================================
# 進度查詢 API
# ==================================================
@app.route('/api/check_progress/<esg_id>', methods=['GET'])
def check_progress(esg_id):
    """查詢分析進度"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT analysis_status FROM company WHERE ESG_id = %s",
                    (esg_id,)
                )
                result = cursor.fetchone()

                if not result:
                    return jsonify({"stage": "unknown", "status": "not_found"}), 404

                current_status = result["analysis_status"] or "processing"
                
                response = jsonify(build_progress_response(
                    stage=current_status,
                    status="completed" if current_status == "completed" else "processing"
                ))
    
                # 禁用快取
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                
                return response

    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


# ==================================================
# 查詢公司 ESG 資料 API
# ==================================================
@app.route('/api/query_company', methods=['POST'])
def query_company():
    """
    查詢公司 ESG 資料並處理自動抓取
    
    請求參數：
        {
            "year": 2024,
            "company_code": "2330",
            "auto_fetch": false
        }
    """
    try:
        from src.crawler_esgReport import validate_report_exists
        
        # 解析請求參數
        data = request.get_json()
        year = int(data.get('year'))
        company_code = str(data.get('company_code')).strip()
        auto_fetch = data.get('auto_fetch', False)
        
        if not year or not company_code:
            return jsonify(build_error_response('error', '參數錯誤：year 和 company_code 為必填')), 400
        
        esg_id = f"{year}{company_code}"
        
        # 1. 查詢資料庫
        result = query_company_data(year, company_code)
        
        # 使用資料庫中的真實 ESG_id
        if result['exists'] and result['data'] and 'ESG_id' in result['data']:
            esg_id = result['data']['ESG_id']
        
        # 情況 A: completed - 直接回傳資料
        if result['status'] == 'completed':
            return jsonify(build_company_response(
                company_data=result['data'],
                details=result['details'],
                status='completed',
                message='資料已存在'
            ))
        
        # 情況 B: processing - 回傳進行中訊息
        elif result['status'] == 'processing':
            return jsonify(build_processing_response(esg_id))
        
        # 情況 C & D: failed 或 not_found - 需要驗證報告是否存在
        else:
            # 驗證報告是否存在
            exists, report_info = validate_report_exists(year, company_code)
            
            if not exists:
                return jsonify(build_not_found_response(year, company_code, esg_id)), 404
            
            # 報告存在，但用戶尚未同意自動抓取
            if not auto_fetch:
                return jsonify(build_validation_needed_response(esg_id, report_info))
            
            # === 用戶同意自動抓取，開始執行流程 ===
            is_retry = (result['status'] == 'failed')
            
            if is_retry:
                update_analysis_status(esg_id, 'processing')
            else:
                success, _, msg = insert_company_basic(
                    year=year,
                    company_code=company_code,
                    company_name=report_info.get('company_name', ''),
                    industry=report_info.get('sector', ''),
                    status='processing'
                )
                
                if not success and '已存在' not in msg:
                    return jsonify(build_error_response('error', f'插入基本資料失敗: {msg}')), 500
            
            # 執行完整分析流程
            analysis_result = run_full_analysis(
                esg_id=esg_id,
                year=year,
                company_code=company_code,
                company_name=report_info.get('company_name', ''),
                industry=report_info.get('sector', ''),
                report_info=report_info
            )
            
            if not analysis_result['success']:
                return jsonify(build_error_response(
                    'failed',
                    analysis_result['message'],
                    esg_id
                )), 500
            
            # 查詢完整資料並回傳
            final_result = query_company_data(year, company_code)
            
            if final_result['status'] == 'completed':
                return jsonify(build_company_response(
                    company_data=final_result['data'],
                    details=final_result['details'],
                    status='completed',
                    message='自動抓取與分析完成'
                ))
            else:
                return jsonify(build_error_response(
                    'error',
                    '分析完成但資料查詢失敗',
                    esg_id
                )), 500
    
    except Exception as e:
        return jsonify(build_error_response('error', f'系統錯誤: {str(e)}')), 500


# ==================================================
# 靜態檔案路由
# ==================================================
@app.route('/word_cloud/wc_output/<filename>')
def serve_wordcloud(filename):
    """提供 Word Cloud JSON 檔案"""
    return send_from_directory(PATHS['WORD_CLOUD_OUTPUT'], filename)


@app.route('/api/companies')
def api_companies():
    """公司列表 API (保留供未來使用)"""
    pass


# ==================================================
# 應用程式入口
# ==================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)