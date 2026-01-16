# JSON Key 結構調整記錄

**日期**: 2026-01-16

## 修改摘要

本次修改主要解決兩個問題：
1. **JSON key 大小寫不一致** - 統一所有 key 為小寫
2. **調整 company 欄位語意** - 改為儲存公司名稱，新增 company_id 儲存代碼

---

## 修改一：JSON Key 大小寫統一

### 變更內容
| 修改前 | 修改後 |
|--------|--------|
| `ESG_category` | `esg_category` |
| `SASB_topic` | `sasb_topic` |
| `MSCI_flag` | `msci_flag` |
| `Internal_consistency` | `internal_consistency` |

### 影響檔案
- `gemini_api.py` - Prompt 輸出格式
- `db_service.py` - JSON 讀取 key
- `run_prompt2_gemini.py` - Prompt 範例

### 原因
MySQL 對欄位名稱大小寫不敏感，但 Python 讀取 JSON 時對 key 大小寫敏感，統一使用小寫避免錯誤。

---

## 修改二：調整 company 欄位結構

### 變更內容
| 欄位 | 修改前 | 修改後 |
|------|--------|--------|
| `company` | 公司代碼（如 "1102"） | 公司名稱（如 "亞泥"） |
| `company_id` | 無此欄位 | 新增：公司代碼（如 "1102"） |

### 影響檔案
- `gemini_api.py`
  - `ESGReportAnalyzer.__init__()` 新增 `company_name` 參數
  - `run()` 方法 Prompt 更新輸出格式
  - `analyze_esg_report()` 傳遞 `company_name`

- `run_prompt2_gemini.py`
  - 更新 Prompt 欄位說明

- `news_search/crawler_news.py`
  - 直接使用 `company` 作為公司名稱
  - 從 `company_id` 取得公司代碼

### 原因
使用公司名稱（如「亞泥」）搜尋新聞比使用代碼（如「1102」）更符合實際報導習慣，提升新聞搜尋準確度。

---

## 修改三：移除已棄用函數

### 變更內容
- 刪除 `gemini_api.py` 中的 `analyze_esg_report_mock()` 函數

### 原因
該測試用模擬函數已被 `analyze_esg_report()` 取代，不再需要。

---

## 修改四：更新註解

### 變更內容
- `gemini_api.py` 第 278-280 行
- 「預留接口（尚未實作）」→「主要分析接口」

### 原因
`analyze_esg_report()` 已完整實作，註解需反映實際狀態。

---

## 注意事項

> ⚠️ **向後相容性**  
> 舊的 P1 JSON 檔案（`company` 儲存代碼）無法正常使用，需重新生成。

## 驗證方法

執行完整 ESG 分析流程，確認：
1. P1 JSON 包含 `company`（名稱）和 `company_id`（代碼）
2. 新聞搜尋使用公司名稱
3. 資料庫寫入正常
