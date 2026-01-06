# Greenwashing Detective Project

## 一、 下載 GitHub Desktop
請先至官網下載並安裝 [GitHub Desktop](https://desktop.github.com/)。

## 二、 把專案領回家 (Clone)
1. 打開 **GitHub Desktop** 並登入你的帳號。
2. 點擊 `File` > `Clone Repository`。
3. 選取 `greenwashing_detective_project`，並選擇本地端的存放路徑。
4. **注意：** 資料夾路徑盡量**不要包含中文**，以避免程式執行時報錯。

## 三、 檔案對應說明
以下為專案主要檔案與功能對照：

* **資料庫服務：** `db_service.py` (pymysql)
* **主程式入口：** `app.py` (flask)
* **AI 介面：**
    * `gemini_api.py` (Gemini)
    * `pplx_api.py` (Perplexity)
* **爬蟲程式：** `crawler_esgReport`
* **前端網頁：**
    * **HTML:** `/templates/index.html`
    * **CSS:** `/static/css/style.css`
    * **JS:** `/static/js/script.js`

---

## 四、 工作步驟 (避免衝突)
為了確保多人協作順暢，請嚴格遵守以下流程：

1.  **同步進度：** 開工前先點擊 **Fetch origin / Pull**，確保本地端是最新版本。
2.  **建立分支：** 點擊 `Current Branch` > `New Branch`。
    * *命名格式建議：* `功能名稱_版本` (例如：`gemini_api_v2`)
3.  **提交變更：** 程式完成後，在 GitHub Desktop 進行 **Commit** 並點擊 **Publish branch**。
4.  **發起合併：** 回到 GitHub 網頁版點擊 **Compare & pull request**，並簡述修改內容。
5.  **完成：** 待管理員確認無誤後，即可進行合併（Merge）。

# process flowchart

```mermaid
flowchart TD
    %% --- 樣式定義 ---
    linkStyle default stroke:#000,stroke-width:1px;
    classDef start_end fill:#f2d08a,stroke:#333,stroke-width:1px,color:#000;
    classDef process fill:#eee,stroke:#999,stroke-width:1px,color:#333;
    classDef decision fill:#fff4dd,stroke:#d4a017,stroke-width:2px,color:#000;
    classDef program fill:#034f4f,stroke:#333,stroke-width:1px,color:#fff;
    classDef gemini fill:#68f4cd,stroke:#68f4cd,stroke-width:1px,color:#333;
    classDef pymysql fill:#6a906d,stroke:#6a906d,stroke-width:1px,color:#333;
    classDef pplx fill:#dbc9ef,stroke:#dbc9ef,stroke-width:1px,color:#333;
    classDef db fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#000;
    classDef outputData fill:#fff3e0,stroke:#ff9800,stroke-dasharray: 5 5,color:#000;

    %% --- 泳道 1: Frontend ---
    subgraph UI [使用者互動層]
        Start(["index.html<br/>Dashboard"]):::start_end
        Input["User Input<br/>搜尋關鍵字"]:::process
        End(["index.html<br/>結果展示"]):::start_end
        JS{"script.js<br/>發送請求"}:::decision
    end

    %% --- 泳道 2: Processing ---
    subgraph App [後端邏輯處理]
        
        CheckDB("check_db.py<br/>檢查資料狀態"):::program
        Crawler("crawler_esgReport.py<br/>PDF 爬蟲"):::program
        Gemini_1("gemini_api<br/>P1:內文比對 / P2:外部驗證"):::gemini
        Gemini_2("gemini_external_api<br/>P2:外部驗證"):::gemini
        Config("config.py<br/>輸入 JSON 檔"):::pplx
        Pplx("pplx_api.py<br/>URL 外部驗證"):::pplx
        Pplx_2("pplx_api_create_url.py<br/>URL 建立"):::pplx
        Calc("calculate_esg.py<br/>風險分數計算"):::program
        Word_cloud("word_cloud.py<br/>生成詞雲"):::program
        Flask("app.py<br/>Flask API Server"):::program
    end

    %% --- 泳道 2-1: DB操作 ---
    subgraph DB [資料庫操作層]
        pymysql_insert_1("pymysql_insert_1.py<br/>寫入資料庫"):::pymysql
        pymysql_update_2("pymysql_update_2.py<br/>更新資料庫"):::pymysql
        pymysql_update_3("pymysql_update_3.py<br/>更新資料庫"):::pymysql
        pymysql_select("pymysql_select.py<br/>讀取資料庫"):::pymysql
    end

    %% --- 泳道 3: Data ---
    subgraph Data [數據管理層]
        PDF[["永續報告書<br/>PDF 檔案"]]:::outputData
        JSON1["prompt1_josn"]:::outputData
        JSON2["prompt2_josn"]:::outputData
        JSON3["prompt3_josn"]:::outputData
        wc_json["詞雲<br/>JSON"]:::outputData
    end

    %% --- 泳道 4: Database ---
    subgraph Database [資料庫管理層]
        DB_Node[("MySQL<br/>資料庫")]:::db
    end

    %% --- 連線邏輯 ---
    Start --> Input --> JS
    JS --> CheckDB
    
    %% 資料檢查路徑
    DB_Node -.->|讀取狀態| CheckDB
    CheckDB -- 無資料 --> Crawler
    CheckDB -- 有資料 --> Flask

    %% 爬蟲與 AI 處理流
    Crawler --> PDF --> Gemini_1
    Gemini_1 --> JSON1 --> Gemini_2
    Gemini_2 --> JSON2

    %% 詞雲生成流
    PDF --> Word_cloud --> wc_json
    wc_json --> Flask

    %% JSON 數據分流
    JSON2 --> Config --> Pplx
    Pplx -- url有效 --> JSON3
    Pplx -- url無效 --> Pplx_2 --> JSON3
    JSON3 --> pymysql_update_3 -.->|更新| DB_Node

    DB_Node -.->|讀取| Calc --> pymysql_select --> Flask
    JSON1 --> pymysql_insert_1 -.->|寫入| DB_Node
    JSON2 --> pymysql_update_2 -.->|更新| DB_Node

    %% 最終回傳展示
    Flask --> End

    %% 調整視覺間距
    style UI fill:#f9f9f9,stroke:#ddd
    style App fill:#f5f5f5,stroke:#ddd
    style Data fill:#f9f9f9,stroke:#ddd
    style DB fill:#f5f5f5,stroke:#ddd
    style Database fill:#f5f5f5,stroke:#ddd