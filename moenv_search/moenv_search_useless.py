"""
環境部公害糾紛裁決書查詢工具
從環境部API取得公害糾紛裁決書資料
"""
import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MY_API_KEY = os.getenv("MOENV_API_KEY")


def get_pollution_dispute_records(api_key=MY_API_KEY, limit=100, year_start="2024-01-01", year_end="2024-12-31"):
    """
    從環境部API取得公害糾紛裁決書資料
    
    Args:
        api_key: 環境部API金鑰
        limit: 查詢筆數上限（預設100）
        year_start: 開始日期
        year_end: 結束日期
    
    Returns:
        DataFrame: 裁決書記錄資料
    """
    data_id = "peti_p_02"  # 公害糾紛裁決書
    url = f"https://data.moenv.gov.tw/api/v2/{data_id}"

    params = {
        "format": "json",
        "offset": 0,
        "limit": limit,
        "api_key": api_key,
        # close_case: 結案日期篩選
        "filters": f"close_case,GR,{year_start}|close_case,LE,{year_end}"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "records" not in data:
            print("⚠ 未取得資料")
            return None
        
        records = data["records"]
        print(f"✓ API 回傳 {len(records)} 筆記錄")
        
        if len(records) == 0:
            print("⚠ 查無資料")
            return None
        
        df = pd.DataFrame(records)
        
        # 欄位對應（根據 peti_p_02 API 規格）
        columns_map = {
            "decision_theme": "裁決主旨",
            "close_case": "結案日期",
            "petitioner": "聲請人",
            "respondent": "相對人",
            "decision_content": "裁決內容",
            "petition_reason": "聲請理由"
        }
        
        # 選取並重新命名欄位
        available_cols = [c for c in columns_map.keys() if c in df.columns]
        if available_cols:
            df = df[available_cols].rename(columns=columns_map)
        
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"✗ API 請求錯誤: {e}")
        return None
    except Exception as e:
        print(f"✗ 發生錯誤: {e}")
        return None


def save_to_json(df, output_path="moenv_pollution_dispute.json"):
    """
    將DataFrame儲存為JSON檔案（添加流水號）
    
    Args:
        df: 要儲存的 DataFrame
        output_path: 輸出檔案路徑
    """
    if df is None or df.empty:
        print("✗ 無資料可儲存")
        return
    
    # 轉換為字典列表
    json_data = df.to_dict(orient='records')
    
    # 添加流水號
    for i, record in enumerate(json_data, start=1):
        record['流水號'] = i
        # 調整順序，將流水號放在最前面
        ordered_record = {'流水號': record.pop('流水號')}
        ordered_record.update(record)
        json_data[i-1] = ordered_record
    
    # 儲存到指定路徑
    output_path = os.path.join(CURRENT_DIR, output_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 資料已儲存至: {output_path}")
    print(f"✓ 共 {len(json_data)} 筆記錄")


def main():
    """主程式"""
    print("=" * 70)
    print("環境部公害糾紛裁決書查詢")
    print("=" * 70)
    
    API_LIMIT = 100
    YEAR_START = "2021-01-01"
    YEAR_END = "2024-12-31"
    
    # 1. 取得環境部公害糾紛裁決書資料
    print(f"\n步驟 1: 取得公害糾紛裁決書資料...")
    print(f"  查詢期間: {YEAR_START} ~ {YEAR_END}")
    print(f"  查詢上限: {API_LIMIT} 筆")
    
    df = get_pollution_dispute_records(
        api_key=MY_API_KEY, 
        limit=API_LIMIT,
        year_start=YEAR_START,
        year_end=YEAR_END
    )
    
    if df is None or df.empty:
        print("\n✗ 無法取得資料或查無記錄")
        return
    
    print(f"✓ 成功取得 {len(df)} 筆裁決書記錄")
    
    # 檢查API上限警告
    if len(df) >= API_LIMIT:
        print(f"\n⚠️  警告: 搜索結果達到API上限 ({API_LIMIT} 筆)")
        print("    實際資料可能更多，建議調整查詢期間或分批查詢")
    
    # 2. 顯示資料預覽
    print(f"\n{'='*70}")
    print(f"資料預覽（前 10 筆）")
    print("=" * 70)
    print(df.head(10).to_string(index=False))
    
    if len(df) > 10:
        print(f"\n... （還有 {len(df) - 10} 筆記錄未顯示）")
    
    # 3. 儲存資料
    print(f"\n{'='*70}")
    print("步驟 2: 儲存資料...")
    output_file = "moenv_pollution_dispute.json"
    save_to_json(df, output_file)
    
    # 統計資訊
    print(f"\n{'='*70}")
    print("統計資訊")
    print("=" * 70)
    print(f"查詢期間: {YEAR_START} ~ {YEAR_END}")
    print(f"總記錄數: {len(df)} 筆")
    
    # 顯示欄位資訊
    print(f"\n可用欄位:")
    for col in df.columns:
        print(f"  - {col}")


if __name__ == "__main__":
    # API參考文件: https://data.moenv.gov.tw/swagger/#/
    main()