"""
環境部裁處資料查詢工具 - 針對上市公司
從環境部API取得污染源裁處資料，並過濾出上市公司的記錄
"""
import os
import json
import re
import requests
import pandas as pd
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MY_API_KEY = os.getenv("MOENV_API_KEY")


def get_epa_penalty_records(api_key=MY_API_KEY, limit=50):
    """
    從環境部API取得裁處資料
    
    Args:
        api_key: 環境部API金鑰
        limit: 查詢筆數上限（預設50）
    
    Returns:
        DataFrame: 裁處記錄資料
    """
    data_id = "EMS_P_46"  # 列管事業污染源裁處資料
    url = f"https://data.moenv.gov.tw/api/v2/{data_id}"

    params = {
    "format": "json",
    "offset": 0,
    "limit": limit,
    "api_key": api_key,
    # 這裡直接寫字串，requests 會自動幫你把 | 轉成 %7C
    "filters": "penalty_date,GR,2014-01-01|penalty_date,LE,2024-12-31"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "records" not in data:
            print("⚠ 未取得資料")
            return None
        
        df = pd.DataFrame(data["records"])
        
        # 欄位對應 - 添加更多字段
        columns_map = {
            "fac_name": "公司名稱",
            "penalty_date": "裁處日期",
            "county_name": "處分機關",
            "law_name": "違反法條",
            "penalty_money": "罰鍰金額",
            "violation_fact": "違規事實",
            "openinfor": "公開資訊",
            "transgress_law": "違規法規",
            "transgress_type": "違規類型",
            "is_improve": "是否改善"
        }
        
        # 選取並重新命名欄位
        available_cols = [c for c in columns_map.keys() if c in df.columns]
        df = df[available_cols].rename(columns=columns_map)
        
        return df
        
    except Exception as e:
        print(f"✗ 發生錯誤: {e}")
        return None


def load_listed_companies_from_json(json_path="tw_listed_companies.json"):
    """
    從本地JSON檔案讀取上市公司清單
    
    Args:
        json_path: JSON檔案路徑
    
    Returns:
        list: 包含完整公司資料的字典列表
    """
    try:
        if not os.path.isabs(json_path):
            json_path = os.path.join(CURRENT_DIR, json_path)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✓ 從 {os.path.basename(json_path)} 讀取 {len(data)} 家上市公司")
        return data
        
    except FileNotFoundError:
        print(f"⚠ 找不到檔案: {json_path}")
        print("  提示: 請先執行 tw_stock.py 產生上市公司清單")
        return []
    except Exception as e:
        print(f"⚠ 讀取檔案錯誤: {e}")
        return []


def filter_listed_companies(df, listed_companies_data):
    """
    過濾只保留上市公司的裁處記錄，並添加公司簡稱
    使用模糊比對處理公司名稱差異（如：股份有限公司 vs XX廠）
    
    Args:
        df: 裁處資料 DataFrame
        listed_companies_data: 上市公司資料列表（包含公司名稱、簡稱等）
    
    Returns:
        DataFrame: 過濾後的資料（包含公司簡稱欄位）
    """
    if df is None or df.empty:
        return df
    
    if not listed_companies_data:
        print("⚠ 上市公司清單為空，無法過濾")
        return df
    
    # 建立公司名稱到簡稱的對應字典
    company_mapping = {}
    listed_set = set()
    
    for company in listed_companies_data:
        full_name = company.get('公司名稱', '')
        abbr_name = company.get('公司簡稱', '')
        clean_name = full_name.replace('股份有限公司', '').replace('有限公司', '').strip()
        
        company_mapping[clean_name] = {
            'full_name': full_name,
            'abbr': abbr_name
        }
        listed_set.add(clean_name)
    
    # 找出匹配的公司簡稱
    def get_company_abbr(company_name):
        if not company_name:
            return None
        
        # 清理公司名稱
        clean_name = company_name.replace('股份有限公司', '').replace('有限公司', '').strip()
        clean_name = re.sub(r'(煉製事業部|事業部|.*廠)$', '', clean_name).strip()
        
        # 精確比對
        if clean_name in company_mapping:
            return company_mapping[clean_name]['abbr']
        
        # 部分比對
        for listed_name, info in company_mapping.items():
            if listed_name in clean_name or clean_name in listed_name:
                return info['abbr']
        
        return None
    
    # 添加公司簡稱欄位
    df['公司簡稱'] = df['公司名稱'].apply(get_company_abbr)
    
    # 過濾出有簡稱的記錄（即上市公司）
    original_count = len(df)
    filtered_df = df[df['公司簡稱'].notna()].copy()
    filtered_count = len(filtered_df)
    
    print(f"\n✓ 過濾結果:")
    print(f"  原始記錄: {original_count} 筆")
    print(f"  上市公司: {filtered_count} 筆")
    print(f"  比例: {filtered_count/original_count*100:.1f}%" if original_count > 0 else "  比例: 0%")
    
    return filtered_df


def save_to_json(df, output_path="moenv_penalty_data.json"):
    """
    將DataFrame儲存為JSON檔案（添加流水號）
    
    Args:
        df: 要儲存的 DataFrame
        output_path: 輸出檔案路徑
    """
    if df is None or df.empty:
        print("✗ 無資料可儲存")
        return
    
    # 重新排列欄位順序
    columns_order = [
        '公司名稱', '公司簡稱', '裁處日期', '處分機關', 
        '違反法條', '違規法規', '違規類型', '違規事實',
        '罰鍰金額', '是否改善', '公開資訊'
    ]
    available_columns = [col for col in columns_order if col in df.columns]
    df_ordered = df[available_columns]
    
    # 轉換為字典列表
    json_data = df_ordered.to_dict(orient='records')
    
    # 添加流水號
    for i, record in enumerate(json_data, start=1):
        record['流水號'] = i
        # 調整順序，將流水號放在最前面
        ordered_record = {'流水號': record.pop('流水號')}
        ordered_record.update(record)
        json_data[i-1] = ordered_record
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 資料已儲存至: {output_path}")
    print(f"✓ 共 {len(json_data)} 筆記錄")


def main():
    """主程式"""
    print("=" * 70)
    print("環境部裁處資料查詢（上市公司）")
    print("=" * 70)
    
    API_LIMIT = 10000
    
    # 1. 讀取上市公司清單
    print("\n步驟 1: 讀取上市公司清單...")
    listed_companies = load_listed_companies_from_json("tw_listed_companies.json")
    
    if not listed_companies:
        print("\n✗ 無法載入上市公司清單，程式結束")
        return
    
    # 2. 取得環境部裁處資料
    print(f"\n步驟 2: 取得環境部裁處資料（上限 {API_LIMIT} 筆）...")
    df = get_epa_penalty_records(MY_API_KEY, limit=API_LIMIT)
    
    if df is None:
        print("\n✗ 無法取得裁處資料")
        return
    
    print(f"✓ 取得 {len(df)} 筆裁處記錄")
    
    # 檢查API上限警告
    if len(df) >= API_LIMIT:
        print(f"\n⚠️  警告: 搜索結果達到API上限 ({API_LIMIT} 筆)")
        print("    實際資料可能更多，建議考慮分批查詢")
    
    # 3. 過濾上市公司
    print("\n步驟 3: 過濾上市公司資料...")
    df_listed = filter_listed_companies(df, listed_companies)
    
    if df_listed.empty:
        print("\n⚠ 未找到上市公司的裁處記錄")
        return
    
    # 4. 顯示結果
    print(f"\n{'='*70}")
    print(f"上市公司裁處記錄（共 {len(df_listed)} 筆）")
    print("=" * 70)
    print(df_listed.head(10).to_string(index=False))
    
    if len(df_listed) > 10:
        print(f"\n... （還有 {len(df_listed) - 10} 筆記錄未顯示）")
    
    # 5. 儲存資料
    print(f"\n{'='*70}")
    print("步驟 4: 儲存資料...")
    output_file = "moenv_listed_companies_penalty.json"
    save_to_json(df_listed, output_file)
    
    # 統計資訊
    print(f"\n{'='*70}")
    print("統計資訊")
    print("=" * 70)
    print(f"總查詢記錄: {len(df)} 筆")
    print(f"上市公司記錄: {len(df_listed)} 筆")
    print(f"過濾比例: {len(df_listed)/len(df)*100:.1f}%")


if __name__ == "__main__":
    # API參考文件: https://data.moenv.gov.tw/swagger/#/
    main()