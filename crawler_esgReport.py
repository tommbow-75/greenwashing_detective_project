import requests
import urllib3
import os
import time

# 隱藏安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----- 互動式參數設定 -----
print("=== ESG 報告自動下載器 ===")

# 1. 市場類型輸入
market_input = input("請輸入市場類型 (0: 上市, 1: 上櫃): ").strip()
marketType = int(market_input) if market_input in ['0', '1'] else 0
print(f"已選擇：{'上市' if marketType == 0 else '上櫃'}")

# 2. 年度輸入
try:
    year = int(input("請輸入查詢年度 (西元，如 2023): "))
except ValueError:
    print("錯誤：年度請輸入數字。")
    exit()

# 3. 公司代碼輸入 (支援多筆)
codes_raw = input("請輸入公司代碼: ")
# 將字串轉換為清單，並移除多餘空格
companyCodeList = [code.strip() for code in codes_raw.replace('，', ',').split(',') if code.strip()]

if not companyCodeList:
    print("錯誤：必須提供至少一個公司代碼。")
    exit()

# 為了符合 API 格式，取清單第一個值作為單一代碼參數
companyCode = companyCodeList[0] 
industryNameList = []  
industryName = "all"  
# --------------------------

# 根據年份決定 API 網址
if year >= 2023:
    url = 'https://esggenplus.twse.com.tw/api/api/MopsSustainReport/data'
    is_new_version = True
else:
    url = 'https://esggenplus.twse.com.tw/api/api/MopsSustainReport/data/old'
    is_new_version = False

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://esggenplus.twse.com.tw',
    'Referer': 'https://esggenplus.twse.com.tw/info/mops-sustain-report'
}

payload = {
    "marketType": marketType,
    "year": year,
    "industryNameList": industryNameList,
    "companyCodeList": companyCodeList,
    "industryName": industryName,
    "companyCode": companyCode
}

save_path = "./ESG_Reports"
if not os.path.exists(save_path):
    os.makedirs(save_path)

# ----- 執行流程 -----
try:
    print(f"\n>>> 正在請求 {year} 年資料，網址: {url}")
    res = requests.post(url, headers=headers, json=payload, timeout=600, verify=False)
    res.raise_for_status() 
    json_data = res.json() 
    items = json_data.get('data')   # 大部分公司資料會出現在這，可以print出來看看

    if not items:
        print(f"[-] 查無 {year} 年的資料，請確認該年度是否有上傳報告或代碼是否正確。")
    else:
        for item in items:
            if is_new_version:
                # --- 新版邏輯 (2023+) ---
                stock_code = item.get('code')
                company_name = item.get('shortName')
                report_id = item.get('twFirstReportDownloadId')
                download_url = f"https://esggenplus.twse.com.tw/api/api/MopsSustainReport/data/FileStream?id={report_id}" if report_id else None
            else:
                # --- 舊版邏輯 (2022-) ---
                stock_code = item.get('companY_ID')
                company_name = item.get('companY_ABBR_NAME')
                file_name_api = item.get('filE_NAME')
                download_url = f"https://mopsov.twse.com.tw/server-java/FileDownLoad?step=9&filePath=/home/html/nas/protect/t100/&fileName={file_name_api}" if file_name_api else None

            if download_url:
                file_local_name = f"{year}_{stock_code}_{company_name}_永續報告書.pdf"
                full_path = os.path.join(save_path, file_local_name)

                print(f"[*] 發現檔案: {file_local_name}，準備下載...")
                
                try:
                    file_res = requests.get(download_url, headers=headers, timeout=120, verify=False)
                    if file_res.status_code == 200:
                        with open(full_path, 'wb') as f:
                            f.write(file_res.content)
                        print(f"    [OK] 下載成功！")
                        time.sleep(1) # 下載間隔
                    else:
                        print(f"    [Error] 下載失敗，狀態碼: {file_res.status_code}")
                except Exception as e:
                    print(f"    [Error] 下載過程出錯: {e}")
            else:
                print(f"[-] 跳過 {stock_code}: 無法取得有效的下載路徑或 ID")

except Exception as e:
    print(f"[!] 程式執行發生錯誤: {e}")

print("\n--- 所有任務處理完成 ---")