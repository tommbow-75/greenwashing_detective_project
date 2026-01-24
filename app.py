
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
import pymysql
from pymysql.cursors import DictCursor
import os
import json
from dotenv import load_dotenv
from src.calculate_esg import calculate_esg_scores
from config import PATHS

load_dotenv()

# ==============Flask 部分========================
app = Flask(__name__)

# === 🆕 記憶體標記：追蹤正在活躍處理中的公司 ===
# 服務重啟時會清空，用於區分「活躍處理中」和「中斷需恢復」
import time
ACTIVE_PROCESSING = {}  # {esg_id: start_timestamp}

def cleanup_temp_files(year, company_code, company_name):
    """當整個流程完全成功後，清理所有暫存 JSON 與 PDF"""
    file_targets = [
        # 1. ESG 報告 PDF
        os.path.join(PATHS['ESG_REPORTS'], f"{year}_{company_code}_{company_name}_永續報告書.pdf"),
        
        # 2. Stage 2 產出的 P1 JSON
        os.path.join(PATHS['P1_JSON'], f"{year}_{company_code}_p1.json"),
        
        # 3. Stage 3 產出的 News JSON
        os.path.join(PATHS['NEWS_OUTPUT'], f"{year}_{company_code}_news.json"),
        
        # 4. Stage 4 產出的 P2 JSON
        os.path.join(PATHS['P2_JSON'], f"{year}_{company_code}_p2.json"),
        
        # 5. Stage 5 產出的 P3 JSON
        os.path.join(PATHS['P3_JSON'], f"{year}_{company_code}_p3.json"),
    ]
    
    print(f"🧹 開始執行最終清理流程 ({year}_{company_code})...")
    for file_path in file_targets:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"  ✅ 已刪除: {os.path.basename(file_path)}")
        except Exception as e:
            # 使用 print 或 logging 記錄錯誤，但不中斷主程式
            print(f"  ⚠️ 無法刪除 {file_path}: {e}")

def mark_processing_start(esg_id):
    """標記開始處理某公司"""
    ACTIVE_PROCESSING[esg_id] = time.time()
    print(f"🟢 標記開始處理: {esg_id}")

def mark_processing_end(esg_id):
    """標記處理結束（完成或失敗）"""
    if esg_id in ACTIVE_PROCESSING:
        del ACTIVE_PROCESSING[esg_id]
        print(f"🔴 標記處理結束: {esg_id}")

def is_actively_processing(esg_id):
    """檢查是否正在活躍處理中"""
    return esg_id in ACTIVE_PROCESSING


