# T6 程式碼結構說明

## 修改檔案

### 1. db_service.py

#### `insert_analysis_results()` 函數

**位置：** 第 170-240 行

**功能：** 插入完整的分析結果至 company_report 表

**參數：**
- `esg_id`: ESG 識別碼（格式：20242330）
- `company_name`: 公司名稱
- `industry`: 產業別
- `url`: 永續報告書連結
- `analysis_items`: 分析項目列表（P3 JSON 格式）

**流程：**
```
1. 更新 company 表基本資料
2. 解析 ESG_id 取得 year 和 company_code
3. 刪除舊的分析資料
4. 逐筆插入 analysis_items 至 company_report 表
   - 包含 is_verified 欄位布林值轉換
```

**INSERT SQL 欄位（15 個）：**
```
ESG_id, company_id, year, ESG_category, SASB_topic, page_number, 
report_claim, greenwashing_factor, risk_score, external_evidence, 
external_evidence_url, consistency_status, MSCI_flag, adjustment_score, is_verified
```

---

#### `query_company_data()` 函數

**位置：** 第 40-104 行

**變更：** SELECT 語句新增 `is_verified` 欄位

---

### 2. app.py

#### Step 7 邏輯（第 414-441 行）

**功能：** 讀取 P3 JSON 並存入資料庫

**流程：**
```python
# 1. 構建 P3 JSON 路徑
p3_path = f"temp_data/prompt3_json/{year}_{company_code}_p3.json"

# 2. 讀取檔案
if os.path.exists(p3_path):
    with open(p3_path, 'r', encoding='utf-8') as f:
        final_analysis_items = json.load(f)

# 3. 呼叫 insert_analysis_results()
insert_success, insert_msg = insert_analysis_results(...)
```

---

## 完整流程

```
Step 1: 查詢資料庫
   ↓
Step 2: 下載 PDF
   ↓
Step 3a: 文字雲生成 (平行)
Step 3b: AI 分析 → P1.json
   ↓
Step 4: 新聞爬蟲
   ↓
Step 5: AI 驗證 → P2.json
   ↓
Step 6: 來源驗證 → P3.json
   ↓
Step 7: 讀取 P3.json → 存入資料庫  ← T6 整合
   ↓
Step 8: 更新狀態為 completed
   ↓
Step 9: 回傳完整結果
```
