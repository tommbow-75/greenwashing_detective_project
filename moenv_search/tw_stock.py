import requests
import json


def get_listed_companies():
    """
    從台灣證交所獲取上市公司清單
    回傳公司名稱列表（用於比對環境部的裁處資料）
    
    Returns:
        list: 上市公司名稱列表
    """
    try:
        # 台灣證交所上市公司基本資料 API
        url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        # 取得公司名稱列表
        company_names = [item.get('公司名稱', '') for item in data if '公司名稱' in item]
        
        print(f"✓ 已取得 {len(company_names)} 家上市公司資料")
        return company_names
        
    except Exception as e:
        print(f"⚠ 取得上市公司清單時發生錯誤: {e}")
        print("將使用空白清單（無法過濾上市公司）")
        return []


def get_listed_companies_full_data():
    """
    從台灣證交所獲取上市公司完整資料
    只保留：公司代號、公司名稱、公司簡稱、產業別
    
    Returns:
        list: 包含簡化資料的字典列表
    """
    try:
        # 台灣證交所上市公司基本資料 API
        url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # 只保留需要的欄位
        filtered_data = []
        for item in data:
            filtered_item = {
                "公司代號": item.get("公司代號", ""),
                "公司名稱": item.get("公司名稱", ""),
                "公司簡稱": item.get("公司簡稱", ""),
                "產業別": item.get("產業別", "")
            }
            filtered_data.append(filtered_item)
        
        print(f"✓ 已取得 {len(filtered_data)} 家上市公司資料（僅保留4個欄位）")
        return filtered_data
        
    except Exception as e:
        print(f"⚠ 取得上市公司資料時發生錯誤: {e}")
        return []


def save_listed_companies_to_json(output_path="tw_listed_companies.json"):
    """
    獲取上市公司資料並儲存為 JSON 檔案
    
    Args:
        output_path: 輸出檔案路徑
    """
    data = get_listed_companies_full_data()
    
    if data:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 資料已儲存至: {output_path}")
        print(f"✓ 共 {len(data)} 家上市公司")
    else:
        print("✗ 無資料可儲存")


# 使用範例
if __name__ == "__main__":
    print("=" * 60)
    print("台灣上市公司資料查詢")
    print("=" * 60)
    
    # 獲取公司名稱列表
    print("\n方法 1: 獲取公司名稱列表")
    companies = get_listed_companies()
    if companies:
        print(f"\n前 10 家公司：")
        for i, name in enumerate(companies[:10], 1):
            print(f"  {i}. {name}")
    
    # 獲取完整資料並儲存
    print("\n\n方法 2: 獲取完整資料並儲存為 JSON")
    save_listed_companies_to_json("tw_listed_companies.json")