# --- 資料庫連線設定 ---
def get_db_connection():
    return pymysql.connect(
        db_port=os.getenv('DB_PORT'),
        port = int(db_port) if db_port else 3306,
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
        # 關鍵：強制同步資料庫狀態
        conn.commit()
        with conn.cursor() as cursor:
            # --- [Update] 資料庫讀取段落 (取得所有公司) ---
            # 資料表名稱變更: companies -> company
            # 欄位對應: id -> ESG_id (或忽略), name -> company_name, stock_id -> company_code
            # 🆕 只取 analysis_status = 'completed' 的資料，排除正在分析中的記錄
            sql_companies = "SELECT * FROM company WHERE analysis_status = 'completed'"
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


# ==================================================
# 新增: 進度查詢 API
# ==================================================
@app.route('/api/check_progress/<esg_id>', methods=['GET'])
def check_progress(esg_id):
    from src.db_service import get_db_connection # 確保使用帶有 commit/close 的版本
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 🆕 同步讀取分析狀態、具體百分比與最後一筆 Log
                sql = "SELECT analysis_status FROM company WHERE ESG_id = %s"
                # sql = "SELECT analysis_status, analysis_progress, last_log FROM company WHERE ESG_id = %s"
                cursor.execute(sql, (esg_id,))
                result = cursor.fetchone()

                if not result:
                    return jsonify({"stage": "unknown", "status": "not_found"}), 404

                # 不預設為 stage1，直接回傳資料庫真實狀態
                current_status = result["analysis_status"] or "processing"
                # progress = result["analysis_progress"] or 0
                # log = result["last_log"] or ""
                
                response = jsonify({
                    "stage": current_status,
                    "status": "completed" if current_status == "completed" else "processing"
                })
    
                # 強制後端不給瀏覽器快取
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                
                return response

                #舊程式碼
                #return jsonify({
                #    "stage": current_status,  # 這會對應前端的 data.stage
                #    # "progress": progress,
                #    # "last_log": log,
                #    "status": "completed" if current_status == "completed" else "processing"
                #})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

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
        from src.db_service import query_company_data, insert_company_basic, update_analysis_status, insert_analysis_results
        from src.crawler_esgReport import validate_report_exists, download_esg_report
        from src.gemini_api import analyze_esg_report
        
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
        
        PROCESSING_STATES = ['processing', 'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6']
        should_execute = False  # 🆕 標記是否進入執行流程

        # 情況 A: completed - 直接回傳資料
        if result['status'] == 'completed':
            # 計算 ESG 分數（使用現有邏輯）
            from src.calculate_esg import calculate_esg_scores
            
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
        
        # 情況 B: processing/stageN - 需要判斷是「正在執行中」還是「中斷需要恢復」
        elif result['status'] in PROCESSING_STATES:
            # 🆕 使用記憶體標記判斷是否正在活躍處理
            if is_actively_processing(esg_id):
                # 後端正在活躍處理中，回傳 processing 讓前端顯示進度條
                return jsonify({
                    'status': 'processing',
                    'message': '分析進行中，請稍候',
                    'esg_id': esg_id
                })
            else:
                # 後端已中斷（記憶體標記不存在），需要用戶選擇
                if not auto_fetch:
                    return jsonify({
                        'status': 'resume_needed',
                        'message': f'偵測到上次分析中斷於 {result["status"]}，是否要從斷點繼續？',
                        'current_stage': result['status'],
                        'esg_id': esg_id
                    })
                # 用戶已同意 auto_fetch，取得 report_info 並繼續
                exists, report_info = validate_report_exists(year, company_code)
                if not exists:
                    return jsonify({
                        'status': 'not_found',
                        'message': f'查無 {year} 年度的永續報告（公司代碼: {company_code}）',
                        'esg_id': esg_id
                    }), 404
                # 🆕 設置標記，進入下方執行流程
                should_execute = True
        
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
            
            # 🆕 設置標記，進入下方執行流程
            should_execute = True
        
        # === 用戶同意自動抓取，開始執行流程 ===
        # 🆕 只有當 should_execute = True 時才會繼續
        if not should_execute:
            return jsonify({
                'status': 'error',
                'message': '程式流程異常，請重新操作'
            }), 500
        
        # 🆕 導入斷點續傳工具
        from src.recovery_utils import determine_resume_point, print_recovery_status
        
        # 檢查是否為重新啟動（資料已存在且狀態為 failed 或 stageN）
        PROCESSING_STATES_FOR_RESUME = ['failed', 'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6']
        is_resume = (result['status'] in PROCESSING_STATES_FOR_RESUME)
        
        if is_resume:
            # 🆕 斷點續傳：判斷應從哪個階段繼續
            recovery_info = print_recovery_status(year, company_code, result['status'])
            resume_from = recovery_info['resume_from']
            print(f"📌 斷點續傳模式：從 {resume_from} 繼續")
            run_analysis = True  # 🆕 標記需要執行分析
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
            
            resume_from = 'stage1'  # 首次執行從 stage1 開始
            run_analysis = True  # 🆕 標記需要執行分析
        
        # === 開始執行分析流程 ===
        if run_analysis:
            print(f"🔍 DEBUG: 進入 run_analysis 區塊，resume_from={resume_from}")
            # 🆕 標記開始處理（用於區分活躍處理和中斷恢復）
            mark_processing_start(esg_id)
            try:
                # === Stage 1: 下載 PDF ===
                if resume_from in ['stage1']:
                    update_analysis_status(esg_id, 'stage1')
                    print("\n--- Step 1: 下載 PDF ---")
                    download_success, pdf_path_or_error = download_esg_report(year, company_code)
                    
                    if not download_success:
                        # 下載失敗，更新狀態為 failed
                        update_analysis_status(esg_id, 'failed')
                        mark_processing_end(esg_id)  # 🆕 標記處理結束
                        return jsonify({
                            'status': 'failed',
                            'message': f'下載失敗: {pdf_path_or_error}',
                            'esg_id': esg_id
                        }), 500
                    
                    pdf_path = pdf_path_or_error
                else:
                    # 🆕 跳過已完成的階段，取得已存在的 PDF 路徑
                    from src.recovery_utils import check_pdf_exists
                    _, pdf_path = check_pdf_exists(year, company_code)
                    print(f"⏭️ Stage 1 已完成，跳過（PDF: {pdf_path}）")
                
                # === Stage 2: 平行執行 Word Cloud 和 AI 分析 ===
                if resume_from in ['stage1', 'stage2']:
                    import threading
                    
                    # 儲存結果的變數
                    wordcloud_result = None
                    analysis_result = None
                    
                    def run_wordcloud():
                        """Word Cloud 生成執行緒"""
                        nonlocal wordcloud_result
                        try:
                            from src.word_cloud import generate_wordcloud
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
                    
                    print("\n--- Step 2: AI 分析 ---")
                    print("🚀 啟動平行處理：Word Cloud 與 AI 分析")
                    update_analysis_status(esg_id, 'stage2')
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
                else:
                    # 🆕 跳過 Stage 2
                    analysis_result = {'url': ''}  # 佔位，後續會從 report_info 取得 URL
                    print(f"⏭️ Stage 2 已完成，跳過 AI 分析")
                
                # === Stage 3: 新聞爬蟲驗證 ===
                if resume_from in ['stage1', 'stage2', 'stage3']:
                    print("\n--- Step 3: 新聞爬蟲驗證 ---")
                    update_analysis_status(esg_id, 'stage3')
                    try:
                        from src.crawler_news import search_news_for_report
                        
                        news_result = search_news_for_report(
                            year=year,
                            company_code=company_code,
                            force_regenerate=True
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
                else:
                    print(f"⏭️ Stage 3 已完成，跳過新聞爬蟲")
                
                # === Stage 4: AI 驗證與評分調整 ===
                if resume_from in ['stage1', 'stage2', 'stage3', 'stage4']:
                    print("\n--- Step 4: AI 驗證與評分調整 ---")
                    update_analysis_status(esg_id, 'stage4')
                    try:
                        from src.run_prompt2_gemini import verify_esg_with_news
                        
                        verify_result = verify_esg_with_news(
                            year=year,
                            company_code=company_code,
                            force_regenerate=True
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
                else:
                    print(f"⏭️ Stage 4 已完成，跳過 AI 驗證")
                
                # === Stage 5: 來源可靠度驗證 ===
                if resume_from in ['stage1', 'stage2', 'stage3', 'stage4', 'stage5']:
                    print("\n--- Step 5: 來源可靠度驗證 ---")
                    update_analysis_status(esg_id, 'stage5')
                    try:
                        from src.pplx_api import verify_evidence_sources
                        
                        pplx_result = verify_evidence_sources(
                            year=year,
                            company_code=company_code,
                            force_regenerate=True
                        )
                        
                        if pplx_result['success']:
                            if pplx_result.get('skipped'):
                                print(f"ℹ️ 來源驗證結果已存在，跳過生成")
                            else:
                                stats = pplx_result['statistics']
                                print(f"✅ 來源驗證完成")
                                print(f"   輸出檔案: {pplx_result['output_path']}")
                                print(f"   輸入項目: {stats['total_input']}")
                                print(f"   輸出項目: {stats['total_output']}")
                                print(f"   有效 URL: {stats['verified_count']}")
                                print(f"   更新 URL: {stats['updated_count']}")
                                print(f"   失敗項目: {stats['failed_count']}")
                                print(f"   執行時間: {stats['execution_time']:.2f} 秒")
                        else:
                            print(f"⚠️ 來源驗證失敗：{pplx_result.get('error')}（不影響主流程）")
                    except Exception as e:
                        print(f"⚠️ 來源驗證發生錯誤: {str(e)}（不影響主流程）")
                else:
                    print(f"⏭️ Stage 5 已完成，跳過來源驗證")
                
                # Step 7: 讀取 P3 JSON 並插入分析結果至資料庫
                print("\n--- Step 7: 存入資料庫 ---")
                update_analysis_status(esg_id, 'stage6')
                import json
                
                # 讀取 P3 JSON（最終分析結果）
                p3_path = os.path.join(PATHS['P3_JSON'], f'{year}_{company_code}_p3.json')
                
                if os.path.exists(p3_path):
                    with open(p3_path, 'r', encoding='utf-8') as f:
                        final_analysis_items = json.load(f)
                    print(f"📂 載入 P3 JSON: {len(final_analysis_items)} 筆分析項目")
                else:
                    # P3 不存在，更新狀態為 failed
                    print(f"❌ P3 JSON 不存在: {p3_path}")
                    update_analysis_status(esg_id, 'failed')
                    return jsonify({
                        'status': 'failed',
                        'message': f'分析流程未完成：找不到 P3 JSON 檔案 ({p3_path})。請確認 Step 5 (AI 驗證與評分調整) 和 Step 6 (來源可靠度驗證) 已成功執行。',
                        'esg_id': esg_id
                    }), 500
                
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
                    from src.calculate_esg import calculate_esg_scores
                    
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
                    
                    # 🆕 在這裡執行統一清理
                    cleanup_temp_files(year, company_code, company_name)
                    # 🆕 標記處理結束
                    mark_processing_end(esg_id)
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
                # 🆕 標記處理結束
                mark_processing_end(esg_id)
                return jsonify({
                    'status': 'failed',
                    'message': f'處理過程發生錯誤: {str(e)}',
                    'esg_id': esg_id
                }), 500
        else:
            # 🆕 run_analysis 為 False 的情況（不應該發生）
            return jsonify({
                'status': 'error',
                'message': '程式流程異常：未能進入分析流程',
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
    return send_from_directory(PATHS['WORD_CLOUD_OUTPUT'], filename)

# 如果需要 API 格式 (Optional)
@app.route('/api/companies')
def api_companies():
    pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)