# Word Cloud 模組使用範例

## 📖 目錄

1. [方式 1：獨立運行](#方式-1獨立運行)
2. [方式 2：模組調用](#方式-2模組調用)
3. [方式 3：在 app.py 中的整合](#方式-3在-apppy-中的整合)

---

## 方式 1：獨立運行

### 命令列執行

```bash
cd c:\project\github_push\greenwashing_detective_project
python word_cloud/word_cloud.py
```

### 互動式輸入

```
=== ESG 報告書文字雲生成器 ===

請輸入年份 (預設 2024): 2024
請輸入公司代碼 (預設 1102): 1314
是否強制重新生成？(y/N): n
```

### 輸出範例

```
找到檔案: c:\...\temp_data\esgReport\2024_1314_中石化_永續報告書.pdf
ℹ️ 文字雲 JSON 已存在，跳過生成 (耗時: 0.05 秒)

==================================================
ℹ️ 文字雲已存在: c:\...\word_cloud\wc_output\2024_1314_wc.json
📊 關鍵字數量: 100
🔝 前 10 個關鍵字: 中石化, 智慧, 溝通, 開發, 環境, 生產, 價值, 前瞻, 關懷, 工業
==================================================
```

---

## 方式 2：模組調用

### 基本使用

```python
from word_cloud.word_cloud import generate_wordcloud

# 自動搜尋 PDF
result = generate_wordcloud(year=2024, company_code="1314")

# 檢查結果
if result['success']:
    print(f"✅ 成功：{result['output_file']}")
    print(f"📊 關鍵字數量：{result['word_count']}")
    print(f"🔝 前 10 個：{result['top_keywords']}")
else:
    print(f"❌ 失敗：{result['error']}")
```

### 指定 PDF 路徑

```python
result = generate_wordcloud(
    year=2024,
    company_code="1314",
    pdf_path="temp_data/esgReport/2024_1314_中石化_永續報告書.pdf"
)
```

### 強制重新生成

```python
result = generate_wordcloud(
    year=2024,
    company_code="1314",
    force_regenerate=True  # 忽略現有檔案，強制重新生成
)
```

### 回傳格式

```python
{
    'success': True,
    'output_file': 'word_cloud/wc_output/2024_1314_wc.json',
    'word_count': 100,
    'top_keywords': ['中石化', '智慧', '溝通', ...],
    'skipped': False  # True 表示使用現有檔案
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
  "company_code": "1314",
  "auto_fetch": true
}
```

### 執行流程

```
1. 檢查資料庫 (Step 1)
    ↓ 資料不存在
2. 下載 PDF (Step 2)
    ↓ 下載成功
3a. Word Cloud 生成 ┐
                     ├─ 平行執行
3b. AI 分析         ┘
    ↓ 兩者完成
4. 存入資料庫 (Step 4)
    ↓
5. 回傳結果
```

### 後端日誌

```
🚀 啟動平行處理：Word Cloud 與 AI 分析
找到檔案: ...2024_1314_中石化_永續報告書.pdf
ℹ️ 文字雲 JSON 已存在，跳過生成 (耗時: 0.05 秒)
ℹ️ Word Cloud 已存在，跳過生成
✅ AI 分析完成
```

### 前端讀取文字雲

```javascript
// 前端 JavaScript
const wordcloudUrl = `/word_cloud/wc_output/${year}_${companyCode}_wc.json`;

fetch(wordcloudUrl)
    .then(response => response.json())
    .then(data => {
        // data = [{name: "永續", value: 156}, ...]
        renderWordCloud(data);
    });
```

---

## 🔧 進階用法

### 批次處理多家公司

```python
from word_cloud.word_cloud import generate_wordcloud

companies = ["1101", "1102", "1314", "2330"]
year = 2024

for company_code in companies:
    print(f"\n處理：{company_code}")
    result = generate_wordcloud(year, company_code)
    
    if result['success']:
        if result['skipped']:
            print(f"  ⏭️ 已存在，跳過")
        else:
            print(f"  ✅ 生成成功：{result['word_count']} 個關鍵字")
    else:
        print(f"  ❌ 失敗：{result['error']}")
```

### 錯誤處理

```python
result = generate_wordcloud(year=2024, company_code="9999")

if not result['success']:
    error = result.get('error', '未知錯誤')
    
    if 'PDF 檔案不存在' in error:
        print("請先下載 PDF")
    elif 'PDF 文字提取失敗' in error:
        print("PDF 可能已損壞")
    elif '儲存 JSON 失敗' in error:
        print("磁碟空間不足或權限問題")
    else:
        print(f"其他錯誤：{error}")
```

---

## 📊 輸出檔案位置

| 項目 | 路徑 |
|------|------|
| **JSON 檔案** | `word_cloud/wc_output/{year}_{company_code}_wc.json` |
| **前端 URL** | `/word_cloud/wc_output/{year}_{company_code}_wc.json` |
| **範例** | `word_cloud/wc_output/2024_1314_wc.json` |

---

## 🔍 常見問題

### Q1: 為什麼第二次執行很快？
A: 加入了檔案存在性檢查機制，若 JSON 已存在且格式正確，直接返回（< 0.1 秒）。

### Q2: 如何強制重新生成？
A: 設定 `force_regenerate=True` 參數。

### Q3: Word Cloud 失敗會影響主流程嗎？
A: 不會。Word Cloud 是非必要功能，失敗只會記錄日誌，不影響 AI 分析和資料庫儲存。

### Q4: 支援哪些檔案格式？
A: 僅支援 PDF 格式的 ESG 報告書。

### Q5: 如何自訂關鍵字數量？
A: 目前固定為 100 個，未來可加入參數支援。
