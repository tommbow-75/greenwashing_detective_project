# T5: 程式碼結構文檔

## 📁 檔案變更概覽

### 修改檔案

#### 1. pplx_api.py
**位置**: 專案根目錄  
**變更行數**: +150 行

**新增函數**: `verify_evidence_sources(year, company_code, force_regenerate=False)`

**功能區塊**:

```python
def verify_evidence_sources(year, company_code, force_regenerate=False):
    """
    模組化接口函數 - T5 整合核心
    
    流程:
    1. 構建檔案路徑 (P2 輸入, P3 輸出)
    2. 檢查輸入檔案存在性
    3. 檢查輸出檔案 (skip if exists)
    4. 讀取 P2 JSON
    5. 逐筆驗證 URL:
       - verify_single_url() → 驗證原始 URL
       - find_alternative_url() → Perplexity 搜尋替代
    6. 寫入 P3 JSON (添加 is_verified 欄位)
    7. 返回統計資訊
    """
```

**依賴函數** (已存在，未修改):
- `verify_single_url(url)` - LINE 17-37
- `search_with_perplexity(query)` - LINE 40-60
- `find_alternative_url(company, year, evidence_summary, original_url)` - LINE 62-79

**移除依賴**:
- `from googleapiclient.discovery import build` (LINE 5 刪除)

---

#### 2. app.py
**位置**: 專案根目錄  
**變更行數**: +29 行 (Step 6 插入)

**插入位置**: LINE 385-413 (Step 5 後)

**整合代碼**:

```python
# Step 6: 來源可靠度驗證 ✨ NEW
print("\n--- Step 6: 來源可靠度驗證 ---")
try:
    from pplx_api import verify_evidence_sources
    
    pplx_result = verify_evidence_sources(
        year=year,
        company_code=company_code,
        force_regenerate=False
    )
    
    if pplx_result['success']:
        if pplx_result.get('skipped'):
            print(f"ℹ️ 來源驗證結果已存在，跳過生成")
        else:
            stats = pplx_result['statistics']
            print(f"✅ 來源驗證完成")
            print(f"   輸出檔案: {pplx_result['output_path']}")
            print(f"   處理項目: {stats['processed_items']}")
            print(f"   有效 URL: {stats['verified_count']}")
            print(f"   更新 URL: {stats['updated_count']}")
            print(f"   失敗項目: {stats['failed_count']}")
            print(f"   Perplexity 調用: {stats['perplexity_calls']} 次")
            print(f"   執行時間: {stats['execution_time']:.2f} 秒")
    else:
        print(f"⚠️ 來源驗證失敗：{pplx_result.get('error')}（不影響主流程）")
except Exception as e:
    print(f"⚠️ 來源驗證發生錯誤: {str(e)}（不影響主流程）")
```

**步驟編號更新**:
- LINE 385: Step 6 → Step 7 (插入資料庫)
- LINE 403: Step 7 → Step 8 (更新狀態)
- LINE 406: Step 8 → Step 9 (查詢回傳)

---

### 刪除內容

#### pplx_api/ 資料夾
**原因**: 與 `pplx_api.py` 名稱衝突，且完全未被使用

**刪除檔案**:
- `pplx_api/__init__.py`
- `pplx_api/config.py` (舊配置類，未使用)
- `pplx_api/esg_news_system.json` (舊配置檔，未使用)

---

## 🔄 資料流圖

```
P2.json (Step 5 輸出)
    ↓
【Step 6: verify_evidence_sources()】
    ↓
  讀取 P2
    ↓
  逐筆驗證 URL (26 筆)
    ├─ verify_single_url() ← 驗證原 URL
    │   ├─ 成功 → is_verified: "True"
    │   └─ 失敗 ↓
    └─ find_alternative_url() ← Perplexity 搜尋
        ├─ 找到 → 更新 URL + is_verified: "True"  
        └─ 失敗 → is_verified: "Failed"
    ↓
  寫入 P3.json
    ↓
  返回統計資訊
    ↓
【Step 7: 插入資料庫】
```

---

## 📊 函數調用關係圖

```
app.py: query_company()
    └─ Step 6: 調用 pplx_api.verify_evidence_sources()
           │
           ├─ 讀取 P2.json
           │
           ├─ for each item:
           │    ├─ verify_single_url(url)
           │    │    └─ requests.get() → 檢查 HTTP 狀態
           │    │
           │    └─ (if failed) find_alternative_url()
           │         └─ search_with_perplexity(query)
           │              └─ Perplexity API 調用
           │
           └─ 寫入 P3.json + 返回統計
```

---

## 🔧 核心邏輯

### URL 驗證邏輯

```python
for item in P2_data:
    url = item["external_evidence_url"]
    
    # 步驟 1: 驗證原始 URL
    result = verify_single_url(url)
    
    if result["is_valid"]:
        # 原 URL 有效
        item["is_verified"] = "True"
        verified_count += 1
    else:
        # 步驟 2: 使用 Perplexity 搜尋替代
        new_url = find_alternative_url(company, year, evidence, url)
        
        if new_url != url:
            # 找到替代 URL
            item["external_evidence_url"] = new_url
            item["is_verified"] = "True"
            updated_count += 1
        else:
            # 無法找到替代
            item["is_verified"] = "Failed"
            failed_count += 1
```

### 檔案檢查邏輯

```python
output_file = f"temp_data/prompt3_json/{year}_{company_code}_P3.json"

# 若檔案已存在且未強制重建
if os.path.exists(output_file) and not force_regenerate:
    return {
        'success': True,
        'skipped': True,
        'statistics': {'execution_time': 0.001}
    }
```

---

## 📈 效能特性

### 執行時間估算

**假設 26 筆資料**:
- **驗證成功 (18 筆)**: ~0.5 秒/筆 = 9 秒
- **需 Perplexity (8 筆)**: ~5 秒/筆 = 40 秒
- **總計**: ~45-50 秒

### 優化機制

1. **檔案快取**: 檔案已存在時 < 0.5 秒返回
2. **並行潛力**: 目前為順序處理，可改為 ThreadPoolExecutor 加速
3. **錯誤容忍**: 單筆失敗不中斷整體流程

---

## 🎯 與 T2-T4 設計一致性

所有整合模組使用統一設計模式:

| 特性 | T2 (Word Cloud) | T3 (News) | T4 (Verify) | T5 (Source) |
|------|----------------|-----------|------------|------------|
| **接口函數** | `generate_wordcloud()` | `search_news_for_report()` | `verify_esg_with_news()` | `verify_evidence_sources()` |
| **force_regenerate** | ✅ | ✅ | ✅ | ✅ |
| **檔案檢查** | ✅ | ✅ | ✅ | ✅ |
| **統計返回** | ✅ | ✅ | ✅ | ✅ |
| **錯誤容忍** | ✅ | ✅ | ✅ | ✅ |
| **app.py 整合** | Step 3a | Step 4 | Step 5 | Step 6 |
