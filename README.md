# greenwashing_detective_project
# 一、 下載GitHub Desktop

#　二、把專案領回家 (Clone)
# 打開 GitHub Desktop，登入你的帳號。
# 點擊 File > Clone Repository。
# 選取 greenwashing_detective_project，本地端找地方放它。
# 注意： 資料夾路徑盡量不要有中文，避免程式報錯。

# 三、檔案對應
# pymysql → db_service.py
# flask → app.py
# gemini → gemini_api.py
# pplx → pplx_api.py
# 爬蟲 → crawler_esgReport
# /template/html → index.html
# /static/css → style.css
# /static/js → script.js

# 四、工作步驟 (避免衝突)
# 為了防止大家改到同一個檔案，請遵守以下流程
# 1.開工前點擊 GitHub Desktop 的 Fetch origin / Pull。先把別人的進度抓下來。
# 2.點擊 Current Branch > New Branch (ex. 命名格式：gemini_api_v2.py)
# 3.程式完成後，在 GitHub Desktop 進行 Commit 並點擊 Publish branch。
# 4.發起合併，到 GitHub 網頁版點擊 Compare & pull request，並簡述修改內容
# 5.待我確認後，即可合併