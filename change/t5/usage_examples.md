# T5: 使用範例文檔

## 📖 獨立模組測試

### 基本使用

```python
from pplx_api import verify_evidence_sources

# 驗證 2024 年亞泥 (1102) 的證據來源
result = verify_evidence_sources(
    year=2024,
    company_code="1102",
    force_regenerate=False
)

# 檢查結果
if result['success']:
    print(f"✅ 驗證成功")
    print(f"輸出檔案: {result['output_path']}")
    
    # 顯示統計
    stats = result['statistics']
    print(f"\n統計資訊:")
    print(f"  處理項目: {stats['processed_items']}")
    print(f"  有效 URL: {stats['verified_count']}")
    print(f"  更新 URL: {stats['updated_count']}")
    print(f"  失敗項目: {stats['failed_count']}")
    print(f"  執行時間: {stats['execution_time']:.2f} 秒")
else:
    print(f"❌ 驗證失敗: {result['error']}")
```

**預期輸出**:
```
📖 讀取檔案: temp_data/prompt2_json/2024_1102_P2.json

開始驗證 26 筆資料...

[1/26] 處理: 1102 2024 - E
  原始 URL: https://news.cnyes.com/...
  ✅ URL 有效 (狀態碼: 200)

[2/26] 處理: 1102 2024 - E
  原始 URL: https://esg.gvm.com.tw/...
  ❌ URL 失效，開始尋找替代...
  🔍 搜尋替代 URL: 1102 2024 ESG 亞泥SBTi第一階段目標提前達陣...
  ✅ Perplexity 找到有效 URL: https://news.google.com/...
  🔄 已更新為新 URL

...

✅ 處理完成！
📊 統計結果:
  - 總共處理: 26 筆
  - 有效 URL: 18 筆
  - 已更新 URL: 5 筆
  - 失敗: 3 筆
📁 輸出檔案: temp_data/prompt3_json/2024_1102_P3.json
```

---

### 強制重新驗證

```python
# 即使 P3 檔案已存在，也強制重新驗證
result = verify_evidence_sources(
    year=2024,
    company_code="1102",
    force_regenerate=True  # ← 強制重建
)

print(f"Skipped: {result.get('skipped', False)}")  # False
print(f"Time: {result['statistics']['execution_time']:.2f}s")  # ~45 秒
```

---

### 檔案快取測試

```python
# 第一次執行 (完整驗證)
result1 = verify_evidence_sources(2024, "1102", force_regenerate=True)
time1 = result1['statistics']['execution_time']
print(f"第一次執行: {time1:.2f} 秒")  # ~45 秒

# 第二次執行 (檔案已存在，跳過)
result2 = verify_evidence_sources(2024, "1102", force_regenerate=False)
time2 = result2['statistics']['execution_time']
print(f"第二次執行: {time2:.4f} 秒")  # < 0.5 秒
print(f"已跳過: {result2['skipped']}")  # True
```

---

## 🌐 Flask API 整合測試

### 完整流程測試

#### 1. 準備環境

```bash
# 確保 .env 有 API Key
echo PERPLEXITY_API_KEY=your_key_here >> .env

# 確保有測試用 P2 檔案
ls temp_data/prompt2_json/2024_1102_P2.json
```

#### 2. 啟動 Flask

```bash
python app.py
```

預期輸出:
```
 * Running on http://127.0.0.1:5000
```

#### 3. 發送 API 請求

**方法 A: 使用 curl**
```bash
curl -X POST http://localhost:5000/api/query_company \
  -H "Content-Type: application/json" \
  -d '{"year": 2024, "company_code": "1102", "auto_fetch": true}'
```

**方法 B: 使用 PowerShell**
```powershell
$body = @{
    year = 2024
    company_code = "1102"
    auto_fetch = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/query_company" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### 4. 觀察執行日誌

```
--- Step 1: 查詢資料庫 ---
...

--- Step 5: AI 驗證與評分調整 ---
✅ AI 驗證完成
   處理項目: 26
   Token 使用: 28,543
   執行時間: 15.32 秒

--- Step 6: 來源可靠度驗證 ---  ← 新增步驟
📖 讀取檔案: temp_data/prompt2_json/2024_1102_P2.json

