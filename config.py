"""
ESG 分析系統 - 集中配置檔案

此檔案集中管理所有目錄路徑，方便維護和修改。
使用時只需 import config，即可存取所有路徑變數。

使用範例：
    from config import PATHS, DATA_FILES
    
    # 使用路徑
    pdf_dir = PATHS['ESG_REPORTS']
    output_dir = PATHS['P1_JSON']
    
    # 使用資料檔案路徑
    sasb_map = DATA_FILES['SASB_WEIGHT_MAP']
"""

import os

# === 專案根目錄 ===
# 取得此 config.py 檔案所在的目錄作為專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# === 目錄路徑配置 ===
PATHS = {
    # 靜態資料目錄
    'STATIC_DIR': os.path.join(PROJECT_ROOT, 'static'),
    'STATIC_DATA': os.path.join(PROJECT_ROOT, 'static', 'data'),
    'STATIC_IMAGES': os.path.join(PROJECT_ROOT, 'static', 'images'),
    'STATIC_DICT': os.path.join(PROJECT_ROOT, 'static', 'data', 'dict'),
    
    # 暫存資料目錄
    'TEMP_DATA': os.path.join(PROJECT_ROOT, 'temp_data'),
    'ESG_REPORTS': os.path.join(PROJECT_ROOT, 'temp_data', 'esgReport'),
    'P1_JSON': os.path.join(PROJECT_ROOT, 'temp_data', 'prompt1_json'),
    'P2_JSON': os.path.join(PROJECT_ROOT, 'temp_data', 'prompt2_json'),
    'P3_JSON': os.path.join(PROJECT_ROOT, 'temp_data', 'prompt3_json'),
    'NEWS_OUTPUT': os.path.join(PROJECT_ROOT, 'temp_data', 'news_output'),
    
    # 新聞搜尋相關（統一存放於 temp_data/news_output）
    'NEWS_SEARCH_OUTPUT': os.path.join(PROJECT_ROOT, 'temp_data', 'news_output'),
    
    # Word Cloud 輸出（統一存放於 temp_data/wc_output）
    'WORD_CLOUD_OUTPUT': os.path.join(PROJECT_ROOT, 'temp_data', 'wc_output'),
    
    # Src 目錄（核心程式碼模組）
    'SRC_DIR': os.path.join(PROJECT_ROOT, 'src'),
    'TEMPLATES_DIR': os.path.join(PROJECT_ROOT, 'templates'),
}


# === 資料檔案路徑 ===
DATA_FILES = {
    # SASB 相關
    'SASB_WEIGHT_MAP': os.path.join(PATHS['STATIC_DATA'], 'SASB_weightMap.json'),
    'SASB_KEYWORD': os.path.join(PATHS['SRC_DIR'], 'sasb_keyword.json'),
    
    # MSCI 標準
    'MSCI_FLAG': os.path.join(PATHS['STATIC_DATA'], 'msci_flag.json'),
    
    # 公司資料
    'TW_LISTED_COMPANIES': os.path.join(PATHS['STATIC_DATA'], 'tw_listed_companies.json'),
    
    # 字典檔
    'ESG_DICT': os.path.join(PATHS['STATIC_DICT'], 'esg_dict.txt'),
}


# === 檔案命名模板 ===
# 定義標準檔名格式，確保整個專案使用一致的命名規則
FILE_TEMPLATES = {
    'P1_JSON': '{year}_{company_code}_p1.json',
    'P2_JSON': '{year}_{company_code}_p2.json',
    'P3_JSON': '{year}_{company_code}_p3.json',
    'NEWS_JSON': '{year}_{company_code}_news.json',
    'ESG_REPORT_PDF': '{year}_{company_code}_*.pdf',
}


# === 輔助函數 ===
def get_file_path(template_key: str, year: int, company_code: str, base_dir: str = None) -> str:
    """
    自動生成標準格式的檔案完整路徑
    
    功能說明：
        避免在程式中手動拼接字串（容易出錯），使用此函數可確保：
        1. 檔名格式統一（例如：2024_2330_p1.json）
        2. 路徑正確（自動加上對應的目錄）
        3. 跨平台相容（自動處理 Windows/Linux 路徑分隔符）
    
    Args:
        template_key: 檔案類型，可選值：'P1_JSON', 'P2_JSON', 'P3_JSON', 'NEWS_JSON', 'ESG_REPORT_PDF'
        year: 年份（例如：2024）
        company_code: 公司代碼（例如：'2330'）
        base_dir: 自訂基礎目錄（可選，通常不需要指定）
    
    Returns:
        完整檔案路徑（絕對路徑）
    
    使用範例：
        # 取代原本的寫法：
        # old: input_path = f'./temp_data/prompt1_json/{year}_{company_code}_p1.json'
        # new: 
        input_path = get_file_path('P1_JSON', 2024, '2330')
        # 結果: 'c:/project/temp_data/prompt1_json/2024_2330_p1.json'
        
        news_path = get_file_path('NEWS_JSON', 2024, '1102')
        # 結果: 'c:/project/temp_data/news_output/2024_1102_news.json'
    """
    filename = FILE_TEMPLATES[template_key].format(
        year=year,
        company_code=company_code
    )
    
    # 自動判斷基礎目錄
    if base_dir is None:
        dir_mapping = {
            'P1_JSON': PATHS['P1_JSON'],
            'P2_JSON': PATHS['P2_JSON'],
            'P3_JSON': PATHS['P3_JSON'],
            'NEWS_JSON': PATHS['NEWS_OUTPUT'],
            'ESG_REPORT_PDF': PATHS['ESG_REPORTS'],
        }
        base_dir = dir_mapping.get(template_key, PATHS['TEMP_DATA'])
    
    return os.path.join(base_dir, filename)


def ensure_directories():
    """
    確保所有必要的目錄存在，若不存在則創建
    
    使用範例:
        from config import ensure_directories
        ensure_directories()
    """
    for dir_path in PATHS.values():
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)


# === 自動建立目錄（可選） ===
# 若要在 import 時自動建立所有目錄，取消下行註解
# ensure_directories()


if __name__ == '__main__':
    """
    測試配置檔案
    """
    print("=== ESG 分析系統配置測試 ===\n")
    
    print("📁 目錄路徑:")
    for key, path in PATHS.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  {exists} {key}: {path}")
    
    print("\n📄 資料檔案:")
    for key, path in DATA_FILES.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  {exists} {key}: {path}")
    
    print("\n 檔案路徑生成測試:")
    test_path = get_file_path('P1_JSON', 2024, '2330')
    print(f"  P1 JSON 路徑範例: {test_path}")
