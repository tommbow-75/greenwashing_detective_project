# 新聞爬蟲程式碼結構說明

## 📁 檔案結構

```
news_search/
├── crawler_news.py          # 主程式（已重構）
├── sasb_keyword.json         # SASB 議題關鍵字
└── news_output/              # 輸出目錄
    ├── .gitkeep
    └── {year}_{code}_news.json
```

---

## 🔧 crawler_news.py 模組結構

### 1. 模組文檔與常數 (L1-28)

```python
"""
新聞爬蟲模組
提供從 P1 JSON 分析結果搜尋相關新聞的功能。
"""

# 模組常數
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_P1_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "temp_data", "prompt1_json"))
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "news_output")
COMPANY_MAP_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "static", "data", "tw_listed_companies.json"))
SASB_KEYWORD_PATH = os.path.join(SCRIPT_DIR, "sasb_keyword.json")

# API 設定
MAX_RETRIES = 3
RETRY_DELAY = 5
SEARCH_DELAY = 2
MAX_RESULTS_PER_TOPIC = 10
```

---

### 2. 輔助函數 (L31-158)

#### _load_company_map()
```python
def _load_company_map() -> Dict[str, str]:
    """載入上市公司代號對照表"""
```
- 讀取 `static/data/tw_listed_companies.json`
- 返回 {公司代碼: 公司名稱} 字典
- 錯誤處理：返回空字典

#### _load_sasb_keywords()
```python
def _load_sasb_keywords() -> Dict[str, List[str]]:
    """載入 SASB 議題關鍵字對照表"""
```
- 讀取 `news_search/sasb_keyword.json`
- 返回 {SASB議題: 關鍵字列表} 字典
- 錯誤處理：返回空字典

#### _get_keywords_from_sasb()
```python
def _get_keywords_from_sasb(sasb_topic: str, company_name: str, sasb_keywords: Dict) -> str:
    """從 SASB 關鍵字表生成搜尋關鍵字"""
```
- 獲取議題的前 3 個關鍵字
- 組合格式：`"{公司名稱} {議題} {關鍵字1} {關鍵字2} {關鍵字3}"`
- 若無關鍵字：`"{公司名稱} {議題}"`

#### _find_p1_json()
```python
def _find_p1_json(year: int, company_code: str, p1_dir: str = DEFAULT_P1_DIR) -> Optional[str]:
    """尋找 P1 JSON 檔案"""
```
- 嘗試標準檔名：`{year}_{company_code}_P1.json`
- 嘗試小寫：`{year}_{company_code}_p1.json`
- 嘗試 glob 搜尋：`{year}_{company_code}*.json`
- 返回完整路徑或 None

#### _is_date_in_year()
```python
def _is_date_in_year(date_str: str, target_year: int) -> bool:
    """檢查新聞發布日期是否在目標年份內"""
```
- 使用 `dateutil.parser` 解析日期字串
- 比對年份
- 錯誤處理：返回 False

---

### 3. 主要函數 search_news_for_report() (L161-360)

#### 函數簽名

```python
def search_news_for_report(
    year: int,
    company_code: str,
    p1_json_path: Optional[str] = None,
    force_regenerate: bool = False
) -> Dict[str, Any]:
```

#### 執行流程

```
┌────────────────────────┐
│ 1. 建立輸出目錄         │
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
│ 3. 尋找 P1 JSON        │
│  - _find_p1_json()     │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 4. 載入資源            │
│  - P1 JSON            │
│  - 公司對照表          │
│  - SASB 關鍵字        │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 5. 遍歷 P1 項目        │
│  └─ 對每個項目：      │
│     ├─ 生成 key_word  │
│     ├─ 設定 GNews     │
│     ├─ 三階段搜尋     │
│     ├─ 過濾年份       │
│     └─ 儲存結果       │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ 6. 儲存 JSON           │
│  - 統計資訊           │
│  - 回傳結果           │
└────────────────────────┘
```

#### key_word 三層級 Fallback

```python
# 層級 1: 優先使用 P1 提供的 key_word
key_word = item.get("key_word", "")

# 層級 2: 從 SASB 關鍵字表生成
if not key_word and topic:
    key_word = _get_keywords_from_sasb(topic, company_name, sasb_keywords)

# 層級 3: 基本組合
if not key_word:
    key_word = f"{company_name} {topic}"
```

#### 搜尋三階段策略

```python
# 策略 1: 使用完整關鍵字
news_results = google_news.get_news(key_word)

# 策略 2: 簡化關鍵字（取前3個詞）
if len(news_results) < 3:
    query2 = ' '.join(key_words_list[:3])
    news_results = google_news.get_news(query2)

# 策略 3: 公司名稱 + 主題
if len(news_results) < 2:
    query3 = f"{company_name} {topic}"
    news_results = google_news.get_news(query3)
```