開始驗證 26 筆資料...
[1/26] 處理: 1102 2024 - E
  ✅ URL 有效 (狀態碼: 200)
...

✅ 來源驗證完成
   輸出檔案: temp_data/prompt3_json/2024_1102_P3.json
   處理項目: 26
   有效 URL: 18
   更新 URL: 5
   失敗項目: 3
   Perplexity 調用: 8 次
   執行時間: 45.32 秒

--- Step 7: 插入分析結果至資料庫 ---
...
```

---

## 🔍 檔案格式驗證

### P3 輸出檔案檢查

```python
import json

# 讀取 P3 檔案
with open("temp_data/prompt3_json/2024_1102_P3.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

# 驗證必要欄位
first_item = data[0]
required_fields = [
    'company', 'year', 'esg_category', 'SASB_topic',
    'report_claim', 'risk_score', 
    'external_evidence', 'external_evidence_url',
    'consistency_status', 'MSCI_flag', 'adjustment_score',
    'is_verified'  # ← T5 新增欄位
]

for field in required_fields:
    assert field in first_item, f"缺少欄位: {field}"
    print(f"✅ {field}: {first_item.get(field, 'N/A')[:50]}")

# 檢查 is_verified 值
verified_values = set(item['is_verified'] for item in data)
print(f"\nis_verified 可能值: {verified_values}")
# 預期: {'True', 'Failed'}
```

---

## 📊 統計資訊解讀

### 返回結果解析

```python
result = verify_evidence_sources(2024, "1102")

stats = result['statistics']

# 總處理項目數 (應等於 P2.json 的項目數)
total = stats['processed_items']  # 例如: 26

# 原 URL 有效數 (無需修改)
verified = stats['verified_count']  # 例如: 18

# 已更新為新 URL 數 (Perplexity 找到替代)
updated = stats['updated_count']  # 例如: 5

# 驗證失敗數 (無法找到有效 URL)
failed = stats['failed_count']  # 例如: 3

# 驗證等式
assert total == verified + updated + failed
print(f"總計: {verified} + {updated} + {failed} = {total} ✅")

# API 調用次數 (僅針對失效 URL)
pplx_calls = stats['perplexity_calls']  # 例如: 8
print(f"Perplexity API 調用: {pplx_calls} 次")
# 注意: pplx_calls ≈ updated + failed (可能略多，因重試機制)
```

---

## 🛠️ 故障排除

### 常見錯誤處理

#### 錯誤 1: 輸入檔案不存在

```python
result = verify_evidence_sources(2024, "9999")
# {'success': False, 'error': 'Input file not found'}
```

**解決**: 確保先執行 Step 5 (AI 驗證) 產生 P2.json

---

#### 錯誤 2: Perplexity API Key 未設定

```bash
# 檢查 .env
cat .env | grep PERPLEXITY_API_KEY
```

**解決**: 在 `.env` 添加
```
PERPLEXITY_API_KEY=your_actual_key
```

---

#### 錯誤 3: 模組導入失敗

```python
# ModuleNotFoundError: No module named 'perplexity'
```

**解決**:
```bash
pip install perplexity-sdk
# 或
uv add perplexity-sdk
```

---

## 🎯 最佳實踐

### 1. 生產環境使用

```python
# 建議添加重試機制
import time

def verify_with_retry(year, code, max_retries=3):
    for attempt in range(max_retries):
        result = verify_evidence_sources(year, code)
        if result['success']:
            return result
        print(f"重試 {attempt + 1}/{max_retries}...")
        time.sleep(5)
    return result
```

### 2. 批次處理

```python
companies = ["1101", "1102", "2330", "2317"]

for code in companies:
    print(f"\n處理公司: {code}")
    result = verify_evidence_sources(2024, code)
    if result['success']:
        print(f"  ✅ 完成: {result['output_path']}")
    else:
        print(f"  ❌ 失敗: {result['error']}")
```

### 3. 成本控制

```python
# 避免重複調用 Perplexity API
result = verify_evidence_sources(2024, "1102", force_regenerate=False)

# 檢查 API 調用次數
pplx_calls = result['statistics'].get('perplexity_calls', 0)
estimated_cost = pplx_calls * 0.001  # 假設每次調用 $0.001
print(f"預估成本: ${estimated_cost:.3f}")
```
