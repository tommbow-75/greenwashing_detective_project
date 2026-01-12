import time
import pandas as pd
import requests
import json
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# === 設定年份範圍 ===
START_YEAR = 2021
END_YEAR = 2024

def get_listed_codes():
    """
    從本地 JSON 檔案讀取上市公司代號列表
    """
    print("正在讀取上市公司代號...")
    json_path = os.path.join(os.path.dirname(__file__), "tw_listed_companies.json")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            companies = json.load(f)
        
        codes = []
        names_map = {}
        
        for company in companies:
            code = company.get('公司代號')
            name = company.get('公司簡稱', company.get('公司名稱', ''))
            
            if code:
                codes.append(code)
                names_map[code] = name
        
        print(f"共讀取 {len(codes)} 家上市公司代號。")
        return codes, names_map
        
    except FileNotFoundError:
        print(f"找不到檔案: {json_path}")
        print("請確認 tw_listed_companies.json 檔案存在於相同目錄下。")
        return [], {}
    except json.JSONDecodeError as e:
        print(f"JSON 解析錯誤: {e}")
        return [], {}
    except Exception as e:
        print(f"讀取檔案失敗: {e}")
        return [], {}

def init_driver():
    """
    初始化 Selenium 瀏覽器
    """
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # 若不想看到瀏覽器跳出來，可取消註解 (但在爬動態網站時建議開啟以除錯)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 使用 webdriver_manager 自動下載/管理驅動
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def scrape_company_penalties(driver, stock_code, stock_name):
    """
    使用使用者指定的 XPath 進入查詢介面並爬取資料
    """
    base_url = "https://thaubing.gcaa.org.tw"
    
    try:
        driver.get(base_url)
        wait = WebDriverWait(driver, 10) # 設定最長等待 10 秒

        # === 修改開始：使用你提供的 XPath ===
        try:
            print(f"正在嘗試點擊指定路徑: /html/body/div[2]...")
            # 1. 定位你提供的 XPath 按鈕
            target_button = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/div[1]/div[2]/div[3]/div/div/div[1]/ul/li[2]/a')))
            target_button.click()
            
            # 點擊後稍微等待介面反應
            time.sleep(1) 
        except Exception as e:
            print(f"找不到指定的 XPath 按鈕或無法點擊: {e}")
            return []
        # === 修改結束 ===

        # 2. 尋找輸入框 (點擊後應該會出現輸入框)
        # 注意：這裡仍需確認點擊該 XPath 後，輸入框的特徵是什麼
        # 假設點擊後會出現一個 type='text' 的輸入框
        try:
            search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")))
            search_input.clear()
            search_input.send_keys(stock_code)
            time.sleep(1)
            search_input.send_keys(Keys.ENTER)
        except Exception as e:
            print(f"無法找到搜尋輸入框: {e}")
            return []
        
        # 3. 處理搜尋結果與表格爬取 (這部分邏輯與之前相同，視網站反應而定)
        time.sleep(3) # 等待搜尋結果載入

        # 以下邏輯需視「輸入代號按 Enter」後，網頁是直接跳轉還是顯示列表而定
        # 若需要點擊列表中的第一筆結果，請在此加入點擊邏輯
        
        # 開始解析表格
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        records = []
        rows = soup.find_all('tr') 
        
        for row in rows:
            cols = row.find_all('td')
            if not cols: continue
            
            row_text = [c.get_text(strip=True) for c in cols]
            
            # 簡單檢查是否有日期格式 (過濾掉非資料列)
            has_date = any("20" in t and ("/" in t or "-" in t) for t in row_text)
            
            if has_date:
                records.append({
                    "股票代號": stock_code,
                    "公司名稱": stock_name,
                    "資料內容": " | ".join(row_text),
                    "來源網址": driver.current_url
                })
                    
        return records

    except Exception as e:
        print(f"[{stock_code}] 爬取發生錯誤: {e}")
        return []

def main():
    # 1. 取得目標股票代號列表
    codes, names_map = get_listed_codes()
    
    # 為了測試，我們先只取前 5 家公司 (正式跑請拿掉 [:5])
    target_codes = ["1102"] 
    print(f"預計爬取 {len(target_codes)} 家公司...")

    # 2. 啟動瀏覽器
    driver = init_driver()
    
    all_data = []

    try:
        for code in target_codes:
            name = names_map.get(code, "")
            print(f"正在爬取: {code} {name} ...")
            
            results = scrape_company_penalties(driver, code, name)
            
            if results:
                print(f" -> 找到 {len(results)} 筆紀錄")
                all_data.extend(results)
            else:
                print(f" -> 無相關紀錄或無法讀取")
            
            # 禮貌性暫停，避免被鎖 IP
            time.sleep(4)
            
    finally:
        driver.quit()
        print("瀏覽器已關閉。")

    # 3. 儲存結果
    if all_data:
        df_result = pd.DataFrame(all_data)
        filename = f"thaubing_penalties_{START_YEAR}_{END_YEAR}.csv"
        df_result.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"爬取完成！資料已儲存為 {filename}")
    else:
        print("沒有爬取到任何資料。")

if __name__ == "__main__":
    main()