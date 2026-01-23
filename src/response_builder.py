"""
API 回應建構模組
統一 ESG 分析系統的 API 回應格式
"""

from typing import Optional
from src.calculate_esg import calculate_esg_scores


def build_company_response(company_data: dict, details: list, status: str = 'completed', message: str = '資料已存在') -> dict:
    """
    建構公司資料的標準回應格式
    
    Args:
        company_data: 公司基本資料 dict
        details: ESG 分析細項列表
        status: 回應狀態
        message: 回應訊息
        
    Returns:
        dict: 標準格式的 API 回應
    """
    scores = calculate_esg_scores(company_data['industry'], details)
    
    company_obj = {
        'id': company_data['ESG_id'],
        'name': company_data['company_name'],
        'stockId': company_data['company_code'],
        'industry': company_data['industry'],
        'year': company_data['Report_year'],
        'url': company_data['URL'],
        'greenwashingScore': scores['Total'],
        'eScore': scores['E'],
        'sScore': scores['S'],
        'gScore': scores['G'],
        'layer4Data': details
    }
    
    return {
        'status': status,
        'message': message,
        'data': company_obj,
        'esg_id': company_data['ESG_id']
    }


def build_processing_response(esg_id: str, message: str = '分析進行中，請稍候') -> dict:
    """
    建構處理中狀態的回應
    
    Args:
        esg_id: ESG ID
        message: 回應訊息
        
    Returns:
        dict: 處理中狀態的回應
    """
    return {
        'status': 'processing',
        'message': message,
        'esg_id': esg_id
    }


def build_validation_needed_response(esg_id: str, report_info: dict, message: str = '查無資料，是否啟動自動抓取與分析？') -> dict:
    """
    建構需要驗證確認的回應
    
    Args:
        esg_id: ESG ID
        report_info: 報告資訊
        message: 回應訊息
        
    Returns:
        dict: 需要使用者確認的回應
    """
    return {
        'status': 'validation_needed',
        'message': message,
        'report_info': report_info,
        'esg_id': esg_id
    }


def build_not_found_response(year: int, company_code: str, esg_id: str) -> dict:
    """
    建構查無資料的回應
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        esg_id: ESG ID
        
    Returns:
        dict: 查無資料的回應
    """
    return {
        'status': 'not_found',
        'message': f'查無 {year} 年度的永續報告（公司代碼: {company_code}）',
        'esg_id': esg_id
    }


def build_error_response(status: str, message: str, esg_id: Optional[str] = None) -> dict:
    """
    建構錯誤回應
    
    Args:
        status: 錯誤狀態 ('error', 'failed')
        message: 錯誤訊息
        esg_id: ESG ID (選填)
        
    Returns:
        dict: 錯誤回應
    """
    response = {
        'status': status,
        'message': message
    }
    if esg_id:
        response['esg_id'] = esg_id
    return response


def build_progress_response(stage: str, status: str) -> dict:
    """
    建構進度查詢回應
    
    Args:
        stage: 當前階段
        status: 狀態 ('processing', 'completed')
        
    Returns:
        dict: 進度回應
    """
    return {
        'stage': stage,
        'status': status
    }
