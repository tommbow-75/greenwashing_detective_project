# 程式碼結構說明

## 📁 檔案結構

```
gemini_api.py (427 行)
├─ 模組文檔字串          (L1-15)
├─ 匯入區               (L17-32)
├─ 核心分析類別          (L35-262)
├─ 測試用模擬函數        (L265-366)
├─ 預留接口             (L369-387)
└─ 命令列執行入口        (L390-427)
```

---

## 📖 詳細分區說明

### 1. 模組文檔字串 (L1-15)

```python
"""
ESG 報告書自動分析模組

提供使用 Gemini AI 分析 ESG 永續報告書的功能。

主要類別：
    ESGReportAnalyzer: 核心分析器，使用 Gemini 2.0 Flash 模型分析 PDF 報告書

使用範例：
    # 基本使用
    from gemini_api import ESGReportAnalyzer
    
    analyzer = ESGReportAnalyzer(target_year=2024, target_company_id="2330")
    analyzer.run()  # 產生分析結果 JSON
"""
```

**功能：**
- 提供模組層級的說明
- 說明主要功能和使用方式
- 方便 IDE 顯示提示訊息

---

### 2. 匯入區 (L17-32)

```python
import os
import json
import time
import re
from typing import Dict, List, Any, Tuple

# ✅ 使用 Google 官方 GenAI SDK
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 取得程式檔案所在的目錄
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
```

**包含：**
- Python 標準庫
- 第三方套件（Google GenAI SDK, dotenv）
- 環境變數載入
- 全域常數設定

---

### 3. 核心分析類別 (L35-262)

#### 類別概覽

```python
class ESGReportAnalyzer:
    """ESG 報告書分析器"""
    
    # 類別屬性
    INPUT_DIR = "temp_data/esgReport"
    OUTPUT_DIR = "temp_data/prompt1_json"
    SASB_MAP_FILE = "static/data/SASB_weightMap.json"
    MODEL_NAME = "models/gemini-2.0-flash"
    
    # 方法
    def __init__(...)
    def _find_target_pdf(...)
    def _load_sasb_map(...)
    def upload_file_to_gemini(...)
    def run(...)
```

#### 方法詳解

##### `__init__(target_year, target_company_id)` (L58-86)

**功能：** 初始化分析器

**執行步驟：**
1. 驗證 API Key (`GEMINI_API_KEY`)
2. 建立 Gemini 客戶端
3. 設定目標年份和公司代碼
4. 建立輸出目錄
5. 尋找目標 PDF 檔案
6. 載入 SASB 權重表
7. 設定輸出檔名

**拋出異常：**
- `RuntimeError`: API Key 不存在
- `FileNotFoundError`: PDF 或 SASB 檔案不存在

---

##### `_find_target_pdf()` (L88-109)

**功能：** 在輸入目錄中搜尋符合條件的 PDF 檔案

**搜尋邏輯：**
```python
prefix = f"{target_year}_{target_company_id}"  # 例如："2024_2330"

for file in os.listdir(INPUT_DIR):
    if prefix in file and file.endswith(".pdf"):
        return (完整路徑, 檔案名稱)
```

**回傳：** `Tuple[str, str]` - (完整檔案路徑, 檔案名稱)

**範例：**
- 搜尋：`2024_2330`
- 找到：`2024_2330_台積電_永續報告書.pdf`
- 回傳：`("./temp_data/esgReport/2024_2330_台積電_永續報告書.pdf", "2024_2330_台積電_永續報告書.pdf")`

---

##### `_load_sasb_map()` (L111-123)

**功能：** 讀取 SASB 產業權重對照表

**檔案位置：** `static/data/SASB_weightMap.json`

**回傳：** `str` - JSON 字串內容

**用途：** 提供給 Gemini AI，用於識別產業和對應的 ESG 議題

---

##### `upload_file_to_gemini()` (L125-164)

**功能：** 將 PDF 上傳至 Gemini 伺服器並等待處理完成

**執行流程：**
```
1. 開啟 PDF 檔案
2. 使用 client.files.upload() 上傳
3. 每 2 秒檢查處理狀態
4. 等待狀態從 PROCESSING → ACTIVE
5. 回傳檔案參考物件
```

**顯示訊息：**
```
[UPLOAD] 準備上傳: 2024_2330_台積電_永續報告書.pdf ...
[UPLOAD] 上傳成功，URI: https://...
[WAIT] 等待 Google 處理檔案中.......
[READY] 檔案準備就緒。
```

**回傳：** Gemini 檔案參考物件

**拋出異常：**
- `RuntimeError`: 上傳失敗或處理失敗

---

##### `run()` (L166-262)

**功能：** 執行完整的 ESG 報告書分析流程

**執行步驟：**

**Step 1: 上傳 PDF**
```python
uploaded_pdf = self.upload_file_to_gemini()
```

**Step 2: 建構 Prompt**
```python
prompt_text = f"""
你是一個專業的 ESG 稽核員...
{self.sasb_map_content}  # 插入 SASB 權重表
"""
```

Prompt 包含：
- 任務說明
- SASB 權重表
- 評分邏輯（Clarkson et al. 2008）
- 輸出格式要求

**Step 3: 呼叫 Gemini AI**
```python
response = self.client.models.generate_content(
    model="models/gemini-2.0-flash",
    contents=[uploaded_pdf, prompt_text],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0  # 穩定性優先
    )
)
```

