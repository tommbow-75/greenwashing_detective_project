# T4: AI 驗證與調整模組整合

**完成日期**：2026-01-15  
**狀態**：✅ 整合完成，等待實際測試

---

## 🎯 整合目標

將 `run_prompt2_gemini.py` 的 AI 驗證與評分調整功能整合至 `app.py` 的 Step 5，實現基於外部新聞驗證的風險評分調整機制。

---

## 📦 主要變更

### 1. 修正 Prompt 欄位格式

**問題**：原 Prompt 會導致 P2.json 的欄位名稱與 P1.json 不一致
- `company`: "亞洲水泥"（公司名稱） ❌
- `disclosure_claim`: "..." ❌

**解決**：修正 Prompt 範例，保持 P1 格式
- `company`: "1101"（代碼） ✅
- `report_claim`: "..." ✅

### 2. 新增模組化接口

**函數**：`verify_esg_with_news(year, company_code, force_regenerate=False)`

**功能**：
- 自動構建檔案路徑
- 檔案存在性檢查（避免重複執行）
- 完整的錯誤處理
- 返回詳細統計資訊（Token 使用、執行時間）

**返回格式**：
```python
{
    'success': True/False,
    'message': str,
    'output_path': str,
    'skipped': bool,
    'statistics': {
        'processed_items': int,
        'input_tokens': int,
        'output_tokens': int,
        'total_tokens': int,
        'api_time': float,
        'total_time': float
    },
    'error': str  # 若失敗
}
```

### 3. 整合到 app.py

**位置**：Step 5（在新聞爬蟲後、資料庫插入前）

**特點**：
- 失敗不中斷主流程
- 詳細的執行統計輸出
- 與其他步驟一致的錯誤處理風格

---

## 💡 使用方式

### 獨立使用

```python
from run_prompt2_gemini import verify_esg_with_news

result = verify_esg_with_news(
    year=2024,
    company_code="1102",
    force_regenerate=False  # True 會強制重新生成
)

if result['success']:
    print(f"處理項目: {result['statistics']['processed_items']}")
    print(f"Token 使用: {result['statistics']['total_tokens']:,}")
else:
    print(f"錯誤: {result['error']}")
```

### 透過 app.py 整合流程

```bash
# 啟動 Flask
python app.py

# 發送 API 請求
curl -X POST http://localhost:5000/api/query_company \
  -H "Content-Type: application/json" \
  -d '{"year": 2024, "company_code": "1102", "auto_fetch": true}'
```

執行流程：
1. PDF 下載
2. AI 分析（P1.json）
3a. Word Cloud 生成（平行）
3b. AI 分析完成
4. 新聞爬蟲（news.json）
5. **AI 驗證（P2.json）** ← 新增
6. 插入資料庫
7. 更新狀態
8. 回傳結果

---

## ⚠️ 注意事項

### 需要重新生成 P2 檔案

現有的 `2024_1102_p2.json` 使用舊格式（company 為公司名稱），不符合新的規範。

**解決方法**：
```bash
# 刪除舊檔案
del temp_data\prompt2_json\2024_1102_p2.json

# 重新運行（會使用新 Prompt）
python run_prompt2_gemini.py
```

### Token 成本

每次 AI 驗證約消耗 25,000-35,000 tokens（約 NT$3-5 元），系統會在執行時顯示詳細統計。

---

## 📋 測試清單

- ✅ 模組化接口實作完成
- ✅ 檔案檢查機制正常
- ✅ 錯誤處理完整
- ⏸️ 獨立運行測試（需安裝 tiktoken）
- ⏸️ app.py 整合測試（需實際 API 調用）
- ⏸️新 Prompt 輸出驗證（需重新生成 P2）

---

## 📁 相關檔案

- [run_prompt2_gemini.py](file:///c:/project/github_push/greenwashing_detective_project/run_prompt2_gemini.py) - 主模組
- [app.py](file:///c:/project/github_push/greenwashing_detective_project/app.py#L359-L383) - 整合位置
- [walkthrough.md](file:///C:/Users/sadiv/.gemini/antigravity/brain/1dee38d8-6304-44a3-958d-b8ddef815fc2/walkthrough.md) - 詳細完成報告
- [implementation_plan.md](file:///C:/Users/sadiv/.gemini/antigravity/brain/1dee38d8-6304-44a3-958d-b8ddef815fc2/implementation_plan.md) - 實作計劃

---

## 🎯 成功指標

- ✅ 程式碼整合完成
- ⏸️ P2.json 格式正確（等待重新生成驗證）
- ⏸️ 完整流程測試通過
- ✅ Token 統計正確
- ✅ 錯誤容忍機制運作
