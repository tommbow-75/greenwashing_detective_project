# T6 使用範例

## 1. 測試資料庫插入功能

### 直接測試 db_service.py

```python
import json
from db_service import insert_analysis_results

# 讀取 P3 JSON
with open('temp_data/prompt3_json/2024_1102_p3.json', 'r', encoding='utf-8') as f:
    p3_data = json.load(f)

print(f"讀取 {len(p3_data)} 筆分析項目")

# 測試插入
success, msg = insert_analysis_results(
    esg_id='20241102',
    company_name='亞洲水泥',
    industry='水泥工業',
    url='https://mops.twse.com.tw',
    analysis_items=p3_data
)

if success:
    print(f"✅ 成功: {msg}")
else:
    print(f"❌ 失敗: {msg}")
```

---

## 2. 驗證資料庫資料

### 檢查 is_verified 欄位

```sql
-- 查詢特定公司的分析資料
SELECT 
    SASB_topic,
    MSCI_flag,
    adjustment_score,
    is_verified
FROM company_report
WHERE company_id = '1102' AND year = 2024
LIMIT 5;
```

**預期結果：**
```
+-------------------+-----------+------------------+-------------+
| SASB_topic        | MSCI_flag | adjustment_score | is_verified |
+-------------------+-----------+------------------+-------------+
| 溫室氣體排放       | Green     | 4.00             | 1           |
| 空氣品質           | Yellow    | 3.00             | 1           |
| 能源管理           | Green     | 4.00             | 1           |
+-------------------+-----------+------------------+-------------+
```

---

## 3. 驗證完整流程

### 使用 API 觸發自動分析

```bash
# 發送請求（需要一個尚未分析過的公司）
curl -X POST http://localhost:5000/api/query_company \
  -H "Content-Type: application/json" \
  -d '{"year": 2024, "company_code": "2330", "auto_fetch": true}'
```

### 觀察 Console 輸出

```
🚀 啟動平行處理：Word Cloud 與 AI 分析
✅ Word Cloud 生成成功: 100 個關鍵字

--- Step 4: 新聞爬蟲驗證 ---
✅ 新聞爬蟲完成：61 則新聞

--- Step 5: AI 驗證與評分調整 ---
✅ AI 驗證完成

--- Step 6: 來源可靠度驗證 ---
✅ 來源驗證完成

--- Step 7: 存入資料庫 ---        ← T6 新增
📂 載入 P3 JSON: 26 筆分析項目    ← T6 新增
```

---

## 4. 資料完整性檢查

### Python 腳本

```python
import json
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# 讀取 P3
with open('temp_data/prompt3_json/2024_1102_p3.json', 'r', encoding='utf-8') as f:
    p3_data = json.load(f)

# 查詢資料庫
conn = pymysql.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT')),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    db=os.getenv('DB_NAME')
)

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM company_report WHERE company_id='1102' AND year=2024")
db_count = cursor.fetchone()[0]

print(f"P3 JSON 筆數: {len(p3_data)}")
print(f"資料庫筆數: {db_count}")

if len(p3_data) == db_count:
    print("✅ 資料一致性驗證通過")
else:
    print("❌ 資料筆數不符")

conn.close()
```