**Step 4: 解析結果**
```python
raw_json = response.text

try:
    parsed_data = json.loads(raw_json)
except json.JSONDecodeError:
    # 清除可能的 Markdown 標記
    clean_text = re.sub(r"^```json|```$", "", raw_json.strip())
    parsed_data = json.loads(clean_text)
```

**Step 5: 儲存檔案**
```python
output_path = "temp_data/prompt1_json/2024_2330_p1.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
```

**顯示訊息：**
```
>>> 發送分析請求 (Gemini 2.0 Flash)...
[SUCCESS] 分析完成！結果已儲存至: temp_data/prompt1_json/2024_2330_p1.json
提取項目數: 15
```

---

### 4. 測試用模擬函數 (L265-366)

#### `analyze_esg_report_mock(...)` 

**目前狀態：** 被 app.py 使用（L160, L284）

**功能：** 產生模擬的 ESG 分析結果

**參數：**
```python
def analyze_esg_report_mock(
    pdf_path: str,           # PDF 路徑（目前未使用）
    year: int,               # 報告年份
    company_code: str,       # 公司代碼
    company_name: str = '',  # 公司名稱（選填）
    industry: str = ''       # 產業類別（選填）
) -> dict:
```

**邏輯：**
1. 若未提供 `company_name`，使用預設對照表
2. 若未提供 `industry`，使用預設對照表
3. 產生 2-4 筆模擬分析項目
4. 隨機產生合理的風險分數和 SASB 議題

**回傳格式：**
```python
{
    'company_name': '台積電',
    'industry': '半導體業',
    'url': 'https://esg.tw/2330',
    'analysis_items': [
        {
            'ESG_category': 'E',
            'SASB_topic': '溫室氣體排放',
            'page_number': '45',
            'report_claim': '承諾在...',
            'greenwashing_factor': '',
            'risk_score': '3',
            'external_evidence': '',
            'external_evidence_url': '',
            'consistency_status': '一致',
            'MSCI_flag': 'AA',
            'adjustment_score': 0.0
        }
    ]
}
```

---

### 5. 預留接口 (L369-387)

#### `analyze_esg_report(...)`

**狀態：** 未實作（拋出 `NotImplementedError`）

**預期功能：**
- 調用 `ESGReportAnalyzer` 進行真實 AI 分析
- 將結果轉換為與 `analyze_esg_report_mock()` 相同的格式
- 可無縫替換 mock 版本

**參數：**
```python
def analyze_esg_report(
    pdf_path: str,      # PDF 檔案路徑
    year: int,          # 報告年份
    company_code: str   # 公司代碼
) -> dict:
```

**回傳格式：** 與 `analyze_esg_report_mock()` 相同

---

### 6. 命令列執行入口 (L390-427)

#### `main()`

**功能：** 提供互動式命令列界面

**執行流程：**
```python
def main():
    print("=== ESG 報告書自動分析系統 (Gemini 2.0 Flash) ===")
    
    # 獲取使用者輸入（提供預設值）
    year = input("請輸入年份 (預設 2024): ") or "2024"
    company_id = input("請輸入公司代碼 (預設 2330): ") or "2330"
    
    # 建立分析器並執行
    try:
        analyzer = ESGReportAnalyzer(int(year), company_id)
        analyzer.run()
    except Exception as e:
        print(f"❌ 程式執行中斷: {e}")
```

#### `if __name__ == "__main__"`

```python
if __name__ == "__main__":
    main()
```

確保模組可以：
- ✅ 被其他程式導入（不執行 main）
- ✅ 直接執行（執行 main）

---

## 🔄 資料流程

### 完整分析流程

```
1. 使用者輸入
   └─> target_year, target_company_id

2. 初始化
   ├─> 驗證 API Key
   ├─> 尋找 PDF 檔案
   └─> 載入 SASB 權重表

3. 上傳 PDF
   ├─> 開啟檔案
   ├─> 上傳至 Gemini
   └─> 等待處理完成

4. AI 分析
   ├─> 建構 Prompt（包含 SASB 權重表）
   ├─> 呼叫 Gemini 2.0 Flash
   └─> 取得 JSON 結果

5. 處理結果
   ├─> 解析 JSON
   ├─> 清理格式（若需要）
   └─> 儲存至檔案

6. 完成
   └─> 顯示結果路徑和項目數
```

---

## 📊 類別屬性說明

| 屬性 | 值 | 說明 |
|------|-----|------|
| `INPUT_DIR` | `temp_data/esgReport` | PDF 報告書輸入目錄 |
| `OUTPUT_DIR` | `temp_data/prompt1_json` | JSON 結果輸出目錄 |
| `SASB_MAP_FILE` | `static/data/SASB_weightMap.json` | SASB 權重表路徑 |
| `MODEL_NAME` | `models/gemini-2.0-flash` | 使用的 AI 模型 |

---

## 🎯 設計原則

1. **單一職責**
   - `ESGReportAnalyzer`: 負責 AI 分析
   - `analyze_esg_report_mock()`: 負責產生測試資料
   - `main()`: 負責命令列界面

2. **錯誤處理**
   - 使用明確的異常類型
   - 提供清楚的錯誤訊息
   - 建議使用 try-except 捕獲

3. **可維護性**
   - 完整的文檔字串
   - 清晰的程式碼結構
   - 合理的函數拆分

4. **可擴展性**
   - 預留 `analyze_esg_report()` 接口
   - 類別屬性可被繼承覆寫
   - 模組化設計便於整合
