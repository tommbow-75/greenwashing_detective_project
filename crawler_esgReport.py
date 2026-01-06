import requests
import urllib3
import os
import time

# 隱藏安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==================== 可程式化呼叫的函式 ====================

def validate_report_exists(year, company_code, market_type=0):
    """
    快速驗證永續報告是否存在（不下載檔案）
    
    Args:
        year: 查詢年度（西元）
        company_code: 公司代碼
        market_type: 市場類型 (0: 上市, 1: 上櫃)
    
    Returns:
        tuple: (exists: bool, report_info: dict or None)
        report_info 包含: {
            'company_code': str,
            'company_name': str,
            'sector': str,
            'download_url': str,
            'file_name': str
        }
    """
    # 根據年份決定 API 網址
    if year >= 2023:
        url = 'https://esggenplus.twse.com.tw/api/api/MopsSustainReport/data'
        is_new_version = True
    else:
        url = 'https://esggenplus.twse.com.tw/api/api/MopsSustainReport/data/old'
        is_new_version = False
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://esggenplus.twse.com.tw',
        'Referer': 'https://esggenplus.twse.com.tw/info/mops-sustain-report'
    }
    
    payload = {
        "marketType": market_type,
        "year": year,
        "industryNameList": [],
        "companyCodeList": [company_code],
        "industryName": "all",
        "companyCode": company_code
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30, verify=False)
        res.raise_for_status()
        json_data = res.json()
        items = json_data.get('data')
        
        if not items or len(items) == 0:
            return (False, None)
        
        # 取得第一筆資料
        item = items[0]
        
        if is_new_version:
            # 新版邏輯 (2023+)
            stock_code = item.get('code')
            company_name = item.get('shortName')
            sector = item.get('sector')  # 2023+ 使用 sector 欄位
            report_id = item.get('twFirstReportDownloadId')
            download_url = f"https://esggenplus.twse.com.tw/api/api/MopsSustainReport/data/FileStream?id={report_id}" if report_id else None
        else:
            # 舊版邏輯 (2022-)
            stock_code = item.get('companY_ID')
            company_name = item.get('companY_ABBR_NAME')
            sector = item.get('name')  # 2022- 使用 name 欄位
            file_name_api = item.get('filE_NAME')
            download_url = f"https://mopsov.twse.com.tw/server-java/FileDownLoad?step=9&filePath=/home/html/nas/protect/t100/&fileName={file_name_api}" if file_name_api else None
        
        if not download_url:
            return (False, None)
        
        report_info = {
            'company_code': stock_code,
            'company_name': company_name,
            'sector': sector,
            'download_url': download_url,
            'file_name': f"{year}_{stock_code}_{company_name}_永續報告書.pdf"
        }
        
        return (True, report_info)
    
    except Exception as e:
        print(f"[驗證失敗] {e}")
        return (False, None)


def download_esg_report(year, company_code, market_type=0, save_dir='./ESG_Reports'):
    """
    下載永續報告書
    
    Args:
        year: 查詢年度（西元）
        company_code: 公司代碼
        market_type: 市場類型 (0: 上市, 1: 上櫃)
        save_dir: 儲存目錄路徑
    
    Returns:
        tuple: (success: bool, file_path_or_error: str)
        若成功，回傳 (True, PDF檔案的完整路徑)
        若失敗，回傳 (False, 錯誤訊息)
    """
    # 先驗證報告是否存在
    exists, report_info = validate_report_exists(year, company_code, market_type)
    
    if not exists:
        return (False, f"查無 {year} 年的報告資料（公司代碼: {company_code}）")
    
    # 建立儲存目錄
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # 開始下載
    download_url = report_info['download_url']
    file_name = report_info['file_name']
    full_path = os.path.join(save_dir, file_name)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"[*] 開始下載: {file_name}")
        file_res = requests.get(download_url, headers=headers, timeout=120, verify=False)
        
        if file_res.status_code == 200:
            with open(full_path, 'wb') as f:
                f.write(file_res.content)
            print(f"    [OK] 下載成功！")
            return (True, full_path)
        else:
            error_msg = f"下載失敗，狀態碼: {file_res.status_code}"
            print(f"    [Error] {error_msg}")
            return (False, error_msg)
    
    except Exception as e:
        error_msg = f"下載過程出錯: {str(e)}"
        print(f"    [Error] {error_msg}")
        return (False, error_msg)


# ==================== 原有互動式功能 ====================

if __name__ == '__main__':
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