"""
資料庫服務模組
提供 ESG 資料的查詢、插入和更新功能
"""

import pymysql
from pymysql.cursors import DictCursor
import os
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()


@contextmanager
def get_db_connection():
    """
    資料庫連線 Context Manager
    自動處理連線的開啟與關閉
    """
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT')),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=DictCursor
    )
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def query_company_data(year, company_code):
    """
    查詢公司 ESG 資料及分析狀態
    
    Args:
        year: 報告年份
        company_code: 公司代碼（股票代號）
    
    Returns:
        dict: {
            'exists': bool,  # 資料是否存在
            'status': str,   # 'completed', 'processing', 'failed', 'not_found'
            'data': dict or None,  # 完整的公司資料（若存在）
            'details': list or None  # ESG 分析細項資料（若 completed）
        }
    """
    # 預設的 esg_id (用於新資料)，但查詢時不應只依賴它
    default_esg_id = f"{year}{company_code}"
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # 修正：改用 company_code 和 Report_year 查詢，因為舊資料的 ESG_id 格式可能不同 (如 C001)
            sql_company = """
                SELECT * FROM company 
                WHERE company_code = %s AND Report_year = %s
            """
            cursor.execute(sql_company, (company_code, year))
            company_data = cursor.fetchone()
            
            if not company_data:
                return {
                    'exists': False,
                    'status': 'not_found',
                    'data': None,
                    'details': None
                }
            
            # 資料存在，檢查狀態
            analysis_status = company_data.get('analysis_status', 'completed')
            # 確保有 ESG_id，如果是舊資料可能沒有標準化的 ESG_id，但也無妨，我們主要用它來做關聯
            current_esg_id = company_data.get('ESG_id')
            
            # 如果狀態是 completed，則查詢詳細資料
            if analysis_status == 'completed':
                # 修正：company_report 表的關聯是用 company_id 和 year
                # 因為 company_report.ESG_id 是該細項的主鍵(R001...)，不是 Foreign Key
                sql_details = """
                    SELECT ESG_category, SASB_topic, risk_score, adjustment_score,
                           report_claim, page_number, greenwashing_factor,
                           external_evidence, external_evidence_url,
                           consistency_status, MSCI_flag
                    FROM company_report
                    WHERE company_id = %s AND year = %s
                """
                cursor.execute(sql_details, (company_code, year))
                details = cursor.fetchall()
            else:
                details = None
            
            return {
                'exists': True,
                'status': analysis_status,
                'data': company_data,
                'details': details
            }


def insert_company_basic(year, company_code, company_name='', industry='', url='', status='processing'):
    """
    插入公司基本資料並設定分析狀態
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        company_name: 公司名稱（選填）
        industry: 產業別（選填）
        url: 永續報告書連結（選填）
        status: 分析狀態，預設為 'processing'
    
    Returns:
        tuple: (success: bool, esg_id: str, message: str)
    """
    esg_id = f"{year}{company_code}"
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 檢查是否已存在 (同樣使用嚴格條件)
                cursor.execute("SELECT ESG_id FROM company WHERE company_code = %s AND Report_year = %s", (company_code, year))
                existing = cursor.fetchone()
                if existing:
                    return (False, existing['ESG_id'], f"資料已存在: {existing['ESG_id']}")
                
                # 插入基本資料
                sql = """
                    INSERT INTO company 
                    (ESG_id, company_name, industry, company_code, Report_year, URL, analysis_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (esg_id, company_name, industry, company_code, year, url, status))
                
                return (True, esg_id, "基本資料已插入")
    
    except Exception as e:
        return (False, esg_id, f"插入失敗: {str(e)}")


def update_analysis_status(esg_id, status, error_msg=None):
    """
    更新分析狀態 (仍支援使用 ESG_id 更新，因為流程中我們通常知道 ID)
    但為了保險，我們也可以過載支援 (year, code)
    這裡暫時維持 esg_id，因為 insert_company_basic 回傳了 esg_id
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                sql = "UPDATE company SET analysis_status = %s WHERE ESG_id = %s"
                cursor.execute(sql, (status, esg_id))
                
                if cursor.rowcount == 0:
                    # 如果用 esg_id 找不到(可能是舊資料)，嘗試解析 esg_id 看看
                    # 但這情況較少見，除非是在處理舊資料的狀態更新
                    return (False, f"找不到資料: {esg_id}")
                
                return (True, f"狀態已更新為: {status}")
    
    except Exception as e:
        return (False, f"更新失敗: {str(e)}")


def insert_analysis_results(esg_id, company_name, industry, url, analysis_items):
    """
    插入完整的分析結果至 company_report 表，並更新 company 表的基本資料
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 1. 更新 company 表的基本資料
                update_sql = """
                    UPDATE company 
                    SET company_name = %s, industry = %s, URL = %s
                    WHERE ESG_id = %s
                """
                cursor.execute(update_sql, (company_name, industry, url, esg_id))
                
                # 2. 插入分析結果至 company_report 表
                if analysis_items:
                    # 拆解 ESG_id 取得 company_code 和 year
                    # 假設 ESG_id 是標準格式 20242330
                    year = int(esg_id[:4])
                    company_code = esg_id[4:]
                    
                    # 先刪除舊資料（依據 company_id 和 year）
                    cursor.execute("DELETE FROM company_report WHERE company_id = %s AND year = %s", (company_code, year))
                    
                    # 批次插入
                    # 注意：id 欄位由資料庫自動生成 (AUTO_INCREMENT)
                    # ESG_id 欄位現在儲存 company 的 ESG_id（用於關聯）
                    insert_sql = """
                        INSERT INTO company_report 
                        (ESG_id, company_id, year, ESG_category, SASB_topic, page_number, 
                         report_claim, greenwashing_factor, risk_score, external_evidence, 
                         external_evidence_url, consistency_status, MSCI_flag, adjustment_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    for item in analysis_items:
                        cursor.execute(insert_sql, (
                            esg_id,  # 儲存 company 的 ESG_id（如 20242330）
                            company_code,
                            year,
                            item.get('ESG_category', ''),
                            item.get('SASB_topic', ''),
                            item.get('page_number', ''),
                            item.get('report_claim', ''),
                            item.get('greenwashing_factor', ''),
                            item.get('risk_score', '0'),
                            item.get('external_evidence', ''),
                            item.get('external_evidence_url', ''),
                            item.get('consistency_status', ''),
                            item.get('MSCI_flag', ''),
                            item.get('adjustment_score', 0.0)
                        ))
                
                return (True, f"已插入 {len(analysis_items)} 筆分析資料")
    
    except Exception as e:
        return (False, f"插入分析結果失敗: {str(e)}")


if __name__ == '__main__':
    # 測試用範例
    print("=== 測試資料庫服務模組 ===\n")
    
    # 測試查詢
    print("1. 測試查詢現有資料 (2024 + 2330)")
    result = query_company_data(2024, '2330')
    print(f"   結果: {result['status']}, 存在: {result['exists']}")
    
    print("\n2. 測試查詢不存在的資料 (2024 + 9999)")
    result = query_company_data(2024, '9999')
    print(f"   結果: {result['status']}, 存在: {result['exists']}")
