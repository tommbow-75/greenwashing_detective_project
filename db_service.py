# 執行程式之前，請先在cmd 執行gcloud auth application-default login，登入GCP中設定成IAM的Google帳戶
# 缺少套件要pip install cloud-sql-python-connector以及pymysql
import pymysql
from google.cloud.sql.connector import Connector, IPTypes

# --- 設定區域 ---
INSTANCE_CONNECTION_NAME = "" # 格式：專案ID:區域:實例名稱
DB_USER = ""         # 更改為自己的使用者名稱
DB_NAME = "ESG"
# ----------------

def get_connection():
    # 初始化 Cloud SQL Connector
    # 它會自動尋找環境變數 GOOGLE_APPLICATION_CREDENTIALS 指向的 JSON 金鑰
    connector = Connector()

    def getconn():
        conn = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pymysql",
            user=DB_USER,
            password="", # 更改為自己的使用者密碼，沒有就不用動
            db=DB_NAME,
            enable_iam_auth=False, # 關鍵：關閉 IAM 驗證
            ip_type=IPTypes.PUBLIC # 如果你的實例只開私有 IP，請改為 IPTypes.PRIVATE
        )
        return conn
    
    return getconn

# 執行 SQL 的主程式
def main():
    # 取得連線產生器
    getconn = get_connection()
    db = None
    try:
        # 建立連線
        db = getconn()
        with db.cursor() as cursor:
            print("--- 連線成功，開始執行 SQL ---")

            # ==========================================
            # 此處為 SQL 程式碼區域：更新與上傳 Table
            # ==========================================
            
            # 可以改成自己的測試SQL語法
            # 範例 1：建立資料表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS company(
                ESG_id VARCHAR(8) NOT NULL PRIMARY KEY,
                company_name VARCHAR(20),
                industry VARCHAR(20),
                company_code VARCHAR(4),
                Report_year INT,
                total_score DECIMAL(5,2),
                URL VARCHAR(24)
            )
            """
            cursor.execute(create_table_sql)
            print("Table 檢查/建立完成")

            # 範例 2：上傳資料 (INSERT)
            # insert_sql = "INSERT INTO user_logs (username, action) VALUES (%s, %s)"
            # data_to_upload = ("Gemini_User", "Login_Success")
            # cursor.execute(insert_sql, data_to_upload)
            
            # 範例 3：更新資料 (UPDATE)
            # update_sql = "UPDATE user_logs SET action = %s WHERE username = %s"
            # cursor.execute(update_sql, ("Logout", "Gemini_User"))

            # 提交變更
            db.commit()
            print(f"成功更新並上傳 {cursor.rowcount} 筆資料")

    except Exception as e:
        print(f"發生錯誤: {e}")
    finally:
        if db is not None:
            db.close()
            print("連線已關閉")

if __name__ == "__main__":
    main()