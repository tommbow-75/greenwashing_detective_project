import requests
import pandas as pd

def get_epa_penalty_records(api_key, limit=1000):
    # 資料集 ID: EMS_P_46 (列管事業污染源裁處資料)
    data_id = "EMS_P_46"
    url = f"https://data.moenv.gov.tw/api/v2/{data_id}"
    
    params = {
        "api_key": api_key,
        "limit": limit,
        "format": "json",
        "sort": "penalty_date desc"  # 依裁處日期降序排列
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # 檢查連線狀態
        data = response.json()
        
        if "records" in data:
            df = pd.DataFrame(data["records"])
            
            # 選取並重新命名常用欄位，方便閱讀
            columns_map = {
                "fac_name": "公司名稱",
                "penalty_date": "裁處日期",
                "county_name": "處分機關",
                "law_name": "違反法條",
                "penalty_money": "罰鍰金額",
                "violation_fact": "違規事實"
            }
            
            # 確保欄位存在再選取
            available_cols = [c for c in columns_map.keys() if c in df.columns]
            df = df[available_cols].rename(columns=columns_map)
            
            return df
        else:
            print("未取得資料 records")
            return None
            
    except Exception as e:
        print(f"發生錯誤: {e}")
        return None

# 使用範例 (請替換成您的 API Key)
# 如果沒有 Key，可以用瀏覽器直接開 URL 測試，但正式使用建議申請 Key
MY_API_KEY = "您的_API_KEY" 

# 若暫時無 Key，環境部有提供 Swagger 測試介面可觀察 Response
# https://data.moenv.gov.tw/swagger/#/

# df = get_epa_penalty_records(MY_API_KEY)
# if df is not None:
#     print(df.head())
#     # 簡單分析：哪家公司被罰最多錢
#     # print(df.sort_values("罰鍰金額", ascending=False).head())