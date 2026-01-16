# 依賴關係分析

## 📊 模組依賴圖

```
gemini_api.py
├─ 被以下程式使用
│  └─ app.py (L160, L284)
│     └─ 導入: analyze_esg_report_mock()
│
└─ 依賴的外部套件
   ├─ google-genai (Google GenAI SDK)
   ├─ python-dotenv (環境變數管理)
   └─ Python 標準庫
      ├─ os
      ├─ json
      ├─ time
      ├─ re
      └─ typing
```

---

## 🔍 詳細分析

### 1. app.py 對 gemini_api.py 的依賴

#### 使用位置

**[app.py:L160](../app.py#L160)** - 導入模組
```python
from gemini_api import analyze_esg_report_mock
```

**[app.py:L284-290](../app.py#L284-L290)** - 實際調用
```python
# Step 3: AI 分析（使用模擬版本，傳入真實的公司資料）
analysis_result = analyze_esg_report_mock(
    pdf_path, 
    year, 
    company_code,
    company_name=report_info.get('company_name', ''),
    industry=report_info.get('sector', '')
)
```

#### 使用場景

在 `/api/query_company` API 的自動抓取流程中：

1. **觸發條件**：查詢的公司資料不存在 + 使用者同意自動抓取
2. **執行步驟**：
   - 驗證報告存在性
   - 下載 PDF 報告
   - **呼叫 `analyze_esg_report_mock()` 進行分析**
   - 將結果存入資料庫
   - 回傳完整資料給前端

3. **回傳格式依賴**：
   ```python
   {
       'company_name': str,      # → insert_analysis_results() 參數
       'industry': str,          # → insert_analysis_results() 參數
       'url': str,               # → insert_analysis_results() 參數
       'analysis_items': [...]   # → insert_analysis_results() 參數
   }
   ```

#### 影響範圍

> [!WARNING]
> 任何對 `analyze_esg_report_mock()` 的修改都必須：
> - ✅ 保持函數簽名不變（參數名稱、順序、類型）
> - ✅ 保持回傳格式不變
> - ✅ 確保 `analysis_items` 陣列中的欄位完整

---

### 2. gemini_api.py 的外部依賴

#### Google GenAI SDK

```python
from google import genai
from google.genai import types
```

**用途：**
- 連接 Gemini AI 服務
- 上傳 PDF 檔案
- 執行 AI 分析

**安裝：**
```bash
pip install google-generativeai
```

#### python-dotenv

```python
from dotenv import load_dotenv
```

**用途：**
- 讀取 `.env` 檔案中的環境變數
- 取得 `GEMINI_API_KEY`

**安裝：**
```bash
pip install python-dotenv
```

#### Python 標準庫

無需額外安裝，Python 內建：
- `os`: 檔案路徑操作
- `json`: JSON 解析和產生
- `time`: 延遲處理（等待檔案上傳）
- `re`: 正則表達式（清理 JSON 輸出）
- `typing`: 類型註解

---

### 3. 內部檔案依賴

#### 讀取的檔案

**SASB 權重表**
- 路徑：`static/data/SASB_weightMap.json`
- 用途：提供各產業的 ESG 議題權重
- 必要性：必須存在，否則分析器無法初始化

**PDF 報告書**
- 路徑：`temp_data/esgReport/{年份}_{公司代碼}*.pdf`
- 用途：待分析的 ESG 報告書
- 必要性：必須存在，否則無法執行分析

#### 產生的檔案

**JSON 分析結果**
- 路徑：`temp_data/prompt1_json/{年份}_{公司代碼}_p1.json`
- 格式：JSON 陣列，包含所有 ESG 議題的分析結果
- 自動建立：輸出目錄會自動建立

---

## 📋 依賴檢查清單

### 執行前檢查

- [ ] `.env` 檔案存在且包含 `GEMINI_API_KEY`
- [ ] `static/data/SASB_weightMap.json` 存在
- [ ] `temp_data/esgReport/` 目錄存在
- [ ] 目標 PDF 檔案存在（格式：`{年份}_{公司代碼}*.pdf`）
- [ ] 已安裝 `google-generativeai` 套件
- [ ] 已安裝 `python-dotenv` 套件

### 執行後檢查

- [ ] `temp_data/prompt1_json/` 目錄已建立
- [ ] JSON 結果檔案已產生
- [ ] JSON 格式正確（可被解析）

---

## 🔄 向後兼容性

### 保證不變的部分

以下部分在 T1 重構中**完全保持不變**：

1. **`analyze_esg_report_mock()` 函數簽名**
   ```python
   def analyze_esg_report_mock(
       pdf_path: str,
       year: int,
       company_code: str,
       company_name: str = '',
       industry: str = ''
   ) -> dict:
   ```

2. **回傳格式**
   ```python
   {
       'company_name': str,
       'industry': str,
       'url': str,
       'analysis_items': [
           {
               'ESG_category': str,
               'SASB_topic': str,
               'page_number': str,
               'report_claim': str,
               'greenwashing_factor': str,
               'risk_score': str,
               'external_evidence': str,
               'external_evidence_url': str,
               'consistency_status': str,
               'MSCI_flag': str,
               'adjustment_score': float
           }
       ]
   }
   ```

3. **行為邏輯**
   - 若未提供 `company_name` 或 `industry`，使用預設值
   - 產生 2-4 筆模擬分析項目
   - 隨機產生合理的風險分數和 ESG 類別

### 安全的修改

- ✅ 修改內部實作（只要不影響輸出）
- ✅ 增強文檔字串
- ✅ 改進程式碼結構
- ✅ 新增其他輔助函數

### 危險的修改

- ❌ 修改函數參數名稱或順序
- ❌ 修改回傳格式
- ❌ 修改 `analysis_items` 的欄位名稱
- ❌ 移除預設參數

---

## 🎯 升級路徑

### 階段 1：目前狀態（T1 完成）

```
app.py
  └─> analyze_esg_report_mock()  [模擬資料]
```

### 階段 2：實作真實 AI 分析（未來）

```
app.py
  ├─> analyze_esg_report_mock()  [保留以備測試]
  └─> analyze_esg_report()       [真實 AI 分析]
        └─> ESGReportAnalyzer
```

### 階段 3：完全替換（最終目標）

```
app.py
  └─> analyze_esg_report()
        └─> ESGReportAnalyzer
              ├─> upload_file_to_gemini()
              └─> Gemini 2.0 Flash API
```

---

## 📝 注意事項

1. **環境變數安全**
   - `GEMINI_API_KEY` 不應提交到版本控制
   - 使用 `.env` 檔案管理
   - 確保 `.gitignore` 包含 `.env`

2. **檔案路徑**
   - 使用 `SCRIPT_DIR` 確保相對路徑正確
   - 所有路徑使用 `os.path.join()` 組合

3. **錯誤處理**
   - 檔案不存在時拋出 `FileNotFoundError`
   - API 錯誤時拋出 `RuntimeError`
   - 建議使用 try-except 捕獲異常

4. **資料格式**
   - JSON 使用 UTF-8 編碼
   - 確保中文正確顯示（`ensure_ascii=False`）
