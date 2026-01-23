"""
ESG 分析流程協調模組
封裝完整的 ESG 報告分析流程，從下載到存入資料庫
"""

import os
import json
import threading
from typing import Optional

from config import PATHS
from src.db_service import update_analysis_status, insert_analysis_results


class ESGAnalysisPipeline:
    """
    ESG 分析流程協調器
    
    負責協調以下分析階段：
    - Stage 1: 下載 ESG 報告 PDF
    - Stage 2: 平行執行 Word Cloud 生成 + AI 分析
    - Stage 3: 新聞爬蟲驗證
    - Stage 4: AI 驗證與評分調整
    - Stage 5: 來源可靠度驗證
    - Stage 6: 存入資料庫
    """
    
    def run_analysis(
        self,
        esg_id: str,
        year: int,
        company_code: str,
        company_name: str,
        industry: str,
        report_info: dict
    ) -> dict:
        """
        執行完整的 ESG 分析流程
        
        Args:
            esg_id: ESG ID (例如 '20242330')
            year: 報告年份
            company_code: 公司代碼
            company_name: 公司名稱
            industry: 產業類別
            report_info: 報告資訊 dict
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'pdf_path': str (若成功),
                'analysis_result': dict (若成功)
            }
        """
        try:
            # Stage 1: 下載 PDF
            stage1_result = self._run_stage_1_download(esg_id, year, company_code)
            if not stage1_result['success']:
                return stage1_result
            
            pdf_path = stage1_result['pdf_path']
            
            # Stage 2: 平行執行 Word Cloud + AI 分析
            stage2_result = self._run_stage_2_parallel_analysis(
                esg_id, year, company_code, pdf_path, company_name, industry
            )
            if not stage2_result['success']:
                return stage2_result
            
            analysis_result = stage2_result['analysis_result']
            
            # Stage 3: 新聞爬蟲驗證
            self._run_stage_3_news_crawler(esg_id, year, company_code)
            
            # Stage 4: AI 驗證與評分調整
            self._run_stage_4_ai_verification(esg_id, year, company_code)
            
            # Stage 5: 來源可靠度驗證
            self._run_stage_5_source_verification(esg_id, year, company_code)
            
            # Stage 6: 存入資料庫
            stage6_result = self._run_stage_6_save_to_db(
                esg_id, year, company_code, company_name, industry, report_info, analysis_result
            )
            if not stage6_result['success']:
                return stage6_result
            
            # 更新狀態為 completed
            update_analysis_status(esg_id, 'completed')
            
            return {
                'success': True,
                'message': '自動抓取與分析完成',
                'pdf_path': pdf_path,
                'analysis_result': analysis_result
            }
            
        except Exception as e:
            update_analysis_status(esg_id, 'failed')
            return {
                'success': False,
                'message': f'處理過程發生錯誤: {str(e)}'
            }
    
    def _run_stage_1_download(self, esg_id: str, year: int, company_code: str) -> dict:
        """
        Stage 1: 下載 ESG 報告 PDF
        
        Returns:
            dict: {'success': bool, 'pdf_path': str or 'message': str}
        """
        from src.crawler_esgReport import download_esg_report
        
        update_analysis_status(esg_id, 'stage1')
        download_success, pdf_path_or_error = download_esg_report(year, company_code)
        
        if not download_success:
            update_analysis_status(esg_id, 'failed')
            return {
                'success': False,
                'message': f'下載失敗: {pdf_path_or_error}'
            }
        
        return {
            'success': True,
            'pdf_path': pdf_path_or_error
        }
    
    def _run_stage_2_parallel_analysis(
        self,
        esg_id: str,
        year: int,
        company_code: str,
        pdf_path: str,
        company_name: str,
        industry: str
    ) -> dict:
        """
        Stage 2: 平行執行 Word Cloud 生成 + AI 分析
        
        Returns:
            dict: {'success': bool, 'analysis_result': dict or 'message': str}
        """
        from src.word_cloud import generate_wordcloud
        from src.gemini_api import analyze_esg_report
        
        update_analysis_status(esg_id, 'stage2')
        
        # 儲存結果的變數
        wordcloud_result = None
        analysis_result = None
        analysis_error = None
        
        def run_wordcloud():
            nonlocal wordcloud_result
            try:
                wordcloud_result = generate_wordcloud(year, company_code, pdf_path, force_regenerate=False)
            except Exception as e:
                wordcloud_result = {'success': False, 'error': str(e)}
                print(f"⚠️ Word Cloud 生成錯誤: {e}")
        
        def run_ai_analysis():
            nonlocal analysis_result, analysis_error
            try:
                analysis_result = analyze_esg_report(
                    pdf_path,
                    year,
                    company_code,
                    company_name=company_name,
                    industry=industry
                )
            except Exception as e:
                analysis_error = str(e)
        
        # 建立並啟動執行緒
        wordcloud_thread = threading.Thread(target=run_wordcloud, name="WordCloudThread")
        ai_thread = threading.Thread(target=run_ai_analysis, name="AIAnalysisThread")
        
        print("🚀 啟動平行處理：Word Cloud 與 AI 分析")
        wordcloud_thread.start()
        ai_thread.start()
        
        # 等待完成
        wordcloud_thread.join(timeout=120)  # Word Cloud 最多等 2 分鐘
        ai_thread.join()  # AI 分析必須完成
        
        # 處理 Word Cloud 結果（非必要，失敗不影響主流程）
        if wordcloud_result and wordcloud_result.get('success'):
            if wordcloud_result.get('skipped'):
                print(f"ℹ️ Word Cloud 已存在，跳過生成")
            else:
                print(f"✅ Word Cloud 生成成功: {wordcloud_result.get('word_count', 0)} 個關鍵字")
        else:
            error_msg = wordcloud_result.get('error') if wordcloud_result else 'timeout'
            print(f"⚠️ Word Cloud 生成失敗: {error_msg}（不影響主流程）")
        
        # 檢查 AI 分析結果
        if analysis_error:
            update_analysis_status(esg_id, 'failed')
            return {
                'success': False,
                'message': f'AI 分析失敗: {analysis_error}'
            }
        
        return {
            'success': True,
            'analysis_result': analysis_result
        }
    
    def _run_stage_3_news_crawler(self, esg_id: str, year: int, company_code: str) -> dict:
        """
        Stage 3: 新聞爬蟲驗證 (非必要，失敗不中斷流程)
        
        Returns:
            dict: 新聞爬蟲結果
        """
        print("\n--- Step 4: 新聞爬蟲驗證 ---")
        update_analysis_status(esg_id, 'stage3')
        
        try:
            from src.crawler_news import search_news_for_report
            
            news_result = search_news_for_report(
                year=year,
                company_code=company_code,
                force_regenerate=True
            )
            
            if news_result['success']:
                if news_result.get('skipped'):
                    print(f"ℹ️ 新聞資料已存在，跳過生成")
                else:
                    print(f"✅ 新聞爬蟲完成：{news_result['news_count']} 則新聞")
                    print(f"   處理項目: {news_result['processed_items']}")
                    print(f"   失敗項目: {news_result['failed_items']}")
            else:
                print(f"⚠️ 新聞爬蟲失敗：{news_result.get('error')}（不影響主流程）")
            
            return news_result
            
        except Exception as e:
            print(f"⚠️ 新聞爬蟲發生錯誤: {str(e)}（不影響主流程）")
            return {'success': False, 'error': str(e)}
    
    def _run_stage_4_ai_verification(self, esg_id: str, year: int, company_code: str) -> dict:
        """
        Stage 4: AI 驗證與評分調整 (非必要，失敗不中斷流程)
        
        Returns:
            dict: AI 驗證結果
        """
        print("\n--- Step 5: AI 驗證與評分調整 ---")
        update_analysis_status(esg_id, 'stage4')
        
        try:
            from src.run_prompt2_gemini import verify_esg_with_news
            
            verify_result = verify_esg_with_news(
                year=year,
                company_code=company_code,
                force_regenerate=True
            )
            
            if verify_result['success']:
                if verify_result.get('skipped'):
                    print(f"ℹ️ AI 驗證結果已存在，跳過生成")
                else:
                    stats = verify_result['statistics']
                    print(f"✅ AI 驗證完成")
                    print(f"   輸出檔案: {verify_result['output_path']}")
                    print(f"   處理項目: {stats['processed_items']}")
                    print(f"   Token 使用: {stats['total_tokens']:,} (輸入: {stats['input_tokens']:,}, 輸出: {stats['output_tokens']:,})")
                    print(f"   執行時間: {stats['api_time']:.2f} 秒")
            else:
                print(f"⚠️ AI 驗證失敗：{verify_result.get('error')}（不影響主流程）")
            
            return verify_result
            
        except Exception as e:
            print(f"⚠️ AI 驗證發生錯誤: {str(e)}（不影響主流程）")
            return {'success': False, 'error': str(e)}
    
    def _run_stage_5_source_verification(self, esg_id: str, year: int, company_code: str) -> dict:
        """
        Stage 5: 來源可靠度驗證 (非必要，失敗不中斷流程)
        
        Returns:
            dict: 來源驗證結果
        """
        print("\n--- Step 6: 來源可靠度驗證 ---")
        update_analysis_status(esg_id, 'stage5')
        
        try:
            from src.pplx_api import verify_evidence_sources
            
            pplx_result = verify_evidence_sources(
                year=year,
                company_code=company_code,
                force_regenerate=True
            )
            
            if pplx_result['success']:
                if pplx_result.get('skipped'):
                    print(f"ℹ️ 來源驗證結果已存在，跳過生成")
                else:
                    stats = pplx_result['statistics']
                    print(f"✅ 來源驗證完成")
                    print(f"   輸出檔案: {pplx_result['output_path']}")
                    print(f"   輸入項目: {stats.get('total_input', 0)}")
                    print(f"   輸出項目: {stats.get('total_output', 0)}")
                    print(f"   有效 URL: {stats.get('verified_count', 0)}")
                    print(f"   更新 URL: {stats.get('updated_count', 0)}")
                    print(f"   失敗項目: {stats.get('failed_count', 0)}")
                    print(f"   執行時間: {stats.get('execution_time', 0):.2f} 秒")
            else:
                print(f"⚠️ 來源驗證失敗：{pplx_result.get('error')}（不影響主流程）")
            
            return pplx_result
            
        except Exception as e:
            print(f"⚠️ 來源驗證發生錯誤: {str(e)}（不影響主流程）")
            return {'success': False, 'error': str(e)}
    
    def _run_stage_6_save_to_db(
        self,
        esg_id: str,
        year: int,
        company_code: str,
        company_name: str,
        industry: str,
        report_info: dict,
        analysis_result: dict
    ) -> dict:
        """
        Stage 6: 存入資料庫
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        print("\n--- Step 7: 存入資料庫 ---")
        update_analysis_status(esg_id, 'stage6')
        
        # 讀取 P3 JSON（最終分析結果）
        p3_path = os.path.join(PATHS['P3_JSON'], f'{year}_{company_code}_p3.json')
        
        if not os.path.exists(p3_path):
            print(f"❌ P3 JSON 不存在: {p3_path}")
            update_analysis_status(esg_id, 'failed')
            return {
                'success': False,
                'message': f'分析流程未完成：找不到 P3 JSON 檔案 ({p3_path})。請確認 Step 5 (AI 驗證與評分調整) 和 Step 6 (來源可靠度驗證) 已成功執行。'
            }
        
        with open(p3_path, 'r', encoding='utf-8') as f:
            final_analysis_items = json.load(f)
        print(f"📂 載入 P3 JSON: {len(final_analysis_items)} 筆分析項目")
        
        # 提取基本資訊
        report_url = analysis_result.get('url', f"https://mops.twse.com.tw/mops/web/t100sb07_{year}")
        
        insert_success, insert_msg = insert_analysis_results(
            esg_id=esg_id,
            company_name=company_name,
            industry=industry,
            url=report_url,
            analysis_items=final_analysis_items
        )
        
        if not insert_success:
            update_analysis_status(esg_id, 'failed')
            return {
                'success': False,
                'message': f'插入分析結果失敗: {insert_msg}'
            }
        
        return {
            'success': True,
            'message': '資料已成功存入資料庫'
        }


# 建立全域實例
pipeline = ESGAnalysisPipeline()


def run_full_analysis(
    esg_id: str,
    year: int,
    company_code: str,
    company_name: str,
    industry: str,
    report_info: dict
) -> dict:
    """
    便捷函數：執行完整 ESG 分析流程
    
    這是 ESGAnalysisPipeline.run_analysis() 的便捷封裝
    """
    return pipeline.run_analysis(
        esg_id=esg_id,
        year=year,
        company_code=company_code,
        company_name=company_name,
        industry=industry,
        report_info=report_info
    )
