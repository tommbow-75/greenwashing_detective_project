# Word Cloud 程式碼結構說明

## 📁 檔案結構

```
word_cloud/
├── word_cloud.py          # 主程式
├── esg_dict.txt           # ESG 專業詞典
├── fuzzy_dict.txt         # 模糊詞典
├── stopword_list.txt      # 停用詞列表
└── wc_output/             # 輸出目錄
    └── {year}_{code}_wc.json
```

---

## 🔧 word_cloud.py 模組結構

### 1. 模組文檔與常數 (L1-30)

```python
"""
Word Cloud 文字雲生成模組
提供從 ESG 報告書 PDF 生成文字雲 JSON 的功能
"""

# 模組常數
WORD_CLOUD_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = WORD_CLOUD_DIR
OUTPUT_DIR = os.path.join(WORD_CLOUD_DIR, "wc_output")
PDF_DIR = os.path.abspath(os.path.join(WORD_CLOUD_DIR, "..", "temp_data", "esgReport"))
```

**用途：**
- 提供模組說明
- 定義全域路徑常數
- 避免硬編碼路徑

---

### 2. 輔助函數 (L32-90)

#### _extract_text_from_pdf()

```python
def _extract_text_from_pdf(pdf_path: str) -> str:
    """讀取 PDF 並提取文字"""
```

**功能：**
- 使用 pdfplumber 讀取 PDF
- 逐頁提取文字
- 每 10 頁顯示進度
- 錯誤處理：返回空字串

#### _load_dictionaries()

```python
def _load_dictionaries() -> None:
    """載入自訂詞典"""
```

**功能：**
- 載入 esg_dict.txt
- 載入 fuzzy_dict.txt
- 使用 jieba.load_userdict()
- 錯誤處理：使用預設斷詞

#### _load_stopwords()

```python
def _load_stopwords() -> set:
    """載入停用詞"""
```

**功能：**
- 讀取 stopword_list.txt
- 返回停用詞集合
- 錯誤處理：返回空集合

---

### 3. 主函數 generate_wordcloud() (L93-200)

#### 函數簽名

```python
def generate_wordcloud(
    year: int,
    company_code: str,
    pdf_path: Optional[str] = None,
    force_regenerate: bool = False
) -> Dict
```

#### 執行流程

```
┌────────────────────────┐
│ 1. 建立輸出路徑         │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 2. 檔案存在性檢查       │ ← force_regenerate=False
│  - 檔案存在？          │
│  - 格式正確？          │
│  - Yes: return skipped │
└──────────┬─────────────┘
           ↓ No
┌────────────────────────┐
│ 3. 尋找 PDF 檔案        │
│  - pdf_path 已提供？   │
│  - 否: glob 搜尋       │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 4. 提取 PDF 文字        │
│  - _extract_text...()  │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 5. 載入詞典和停用詞     │
│  - _load_dictionaries()│
│  - _load_stopwords()   │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 6. 斷詞並過濾          │
│  - jieba.lcut()        │
│  - 長度 >= 2           │
│  - 排除停用詞          │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 7. 計算字頻            │
│  - Counter()           │
│  - most_common(100)    │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 8. 生成 JSON           │
│  - [{name, value}, ...]│
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 9. 儲存檔案            │
│  - json.dump()         │
│  - return success      │
└────────────────────────┘
```

#### 檔案檢查邏輯 (重要)

```python
# === 檔案存在性檢查 ===
if not force_regenerate and os.path.exists(output_path):
    try:
        # 讀取並驗證格式
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # 驗證：是否為列表？長度 > 0？
        if isinstance(existing_data, list) and len(existing_data) > 0:
            # 驗證：前 5 個元素是否包含 name 和 value？
            if all('name' in item and 'value' in item for item in existing_data[:5]):
                # 格式正確，跳過生成
                return {
                    'success': True,
                    'skipped': True,
                    ...
                }
    except (json.JSONDecodeError, KeyError, IOError, TypeError):
        # 檔案損壞，繼續生成
        print("⚠️ 現有檔案格式錯誤，將重新生成")
```

**設計考量：**
1. 僅檢查前 5 個元素（效能優化）
2. 多種異常處理（JSON 解析、鍵值錯誤、I/O 錯誤）
3. 損壞檔案自動重新生成

---

### 4. 命令列執行入口 (L203-230)

#### main() 函數

```python
def main():
    """命令列執行的主函數"""
    year = input("請輸入年份 (預設 2024): ").strip() or "2024"
    company_code = input("請輸入公司代碼 (預設 1102): ").strip() or "1102"
    force = input("是否強制重新生成？(y/N): ").strip().lower() == 'y'
    
    result = generate_wordcloud(int(year), company_code, force_regenerate=force)
    
    # 顯示結果
    ...
```

