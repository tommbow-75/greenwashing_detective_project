# 使用範例

## 📚 目錄

- [方式 1：導入 ESGReportAnalyzer 類別](#方式-1導入-esgreportanalyzer-類別)
- [方式 2：使用測試模擬函數](#方式-2使用測試模擬函數)
- [方式 3：命令列執行](#方式-3命令列執行)
- [在 app.py 中使用（現況）](#在-apppy-中使用現況)

---

## 方式 1：導入 ESGReportAnalyzer 類別

### 基本使用

```python
from gemini_api import ESGReportAnalyzer

# 建立分析器實例
analyzer = ESGReportAnalyzer(target_year=2024, target_company_id="2330")

# 執行分析
analyzer.run()
```

### 完整範例

```python
from gemini_api import ESGReportAnalyzer

def analyze_company_report():
    """分析台積電 2024 年 ESG 報告"""
    try:
        # 初始化分析器
        analyzer = ESGReportAnalyzer(
            target_year=2024,
            target_company_id="2330"
        )
        
        # 執行分析
        # 這會：
        # 1. 在 temp_data/esgReport/ 尋找 2024_2330*.pdf
        # 2. 上傳至 Gemini
        # 3. 執行 AI 分析
        # 4. 產生 temp_data/prompt1_json/2024_2330_p1.json
        analyzer.run()
        
        print("✅ 分析完成！")
        
    except FileNotFoundError as e:
        print(f"❌ 找不到檔案: {e}")
    except RuntimeError as e:
        print(f"❌ 執行錯誤: {e}")
    except Exception as e:
        print(f"❌ 未預期的錯誤: {e}")

if __name__ == "__main__":
    analyze_company_report()
```

### 輸出結果

執行後會產生 JSON 檔案：`temp_data/prompt1_json/2024_2330_p1.json`

JSON 格式：
```json
[
  {
    "company_id": "2330",
    "year": "2024",
    "ESG_category": "E",
    "SASB_topic": "溫室氣體排放",
    "page_number": "45",
    "report_claim": "2024年溫室氣體排放總量為...",
    "greenwashing_factor": "數據完整且經第三方查證",
    "risk_score": "4",
    "Internal_consistency": true
  },
  {
    "company_id": "2330",
    "year": "2024",
    "ESG_category": "S",
    "SASB_topic": "員工健康與安全",
    "page_number": "67",
    "report_claim": "...",
    "greenwashing_factor": "...",
    "risk_score": "3",
    "Internal_consistency": true
  }
]
```

---

## 方式 2：使用測試模擬函數

### 基本使用（目前 app.py 的做法）

```python
from gemini_api import analyze_esg_report_mock

# 產生模擬的分析結果
result = analyze_esg_report_mock(
    pdf_path="./temp_data/esgReport/2024_2330_report.pdf",
    year=2024,
    company_code="2330",
    company_name="台積電",
    industry="半導體業"
)

# 使用結果
print(f"公司名稱: {result['company_name']}")
print(f"產業: {result['industry']}")
print(f"URL: {result['url']}")
print(f"分析項目數: {len(result['analysis_items'])}")
```

### 完整範例

```python
from gemini_api import analyze_esg_report_mock

def test_analysis_flow():
    """測試分析流程（使用模擬資料）"""
    
    # 呼叫模擬函數
    result = analyze_esg_report_mock(
        pdf_path="./report.pdf",
        year=2024,
        company_code="2330",
        company_name="台積電",
        industry="半導體業"
    )
    
    # 驗證回傳格式
    assert 'company_name' in result
    assert 'industry' in result
    assert 'url' in result
    assert 'analysis_items' in result
    
    # 檢查分析項目
    for item in result['analysis_items']:
        print(f"ESG 類別: {item['ESG_category']}")
        print(f"SASB 議題: {item['SASB_topic']}")
        print(f"風險分數: {item['risk_score']}")
        print(f"頁碼: {item['page_number']}")
        print("---")
    
    print("✅ 測試通過！")

if __name__ == "__main__":
    test_analysis_flow()
```

### 回傳格式

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
            'report_claim': '承諾在 溫室氣體排放 方面達成目標...',
            'greenwashing_factor': '',  # 若 risk_score >= 3 則為空
            'risk_score': '3',
            'external_evidence': '',
            'external_evidence_url': '',
            'consistency_status': '一致',
            'MSCI_flag': 'AA',
            'adjustment_score': 0.0
        },
        # ... 2-4 筆項目
    ]
}
```

---

## 方式 3：命令列執行

### 互動式執行

```bash
python gemini_api.py
```

執行過程：
```
=== ESG 報告書自動分析系統 (Gemini 2.0 Flash) ===
請輸入年份 (預設 2024): 2024
請輸入公司代碼 (預設 2330): 2330

[SEARCH] 正在搜尋包含 '2024_2330' 的 PDF 檔案...
[FOUND] 找到檔案: 2024_2330_台積電_永續報告書.pdf
[CONFIG] 輸出檔名已設定為: 2024_2330_p1.json
[UPLOAD] 準備上傳: 2024_2330_台積電_永續報告書.pdf ...
[UPLOAD] 上傳成功，URI: ...
[WAIT] 等待 Google 處理檔案中.......
[READY] 檔案準備就緒。
>>> 發送分析請求 (Gemini 2.0 Flash)...

[SUCCESS] 分析完成！結果已儲存至: temp_data/prompt1_json/2024_2330_p1.json
提取項目數: 15
```

### 使用預設值

直接按 Enter 使用預設值（2024 年、2330 公司代碼）：
```bash
python gemini_api.py
# 直接按 Enter × 2
```

---

## 在 app.py 中使用（現況）

### 目前的使用方式

在 [app.py](../app.py) 的自動抓取流程中：

```python
# app.py L160
from gemini_api import analyze_esg_report_mock

# app.py L284-290
# Step 3: AI 分析（使用模擬版本，傳入真實的公司資料）
analysis_result = analyze_esg_report_mock(
    pdf_path, 
    year, 
    company_code,
    company_name=report_info.get('company_name', ''),
    industry=report_info.get('sector', '')
)

# 使用分析結果
insert_success, insert_msg = insert_analysis_results(
    esg_id=esg_id,
    company_name=analysis_result['company_name'],
    industry=analysis_result['industry'],
    url=analysis_result['url'],
    analysis_items=analysis_result['analysis_items']
)
```

### 流程說明

1. 使用者查詢的公司資料不存在
2. 使用者同意自動抓取
3. 系統下載 PDF 報告
4. **呼叫 `analyze_esg_report_mock()` 產生模擬分析**
5. 將結果存入資料庫

> [!IMPORTANT]
> `analyze_esg_report_mock()` 目前是生產環境中的功能，不僅僅是測試用！

---

## 🔄 未來升級計劃

### 將 mock 版本替換為真實 AI 分析

```python
# 未來的 app.py 使用方式
from gemini_api import analyze_esg_report  # 真實 AI 版本

# Step 3: AI 分析（使用真實 Gemini AI）
analysis_result = analyze_esg_report(
    pdf_path=pdf_path,
    year=year, 
    company_code=company_code
)
# 回傳格式與 mock 版本相同，可無縫替換
```

### 優點

- ✅ 真實的 AI 分析結果
- ✅ 基於 SASB 框架和 Clarkson 理論
- ✅ 完整的漂綠風險評估
- ✅ 無需修改 app.py 的其他邏輯
