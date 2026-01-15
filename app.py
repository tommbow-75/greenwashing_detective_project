
import requests
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
                           consistency_status, MSCI_flag, is_verified
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

# 新增：查詢公司 ESG 資料的 API
@app.route('/api/query_company', methods=['POST'])
def query_company():
    """
    查詢公司 ESG 資料並處理自動抓取
    
    請求參數：
        {
            "year": 2024,
            "company_code": "2330",
            "auto_fetch": false  # 是否同意自動抓取
        }
    
    回應格式：
        {
            "status": "completed|processing|failed|validation_needed|not_found",
            "message": "說明訊息",
            "data": {...},  # 若有資料則包含完整 ESG 分析結果
            "esg_id": "20242330"
        }
    """
    try:
        # 延遲導入以避免循環依賴或初始化錯誤，並確保能被 try-except 捕獲
        from db_service import query_company_data, insert_company_basic, update_analysis_status, insert_analysis_results
        from crawler_esgReport import validate_report_exists, download_esg_report
        from gemini_api import analyze_esg_report
        
        # 解析請求參數
        data = request.get_json()
        year = int(data.get('year'))
        company_code = str(data.get('company_code')).strip()
        auto_fetch = data.get('auto_fetch', False)
        
        if not year or not company_code:
            return jsonify({
                'status': 'error',
                'message': '參數錯誤：year 和 company_code 為必填'
            }), 400
        
        esg_id = f"{year}{company_code}"
        
        # 1. 查詢資料庫
        result = query_company_data(year, company_code)
        
        # 如果資料庫已存在該公司年度資料，使用資料庫中的真實 ESG_id (可能是 C001 等舊格式)
        if result['exists'] and result['data'] and 'ESG_id' in result['data']:
            esg_id = result['data']['ESG_id']
        
        # 情況 A: completed - 直接回傳資料
        if result['status'] == 'completed':
            # 計算 ESG 分數（使用現有邏輯）
            from app.calculate_esg import calculate_esg_scores
            
            company_data = result['data']
            details = result['details']
            
            scores = calculate_esg_scores(company_data['industry'], details)
            
            company_obj = {
                'id': company_data['ESG_id'],
                'name': company_data['company_name'],
                'stockId': company_data['company_code'],
                'industry': company_data['industry'],
                'year': company_data['Report_year'],
                'url': company_data['URL'],
                'greenwashingScore': scores['Total'],
                'eScore': scores['E'],
                'sScore': scores['S'],
                'gScore': scores['G'],
                'layer4Data': details
            }
            
            return jsonify({
                'status': 'completed',
                'message': '資料已存在',
                'data': company_obj,
                'esg_id': esg_id
            })
        
        # 情況 B: processing - 回傳進行中訊息
        elif result['status'] == 'processing':
            return jsonify({
                'status': 'processing',
                'message': '分析進行中，請稍候',
                'esg_id': esg_id
            })
        
        # 情況 C & D: failed 或 not_found - 需要驗證報告是否存在
        else:
            # 驗證報告是否存在
            exists, report_info = validate_report_exists(year, company_code)
            
            if not exists:
                return jsonify({
                    'status': 'not_found',
                    'message': f'查無 {year} 年度的永續報告（公司代碼: {company_code}）',
                    'esg_id': esg_id
                }), 404
            
            # 報告存在，但用戶尚未同意自動抓取
            if not auto_fetch:
                return jsonify({
                    'status': 'validation_needed',
                    'message': '查無資料，是否啟動自動抓取與分析？',
                    'report_info': report_info,
                    'esg_id': esg_id
                })
            
            # === 用戶同意自動抓取，開始執行流程 ===
            
            # 檢查是否為重新啟動（資料已存在且狀態為 failed）
            is_retry = (result['status'] == 'failed')
            
            if is_retry:
                # 重新啟動：直接更新狀態為 processing
                update_analysis_status(esg_id, 'processing')
            else:
                # 首次執行：插入基本資料
                success, _, msg = insert_company_basic(
                    year=year,
                    company_code=company_code,
                    company_name=report_info.get('company_name', ''),
                    industry=report_info.get('sector', ''),  # 添加產業類別
                    status='processing'
                )
                
                if not success and '已存在' not in msg:
                    # 如果錯誤不是「資料已存在」，則回傳錯誤
                    return jsonify({
                        'status': 'error',
                        'message': f'插入基本資料失敗: {msg}'
                    }), 500
            
            try:
                # Step 2: 下載 PDF
                download_success, pdf_path_or_error = download_esg_report(year, company_code)
                
                if not download_success:
                    # 下載失敗，更新狀態為 failed
                    update_analysis_status(esg_id, 'failed')
                    return jsonify({
                        'status': 'failed',
                        'message': f'下載失敗: {pdf_path_or_error}',
                        'esg_id': esg_id
                    }), 500
                
                pdf_path = pdf_path_or_error
                
               # Step 3a & 3b: 平行執行 Word Cloud 和 AI 分析
                import threading
                
                # 儲存結果的變數
                wordcloud_result = None
                analysis_result = None
                
                def run_wordcloud():
                    """Word Cloud 生成執行緒"""
                    nonlocal wordcloud_result
                    try:
                        from word_cloud.word_cloud import generate_wordcloud
                        wordcloud_result = generate_wordcloud(year, company_code, pdf_path, force_regenerate=False)
                    except Exception as e:
                        wordcloud_result = {'success': False, 'error': str(e)}
                        print(f"⚠️ Word Cloud 生成錯誤: {e}")
                
                def run_ai_analysis():
                    """AI 分析執行緒"""
                    nonlocal analysis_result
                    try:
                        analysis_result = analyze_esg_report(
                            pdf_path, 
                            year, 
                            company_code,
                            company_name=report_info.get('company_name', ''),
                            industry=report_info.get('sector', '')
                        )
                    except Exception as e:
                        raise  # AI 分析失敗則整個流程失敗
                
                # 建立並啟動執行緒
                wordcloud_thread = threading.Thread(target=run_wordcloud, name="WordCloudThread")
                ai_thread = threading.Thread(target=run_ai_analysis, name="AIAnalysisThread")
                
                print("🚀 啟動平行處理：Word Cloud 與 AI 分析")
                wordcloud_thread.start()
                ai_thread.start()
                
                # 等待完成
                wordcloud_thread.join(timeout=120)  # Word Cloud 最多等 2 分鐘
                ai_thread.join()  # AI 分析必須完成
                
                # 處理 Word Cloud 結果（非必要，失敗不影响主流程）
                if wordcloud_result and wordcloud_result.get('success'):
                    if wordcloud_result.get('skipped'):
                        print(f"ℹ️ Word Cloud 已存在，跳過生成")
                    else:
                        print(f"✅ Word Cloud 生成成功: {wordcloud_result.get('word_count', 0)} 個關鍵字")
                else:
                    error_msg = wordcloud_result.get('error') if wordcloud_result else 'timeout'
                    print(f"⚠️ Word Cloud 生成失敗: {error_msg}（不影響主流程）")
                
                # Step 4: 新聞爬蟲驗證 ✨ NEW
                print("\n--- Step 4: 新聞爬蟲驗證 ---")
                try:
                    from news_search.crawler_news import search_news_for_report
                    
                    news_result = search_news_for_report(
                        year=year,
                        company_code=company_code,
                        force_regenerate=False
                    )
                    
                    if news_result['success']:
                        if news_result.get('skipped'):
                            print(f"ℹ️ 新聞資料已存在，跳過生成")
                        else:
                            print(f"✅ 新聞爬蟲完成：{news_result['news_count']} 則新聞")
                            print(f"   處理項目: {news_result['processed_items']}")
                            print(f"   失敗項目: {news_result['failed_items']}")
                    else:
                        print(f"⚠️ 新聞爬蟲失敗：{news_result.get('error')}（不影響主流程）")
                except Exception as e:
                    print(f"⚠️ 新聞爬蟲發生錯誤: {str(e)}（不影響主流程）")
                
                # Step 5: AI 驗證與評分調整 ✨ NEW
                print("\n--- Step 5: AI 驗證與評分調整 ---")
                try:
                    from run_prompt2_gemini import verify_esg_with_news
                    
                    verify_result = verify_esg_with_news(
                        year=year,
                        company_code=company_code,
                        force_regenerate=False
                    )
                    
                    if verify_result['success']:
                        if verify_result.get('skipped'):
                            print(f"ℹ️ AI 驗證結果已存在，跳過生成")
                        else:
                            stats = verify_result['statistics']
                            print(f"✅ AI 驗證完成")
                            print(f"   輸出檔案: {verify_result['output_path']}")
                            print(f"   處理項目: {stats['processed_items']}")
                            print(f"   Token 使用: {stats['total_tokens']:,} (輸入: {stats['input_tokens']:,}, 輸出: {stats['output_tokens']:,})")
                            print(f"   執行時間: {stats['api_time']:.2f} 秒")
                    else:
                        print(f"⚠️ AI 驗證失敗：{verify_result.get('error')}（不影響主流程）")
                except Exception as e:
                    print(f"⚠️ AI 驗證發生錯誤: {str(e)}（不影響主流程）")
                
                # Step 6: 來源可靠度驗證 ✨ NEW
                print("\n--- Step 6: 來源可靠度驗證 ---")
                try:
                    from pplx_api import verify_evidence_sources
                    
                    pplx_result = verify_evidence_sources(
                        year=year,
                        company_code=company_code,
                        force_regenerate=False
                    )
                    
                    if pplx_result['success']:
                        if pplx_result.get('skipped'):
                            print(f"ℹ️ 來源驗證結果已存在，跳過生成")
                        else:
                            stats = pplx_result['statistics']
                            print(f"✅ 來源驗證完成")
                            print(f"   輸出檔案: {pplx_result['output_path']}")
                            print(f"   處理項目: {stats['processed_items']}")
                            print(f"   有效 URL: {stats['verified_count']}")
                            print(f"   更新 URL: {stats['updated_count']}")
                            print(f"   失敗項目: {stats['failed_count']}")
                            print(f"   Perplexity 調用: {stats['perplexity_calls']} 次")
                            print(f"   執行時間: {stats['execution_time']:.2f} 秒")
                    else:
                        print(f"⚠️ 來源驗證失敗：{pplx_result.get('error')}（不影響主流程）")
                except Exception as e:
                    print(f"⚠️ 來源驗證發生錯誤: {str(e)}（不影響主流程）")
                
                # Step 7: 讀取 P3 JSON 並插入分析結果至資料庫
                print("\n--- Step 7: 存入資料庫 ---")
                import json
                
                # 讀取 P3 JSON（最終分析結果）
                p3_path = f"temp_data/prompt3_json/{year}_{company_code}_p3.json"
                
                if os.path.exists(p3_path):
                    with open(p3_path, 'r', encoding='utf-8') as f:
                        final_analysis_items = json.load(f)
                    print(f"📂 載入 P3 JSON: {len(final_analysis_items)} 筆分析項目")
                else:
                    # P3 不存在時使用 P1 資料（fallback 但會缺少驗證資訊）
                    print(f"⚠️ P3 JSON 不存在，使用 P1 分析結果")
                    final_analysis_items = analysis_result['analysis_items']
                
                # 提取基本資訊
                company_name = report_info.get('company_name', '')
                industry = report_info.get('sector', '')
                report_url = analysis_result.get('url', f"https://mops.twse.com.tw/mops/web/t100sb07_{year}")
                
                insert_success, insert_msg = insert_analysis_results(
                    esg_id=esg_id,
                    company_name=company_name,
                    industry=industry,
                    url=report_url,
                    analysis_items=final_analysis_items
                )
                
                if not insert_success:
                    update_analysis_status(esg_id, 'failed')
                    return jsonify({
                        'status': 'failed',
                        'message': f'插入分析結果失敗: {insert_msg}',
                        'esg_id': esg_id
                    }), 500
                
                # Step 8: 更新狀態為 completed
                update_analysis_status(esg_id, 'completed')
                
                # Step 9: 查詢完整資料並回傳
                final_result = query_company_data(year, company_code)
                
                if final_result['status'] == 'completed':
                    from app.calculate_esg import calculate_esg_scores
                    
                    company_data = final_result['data']
                    details = final_result['details']
                    scores = calculate_esg_scores(company_data['industry'], details)
                    
                    company_obj = {
                        'id': company_data['ESG_id'],
                        'name': company_data['company_name'],
                        'stockId': company_data['company_code'],
                        'industry': company_data['industry'],
                        'year': company_data['Report_year'],
                        'url': company_data['URL'],
                        'greenwashingScore': scores['Total'],
                        'eScore': scores['E'],
                        'sScore': scores['S'],
                        'gScore': scores['G'],
                        'layer4Data': details
                    }
                    
                    return jsonify({
                        'status': 'completed',
                        'message': '自動抓取與分析完成',
                        'data': company_obj,
                        'esg_id': esg_id
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': '分析完成但資料查詢失敗',
                        'esg_id': esg_id
                    }), 500
            
            except Exception as e:
                # 發生錯誤，更新狀態為 failed
                update_analysis_status(esg_id, 'failed')
                return jsonify({
                    'status': 'failed',
                    'message': f'處理過程發生錯誤: {str(e)}',
                    'esg_id': esg_id
                }), 500
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'系統錯誤: {str(e)}'
        }), 500

# Serve word cloud JSON files
@app.route('/word_cloud/wc_output/<filename>')
def serve_wordcloud(filename):
    return send_from_directory('word_cloud/wc_output', filename)

# 如果需要 API 格式 (Optional)
@app.route('/api/companies')
def api_companies():
    pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)