#### if __name__ == "__main__"

```python
if __name__ == "__main__":
    main()
```

**功能：**
- 支援互動式執行
- 提供友善的使用者介面
- 格式化輸出結果

---

## 🔄 資料流

### 完整資料流程圖

```
使用者調用
    ↓
┌──────────────────────┐
│ generate_wordcloud() │
└──────────┬───────────┘
           ↓
    檔案已存在？
       ↙   ↘
    Yes    No
     ↓      ↓
  跳過    尋找 PDF
  返回      ↓
        提取文字 (_extract_text_from_pdf)
            ↓
        載入詞典 (_load_dictionaries)
            ↓
        載入停用詞 (_load_stopwords)
            ↓
        斷詞 (jieba.lcut)
            ↓
        過濾 (長度、停用詞)
            ↓
        計算字頻 (Counter)
            ↓
        取前 100 個
            ↓
        生成 JSON
            ↓
        儲存檔案
            ↓
        返回結果
```

---

## 📊 資料結構

### 輸入

```python
{
    'year': int,              # 必填
    'company_code': str,      # 必填
    'pdf_path': str | None,   # 選填
    'force_regenerate': bool  # 選填，預設 False
}
```

### 輸出

```python
{
    'success': bool,        # 是否成功
    'output_file': str,     # JSON 檔案路徑
    'word_count': int,      # 關鍵字數量
    'top_keywords': list,   # 前 10 個關鍵字
    'skipped': bool,        # 是否跳過生成
    'error': str            # 錯誤訊息（可選）
}
```

### JSON 檔案格式

```python
[
    {
        "name": str,   # 關鍵字
        "value": int   # 出現次數
    },
    ...  # 共 100 個
]
```

---

## 🛡️ 錯誤處理

### 異常捕獲層級

| 層級 | 位置 | 處理方式 |
|------|------|---------|
| **檔案讀取** | _extract_text_from_pdf | 返回空字串 |
| **詞典載入** | _load_dictionaries | 使用預設斷詞 |
| **停用詞載入** | _load_stopwords | 返回空集合 |
| **JSON 驗證** | generate_wordcloud | 繼續生成 |
| **檔案儲存** | generate_wordcloud | 返回錯誤 |

### 錯誤訊息示例

```python
{
    'success': False,
    'error': '找不到符合格式的 PDF 檔案: ...'
}

{
    'success': False,
    'error': 'PDF 文字提取失敗'
}

{
    'success': False,
    'error': '儲存 JSON 失敗: [Errno 13] Permission denied'
}
```

---

## 📝 設計模式

### 1. 單一職責原則 (SRP)
- `_extract_text_from_pdf`: 只負責PDF處理
- `_load_dictionaries`: 只負責詞典載入
- `_load_stopwords`: 只負責停用詞載入
- `generate_wordcloud`: 負責流程編排

### 2. 開放封閉原則 (OCP)
- 透過 `force_regenerate` 參數擴展功能
- 不修改既有邏輯

### 3. 依賴反轉原則 (DIP)
- 使用常數定義路徑，方便測試和部署

---

## 🔑 關鍵設計決策

### 1. 為什麼使用私有函數（_前綴）？
- 表示內部使用，不建議外部直接調用
- 保持 API 清晰簡潔

### 2. 為什麼設定 100 個關鍵字？
- 平衡資訊量和可讀性
- 前端文字雲顯示限制

### 3. 為什麼檔案檢查只驗證前 5 個元素？
- 效能考量（避免讀取整個大檔案）
- 99% 情況足以判斷格式正確性

### 4. 為什麼不使用 async/await？
- jieba 和 pdfplumber 不支援非同步
- threading 對 I/O 密集型任務已足夠

---

## 📐 效能分析

### 時間複雜度

| 步驟 | 複雜度 | 說明 |
|------|--------|------|
| PDF 讀取 | O(n) | n = 頁數 |
| 斷詞 | O(m) | m = 字數 |
| 字頻統計 | O(m) | Counter 內部使用 hash |
| 排序 | O(k log k) | k = 不重複字數 |
| **總計** | **O(n + m + k log k)** | |

### 空間複雜度

| 項目 | 空間 |
|------|------|
| PDF 文字 | 約 50-100 MB |
| 斷詞結果 | 約 100-200 MB |
| 字頻統計 | 約 10-20 MB |
| **峰值** | **約 200-300 MB** |

---

**文檔版本：** 1.0  
**最後更新：** 2026-01-14