#### 重試機制

```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        news_results = google_news.get_news(key_word)
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
        else:
            raise e
```

---

### 4. 命令列執行入口 (L363-385)

#### main()

```python
def main():
    """命令列執行的主函數"""
    year = input("請輸入年份 (預設 2024): ") or "2024"
    company_code = input("請輸入公司代碼 (預設 1102): ") or "1102"
    force = input("是否強制重新生成？(y/N): ").lower() == 'y'
    
    result = search_news_for_report(
        year=int(year),
        company_code=company_code,
        force_regenerate=force
    )
```

#### if __name__ == "__main__"

```python
if __name__ == "__main__":
    main()
```

---

## 🔄 資料流

### 完整執行流程

```
使用者調用
    ↓
┌──────────────────────────┐
│ search_news_for_report() │
└──────────┬───────────────┘
           ↓
      檔案已存在？
         ↙   ↘
      Yes    No
       ↓      ↓
    跳過    尋找 P1 JSON
    返回      ↓
          載入資源
              ↓
          遍歷 P1 項目
              ↓
       ┌──────┴──────┐
       ↓             ↓
   生成 key_word   設定 GNews
       ↓             ↓
   三階段搜尋    過濾年份
       └──────┬──────┘
              ↓
          儲存 JSON
              ↓
          返回結果
```

---

## 📊 資料結構

### 輸入

**P1 JSON 格式：**
```python
[
  {
    "company": "1102",
    "year": "2024",
    "sasb_topic": "溫室氣體排放",
    "key_word": "(選填) 亞泥 溫室氣體 SBTi"
  }
]
```

### 輸出

**函數回傳格式：**
```python
{
    'success': bool,
    'output_file': str,
    'news_count': int,
    'processed_items': int,
    'failed_items': int,
    'skipped': bool,
    'failure_details': [
        {'topic': str, 'reason': str}
    ]
}
```

**JSON 檔案格式：**
```python
[
  {
    "news_id": 1,
    "stock_code": "1102",
    "company_name": "亞泥",
    "sasb_topic": "溫室氣體排放",
    "search_query": "亞泥 溫室氣體 排放強度",
    "title": "新聞標題",
    "url": "https://...",
    "published_date": "Wed, 20 Nov 2024 08:00:00 GMT",
    "publisher": "news.cnyes.com"
  }
]
```

---

## 🛡️ 錯誤處理

### 異常捕獲層級

| 層級 | 位置 | 處理方式 |
|------|------|---------|
| **載入資源** | _load_company_map / _load_sasb_keywords | 返回空字典 |
| **尋找檔案** | _find_p1_json | 返回 None |
| **API 請求** | search_news_for_report | 重試 3 次，失敗則記錄並繼續 |
| **檔案儲存** | search_news_for_report | 返回錯誤 |

### 錯誤訊息示例

```python
{
    'success': False,
    'error': '找不到 P1 JSON 檔案: 2024_1102_P1.json'
}

{
    'success': False,
    'error': '讀取 P1 JSON 失敗: ...'
}

{
    'success': False,
    'error': '儲存檔案失敗: ...'
}
```

---

## 📝 設計模式

### 1. 單一職責原則 (SRP)
- `_load_company_map`: 只負責載入公司對照表
- `_load_sasb_keywords`: 只負責載入 SASB 關鍵字
- `_get_keywords_from_sasb`: 只負責生成關鍵字
- `search_news_for_report`: 負責流程編排

### 2. 開放封閉原則 (OCP)
- 透過 `force_regenerate` 參數擴展功能
- 不修改既有邏輯

### 3. Fallback 模式
- 三層級 key_word 生成
- 三階段搜尋策略
- 確保容錯性

---

## 🔑 關鍵設計決策

### 1. 為什麼使用私有函數（_前綴）？
- 表示內部使用，不建議外部直接調用
- 保持 API 清晰簡潔

### 2. 為什麼移除時間戳？
- 與 P1/P2/P3 命名規範一致
- 方便後續模組讀取
- 支援檔案存在性檢查

### 3. 為什麼使用三層級 fallback？
- P1 JSON 可能缺少 key_word 欄位
- 確保即使無 key_word 也能執行
- 提供多種備援方案

### 4. 為什麼單一失敗不中斷流程？
- 提高整體成功率
- 部分結果總比完全失敗好
- 符合實際使用需求

---

**文檔版本：** 1.0  
**最後更新：** 2026-01-14
