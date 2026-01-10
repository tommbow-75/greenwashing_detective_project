import os
import pymysql
from dotenv import load_dotenv

# 載入 .env
load_dotenv()

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

def get_company_reports(user_input):
    """
    回傳多筆公司報告（list[dict]）
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT r.*
                FROM company_report r
                JOIN company c ON r.company_id = c.company_id
                WHERE c.company_id = %s OR c.company_name = %s
            """
            cursor.execute(sql, (user_input, user_input))
            return cursor.fetchall()
    finally:
        connection.close()

def get_latest_company_report(user_input):
    """
    供 B 按鈕使用：回傳最新一筆公司報告（dict or None）
    """
    reports = get_company_reports(user_input)
    if not reports:
        return None
    return reports[-1]

def get_company_updates(user_input: str, limit: int = 4):
    """
    C 按鈕用：回傳公司最新動態清單（list[dict]）
    - 若 DB 有 company_news / news 類表：優先查表
    - 若沒有：用 company_report 的內容做保底資料（避免 demo 翻車）
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # ✅ 1) 優先嘗試：company_news（你們若之後建立這張表就直接生效）
            # 欄位假設：title, date, content, url, company_id
            try:
                sql = """
                    SELECT n.title, n.date, n.content, n.url
                    FROM company_news n
                    JOIN company c ON n.company_id = c.company_id
                    WHERE c.company_id = %s OR c.company_name = %s
                    ORDER BY n.date DESC
                    LIMIT %s
                """
                cursor.execute(sql, (user_input, user_input, limit))
                rows = cursor.fetchall()
                if rows:
                    return rows
            except Exception:
                pass

            # ✅ 2) 保底：從 company_report 抓最近資料，切出「可顯示的動態」
            try:
                sql = """
                    SELECT r.*
                    FROM company_report r
                    JOIN company c ON r.company_id = c.company_id
                    WHERE c.company_id = %s OR c.company_name = %s
                    ORDER BY r.id DESC
                    LIMIT %s
                """
                cursor.execute(sql, (user_input, user_input, limit))
                reports = cursor.fetchall() or []
            except Exception:
                reports = []

            updates = []
            for r in reports:
                # 盡量抓得到的欄位當 title
                title = (
                    (r.get("sasb_topic") or r.get("topic") or r.get("esg_domain") or "ESG 更新")
                )
                # date 欄位可能叫 created_at / updated_at / date
                date = (r.get("date") or r.get("updated_at") or r.get("created_at") or "")
                # content 優先用 external_evidence / report_claim
                content = (r.get("external_evidence") or r.get("report_claim") or "")
                updates.append({
                    "title": str(title),
                    "date": str(date)[:10] if date else "",
                    "content": str(content),
                    "url": ""
                })
            return updates

    finally:
        connection.close()

