# T6: 資料庫整合模組

## 變更摘要

**完成日期：** 2026-01-15  
**負責模組：** `db_service.py`, `app.py`

將 P3 JSON 最終分析結果完整儲存至資料庫，完成端到端自動化流程。

---

## 變更內容

### 1. `SQL_table.txt` - 修正語法錯誤

**問題：** 第 20-21 行缺少逗號導致 SQL 語法錯誤

```diff
-adjustment_score DECIMAL(5,2)  -- 調整分數 (扣分項)
+adjustment_score DECIMAL(5,2),  -- 調整分數 (扣分項)
 is_verified BOOLEAN NOT NULL DEFAULT TRUE   -- 外部證據是否已驗證
```

---

### 2. `db_service.py` - 新增 `is_verified` 欄位支援

**函數：** `insert_analysis_results()`

**變更：**
- INSERT SQL 新增 `is_verified` 欄位
- 實作布林值轉換邏輯（支援字串 "True"/"Failed" 轉布林值）
- 更新參數數量（14 → 15）

```python
# 布林值轉換邏輯
is_verified_raw = item.get('is_verified', True)
if isinstance(is_verified_raw, str):
    is_verified = is_verified_raw.lower() not in ('false', 'failed', '0', '')
else:
    is_verified = bool(is_verified_raw)
```

**函數：** `query_company_data()`

**變更：** SELECT 語句新增 `is_verified` 欄位

---

### 3. `app.py` - Step 7 讀取 P3 JSON

**位置：** 第 414-441 行

**變更前：** 使用 `analysis_result`（P1 資料）

**變更後：** 讀取 `temp_data/prompt3_json/{year}_{code}_p3.json`

```python
p3_path = f"temp_data/prompt3_json/{year}_{company_code}_p3.json"

if os.path.exists(p3_path):
    with open(p3_path, 'r', encoding='utf-8') as f:
        final_analysis_items = json.load(f)
```

---

## 資料流變更

```
Step 3b (P1) → Step 5 (P2) → Step 6 (P3) → Step 7 (資料庫)
                                              ↑
                                           使用 P3*
```

**P3 JSON 包含的完整欄位：**
- 基本資料：company_id, year, ESG_category, SASB_topic, page_number
- 分析結果：report_claim, risk_score
- 外部驗證：external_evidence, external_evidence_url, consistency_status
- 評級資訊：MSCI_flag, adjustment_score
- **來源驗證：is_verified** ← T6 新增支援

---

## 欄位對應表

| P3 JSON 欄位 | 資料庫欄位 | 資料類型 | 預設值 |
|-------------|-----------|---------|--------|
| is_verified | is_verified | BOOLEAN | TRUE |

**布林值轉換規則：**
| 輸入值 | 轉換結果 |
|-------|---------|
| `true` (布林) | `TRUE` |
| `"True"` (字串) | `TRUE` |
| `false` (布林) | `FALSE` |
| `"Failed"` (字串) | `FALSE` |
| `"false"` (字串) | `FALSE` |

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| [SQL_table.txt](file:///c:/project/github_push/greenwashing_detective_project/SQL_table.txt) | SQL 表結構定義 |
| [db_service.py](file:///c:/project/github_push/greenwashing_detective_project/db_service.py#L170-L240) | 資料庫服務模組 |
| [app.py](file:///c:/project/github_push/greenwashing_detective_project/app.py#L414-L441) | Flask 應用 Step 7 |
