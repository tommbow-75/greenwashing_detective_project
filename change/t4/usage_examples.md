# AI 驗證模組使用範例

## 📖 目錄

1. [方式 1：獨立運行](#方式-1獨立運行)
2. [方式 2：模組調用](#方式-2模組調用)
3. [方式 3：在 app.py 中的整合](#方式-3在-apppy-中的整合)

---

## 方式 1：獨立運行

### 命令列執行

```bash
cd c:\project\github_push\greenwashing_detective_project
python run_prompt2_gemini.py
```

### 預設行為

程式會使用硬編碼的路徑執行驗證：

```python
input_path = './temp_data/prompt1_json/2024_1102_p1.json'
news_path = './news_search/news_output/2024_1102_news.json'
msci_path = './static/data/msci_flag.json'
output_path = './temp_data/prompt2_json/2024_1102_p2.json'
```

### 輸出範例（首次執行）

```
============================================================
開始 AI 驗證與評分調整: 2024 年 1102
============================================================
✅ 成功讀取原檔：26 筆資料
✅ 成功讀取驗證資料：61 筆新聞
✅ 成功讀取 MSCI 判斷標準

📊 估計輸入 Token 數：18,523

🔄 正在呼叫 Gemini API 並檢索外部資訊，請稍候...
✅ Gemini API 呼叫完成，耗時 45.23 秒

📄 API 原始回應（前 500 字元）：
[
  {
    "company": "1102",
    "year": "2024",
    ...

✅ 使用方法 1（移除 markdown 標記）成功解析
✅ 成功！結果已儲存至 ./temp_data/prompt2_json/2024_1102_p2.json，共 26 筆

==================================================
📊 Token 使用統計
==================================================
輸入 Token 數 : 18,523
輸出 Token 數 : 9,842
總計 Token 數 : 28,365

==================================================
⏱️  執行時間統計
==================================================
API 呼叫時間  : 45.23 秒
總執行時間    : 46.12 秒
==================================================
```

---

## 方式 2：模組調用

### 基本使用

```python
from run_prompt2_gemini import verify_esg_with_news

# 自動查找所有輸入檔案
result = verify_esg_with_news(year=2024, company_code="1102")

# 檢查結果
if result['success']:
    print(f"✅ 成功：{result['message']}")
    print(f"📁 輸出：{result['output_path']}")
    
    if not result['skipped']:
        stats = result['statistics']
        print(f"📊 處理項目：{stats['processed_items']}")
        print(f"📊 Token 使用：{stats['total_tokens']:,}")
        print(f"⏱️  執行時間：{stats['api_time']:.2f} 秒")
else:
    print(f"❌ 失敗：{result['error']}")
```

### 檔案已存在時（跳過生成）

```python
result = verify_esg_with_news(year=2024, company_code="1102")

# 輸出
{
    'success': True,
    'message': 'AI 驗證結果已存在，跳過生成',
    'output_path': './temp_data/prompt2_json/2024_1102_p2.json',
    'skipped': True,
    'statistics': {
        'processed_items': 26,
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'api_time': 0,
        'total_time': 0.01
    }
}
```

### 強制重新生成

```python
result = verify_esg_with_news(
    year=2024,
    company_code="1102",
    force_regenerate=True  # 忽略現有檔案，強制重新生成
)

# 輸出
{
    'success': True,
    'message': 'AI 驗證完成',
    'output_path': './temp_data/prompt2_json/2024_1102_p2.json',
    'skipped': False,
    'statistics': {
        'processed_items': 26,
        'input_tokens': 18523,
        'output_tokens': 9842,
        'total_tokens': 28365,
        'api_time': 45.23,
        'total_time': 46.12
    }
}
```

### 錯誤處理範例

```python
# 缺少輸入檔案
result = verify_esg_with_news(year=9999, company_code="9999")

{
    'success': False,
    'message': '缺少必要輸入檔案',
    'error': 'P1 檔案: ./temp_data/prompt1_json/9999_9999_p1.json',
    'output_path': None,
    'skipped': False
}
```

---

## 方式 3：在 app.py 中的整合

### 自動執行流程

當使用者透過 `/api/query_company` 查詢公司時：

```
POST /api/query_company
{
  "year": 2024,
  "company_code": "1102",
  "auto_fetch": true
}
```

### 完整執行流程

```
1. 檢查資料庫 (Step 1)
    ↓ 資料不存在
2. 下載 PDF (Step 2)
    ↓ 下載成功
3a. Word Cloud 生成 ┐
                     ├─ 平行執行
3b. AI 分析         ┘
    ↓ 兩者完成
4. 新聞爬蟲搜尋 (Step 4)
    ↓ 完成
5. AI 驗證與評分調整 ✨ NEW (Step 5)
    ↓ 完成（失敗不影響）
6. 存入資料庫 (Step 6)
    ↓
7. 更新狀態 (Step 7)
    ↓
8. 回傳結果 (Step 8)
```

### 後端日誌（成功）

```
🚀 啟動平行處理：Word Cloud 與 AI 分析
✅ Word Cloud 生成成功: 100 個關鍵字
✅ AI 分析完成

--- Step 4: 新聞爬蟲驗證 ---
✅ 新聞爬蟲完成：61 則新聞
   處理項目: 26
   失敗項目: 2

--- Step 5: AI 驗證與評分調整 ---
============================================================
開始 AI 驗證與評分調整: 2024 年 1102
============================================================
✅ 成功讀取原檔：26 筆資料
✅ 成功讀取驗證資料：61 筆新聞
...
✅ AI 驗證完成
   輸出檔案: ./temp_data/prompt2_json/2024_1102_p2.json
   處理項目: 26
   Token 使用: 28,365 (輸入: 18,523, 輸出: 9,842)
   執行時間: 45.23 秒
```

### 後端日誌（跳過生成）

```
--- Step 5: AI 驗證與評分調整 ---
ℹ️  AI 驗證結果已存在，跳過生成
```

### 後端日誌（失敗不中斷）

```
--- Step 5: AI 驗證與評分調整 ---
⚠️ AI 驗證失敗：P1 檔案: ./temp_data/prompt1_json/2024_1102_p1.json（不影響主流程）

繼續執行 Step 6...
```

---

## 🔧 進階用法

### 批次處理多家公司

```python
from run_prompt2_gemini import verify_esg_with_news

companies = ["1101", "1102", "1314", "2330"]
year = 2024

for company_code in companies:
    print(f"\n處理：{company_code}")
    result = verify_esg_with_news(year, company_code)
    
    if result['success']:
        if result['skipped']:
            print(f"  ⏭️  已存在，跳過")
        else:
            stats = result['statistics']
            print(f"  ✅ 生成成功")
            print(f"     處理項目：{stats['processed_items']}")
            print(f"     Token 使用：{stats['total_tokens']:,}")
            print(f"     執行時間：{stats['api_time']:.2f} 秒")
    else:
        print(f"  ❌ 失敗：{result['error']}")
```

**輸出範例：**
```
處理：1101
  ✅ 生成成功
     處理項目：26
     Token 使用：28,365
     執行時間：45.23 秒

處理：1102
  ⏭️  已存在，跳過

處理：1314
  ❌ 失敗：P1 檔案: ./temp_data/prompt1_json/2024_1314_p1.json
```

### Token 成本估算

```python
result = verify_esg_with_news(year=2024, company_code="1102")

if result['success'] and not result['skipped']:
    stats = result['statistics']
    
    # Gemini 2.5 Pro 定價（假設）
    input_cost = stats['input_tokens'] * 0.000125 / 1000  # $0.125/1M tokens
    output_cost = stats['output_tokens'] * 0.000375 / 1000  # $0.375/1M tokens
    total_cost_usd = input_cost + output_cost
    total_cost_ntd = total_cost_usd * 30  # 假設匯率 1:30
    
    print(f"💰 成本估算：")
    print(f"   輸入成本：${input_cost:.4f} USD")
    print(f"   輸出成本：${output_cost:.4f} USD")
    print(f"   總計：${total_cost_usd:.4f} USD (約 NT${total_cost_ntd:.2f})")
```

### 驗證輸出格式

```python
import json

result = verify_esg_with_news(year=2024, company_code="1102")

if result['success']:
    # 讀取輸出檔案
    with open(result['output_path'], 'r', encoding='utf-8') as f:
        p2_data = json.load(f)
    
    # 檢查欄位格式
    first_item = p2_data[0]
    
    # 驗證關鍵欄位
    assert 'company' in first_item, "缺少 company 欄位"
    assert first_item['company'].isdigit(), "company 應為代碼格式"
    assert 'report_claim' in first_item, "應使用 report_claim 而非 disclosure_claim"
    assert 'external_evidence' in first_item, "缺少 external_evidence"
    assert 'msci_flag' in first_item, "缺少 msci_flag"
    
    print("✅ P2 格式驗證通過")
```

---

## 📊 輸出檔案位置

| 項目 | 路徑 |
|------|------|
| **P2 JSON** | `temp_data/prompt2_json/{year}_{company_code}_p2.json` |
| **範例** | `temp_data/prompt2_json/2024_1102_p2.json` |
| **Debug 檔案**（若解析失敗） | `temp_data/prompt2_json/2024_1102_p2_debug_response.txt` |

---

## 🔍 常見問題

### Q1: 為什麼第二次執行很快？
A: 加入了檔案存在性檢查機制，若 P2 JSON 已存在且格式正確，直接返回（< 0.1 秒）。

### Q2: 如何強制重新生成？
A: 設定 `force_regenerate=True` 參數。

### Q3: AI 驗證失敗會影響主流程嗎？
A: 不會。AI 驗證是增強功能，失敗只會記錄日誌，不影響資料庫儲存。

### Q4: Token 消耗量大概是多少？
A: 約 25,000-35,000 tokens，成本約 NT$3-5 元/次（視報告複雜度）。

### Q5: 為什麼需要修正 Prompt？
A: 舊 Prompt 會導致：
- `company`: "亞洲水泥"（公司名稱） ❌
- `disclosure_claim`: "..." ❌

新 Prompt 確保：
- `company`: "1102"（代碼） ✅
- `report_claim`: "..." ✅

### Q6: P2 JSON 和 P1 JSON 有什麼差別？
A: P2 在 P1 基礎上新增：
- `external_evidence`：外部新聞證據
- `external_evidence_url`：證據來源 URL
- `consistency_status`：一致性狀態
- `msci_flag`：MSCI 風險旗號（Green/Yellow/Orange/Red）
- `adjustment_score`：調整後風險分數

### Q7: 如何處理 API 限制？
A: Gemini API 有請求限制，若遇到錯誤：
- 檢查 `.env` 中的 `GEMINI_API_KEY`
- 確認 API quota 未用盡
- 適當延遲批次處理（每次間隔 5-10 秒）

### Q8: 為什麼有 Debug 檔案？
A: 若 JSON 解析失敗，系統會自動儲存原始回應至 `_debug_response.txt`，方便問題診斷。

---

## ⚠️ 注意事項

### 1. Token 成本
- 每次執行約消耗 25K-35K tokens
- 建議在開發階段使用已存在的檔案測試
- 生產環境監控 API 使用量

### 2. 執行時間
- 單次執行約 40-60 秒
- 主要時間花費在 Gemini API 呼叫
- 批次處理時注意總時間

### 3. 欄位格式
- 確保使用修正後的 Prompt
- 舊版 P2 檔案不符合新規範
- 建議刪除舊檔案後重新生成

### 4. 依賴檔案
必須先執行前置步驟：
- ✅ P1 JSON（AI 分析）
- ✅ 新聞 JSON（新聞爬蟲）
- ✅ MSCI 標準檔案

---

**文檔版本：** 1.0  
**最後更新：** 2026-01-15
