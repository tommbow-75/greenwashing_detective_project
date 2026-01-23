"""
斷點續傳工具模組
提供分析流程的階段完成檢查和恢復點判斷功能

各階段輸出檔案對應：
- Stage 1（下載 PDF）: temp_data/esgReport/{year}_{company_code}_*.pdf
- Stage 2（AI 分析）: temp_data/prompt1_json/{year}_{company_code}_p1.json
- Stage 3（新聞爬蟲）: temp_data/news_output/{year}_{company_code}_news.json
- Stage 4（AI 驗證）: temp_data/prompt2_json/{year}_{company_code}_p2.json
- Stage 5（來源驗證）: temp_data/prompt3_json/{year}_{company_code}_p3.json
- Stage 6（存入資料庫）: 資料庫中有 company_report 資料
"""

import os
import json
import glob
from config import PATHS, get_file_path


def check_pdf_exists(year: int, company_code: str) -> tuple[bool, str]:
    """
    檢查 PDF 是否已下載
    
    Returns:
        (存在與否, 檔案路徑或錯誤訊息)
    """
    # PDF 檔名模式: {year}_{company_code}_*.pdf
    pattern = os.path.join(PATHS['ESG_REPORTS'], f'{year}_{company_code}_*.pdf')
    matches = glob.glob(pattern)
    
    if matches:
        return True, matches[0]
    return False, f"PDF 不存在: {pattern}"


def check_json_valid(file_path: str) -> tuple[bool, str]:
    """
    檢查 JSON 檔案是否存在且有效
    
    Returns:
        (有效與否, 訊息)
    """
    if not os.path.exists(file_path):
        return False, f"檔案不存在: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 檢查是否為非空列表或字典
        if isinstance(data, list) and len(data) > 0:
            return True, f"有效 JSON ({len(data)} 筆資料)"
        elif isinstance(data, dict) and len(data) > 0:
            return True, f"有效 JSON (物件)"
        else:
            return False, f"JSON 內容為空"
    except json.JSONDecodeError as e:
        return False, f"JSON 解析失敗: {e}"
    except Exception as e:
        return False, f"讀取失敗: {e}"


def check_stage_completion(year: int, company_code: str, stage: str) -> tuple[bool, str, str]:
    """
    檢查特定階段是否已完成（輸出檔案存在且有效）
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        stage: 階段名稱 ('stage1' ~ 'stage6')
    
    Returns:
        (是否完成, 檔案路徑, 說明訊息)
    """
    if stage == 'stage1':
        # 檢查 PDF
        exists, path_or_msg = check_pdf_exists(year, company_code)
        return exists, path_or_msg if exists else "", path_or_msg
    
    elif stage == 'stage2':
        # 檢查 P1 JSON
        p1_path = get_file_path('P1_JSON', year, company_code)
        valid, msg = check_json_valid(p1_path)
        return valid, p1_path if valid else "", msg
    
    elif stage == 'stage3':
        # 檢查 News JSON
        news_path = get_file_path('NEWS_JSON', year, company_code)
        valid, msg = check_json_valid(news_path)
        return valid, news_path if valid else "", msg
    
    elif stage == 'stage4':
        # 檢查 P2 JSON
        p2_path = get_file_path('P2_JSON', year, company_code)
        valid, msg = check_json_valid(p2_path)
        return valid, p2_path if valid else "", msg
    
    elif stage == 'stage5':
        # 檢查 P3 JSON
        p3_path = get_file_path('P3_JSON', year, company_code)
        valid, msg = check_json_valid(p3_path)
        return valid, p3_path if valid else "", msg
    
    elif stage == 'stage6':
        # 檢查資料庫（這裡只返回 False，實際檢查在 app.py 中進行）
        return False, "", "Stage 6 需在資料庫層檢查"
    
    return False, "", f"未知階段: {stage}"


def determine_resume_point(year: int, company_code: str, current_status: str) -> dict:
    """
    根據 analysis_status 和檔案狀態判斷應從哪個階段繼續
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        current_status: 資料庫中的 analysis_status
    
    Returns:
        {
            'resume_from': 'stage1' ~ 'stage6' 或 'completed',
            'completed_stages': ['stage1', 'stage2', ...],
            'stage_details': {
                'stage1': {'completed': True, 'path': '...', 'msg': '...'},
                ...
            }
        }
    """
    stages = ['stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6']
    result = {
        'resume_from': 'stage1',
        'completed_stages': [],
        'stage_details': {}
    }
    
    # 逐一檢查每個階段
    for stage in stages:
        completed, path, msg = check_stage_completion(year, company_code, stage)
        result['stage_details'][stage] = {
            'completed': completed,
            'path': path,
            'msg': msg
        }
        
        if completed:
            result['completed_stages'].append(stage)
    
    # 判斷應從哪個階段繼續
    # 找到第一個未完成的階段
    for stage in stages:
        if stage not in result['completed_stages']:
            result['resume_from'] = stage
            break
    else:
        # 所有階段都完成
        result['resume_from'] = 'stage6'  # 從最後一步（存入資料庫）開始
    
    return result


def print_recovery_status(year: int, company_code: str, current_status: str):
    """
    列印恢復狀態報告（用於除錯）
    """
    result = determine_resume_point(year, company_code, current_status)
    
    print(f"\n{'='*50}")
    print(f"📊 斷點續傳狀態報告: {year}_{company_code}")
    print(f"   資料庫狀態: {current_status}")
    print(f"   應從 {result['resume_from']} 繼續")
    print(f"{'='*50}")
    
    stage_names = {
        'stage1': '下載 PDF',
        'stage2': 'AI 分析',
        'stage3': '新聞爬蟲',
        'stage4': 'AI 驗證',
        'stage5': '來源驗證',
        'stage6': '存入資料庫'
    }
    
    for stage, info in result['stage_details'].items():
        status = "✅" if info['completed'] else "❌"
        name = stage_names.get(stage, stage)
        print(f"   {status} {stage} ({name}): {info['msg']}")
    
    print(f"{'='*50}\n")
    
    return result


if __name__ == '__main__':
    # 測試
    print_recovery_status(2024, '2330', 'stage3')
