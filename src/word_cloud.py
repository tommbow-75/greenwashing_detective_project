"""
Word Cloud 文字雲生成模組

提供從 ESG 報告書 PDF 生成文字雲 JSON 的功能。

主要函數：
    generate_wordcloud: 生成文字雲 JSON 檔案

使用範例：
    # 基本使用
    from word_cloud.word_cloud import generate_wordcloud
    
    result = generate_wordcloud(year=2024, company_code="1102")
    if result['success']:
        print(f"生成成功: {result['output_file']}")
"""

import jieba
import os
import sys
from collections import Counter
import pdfplumber
import time
import json
import glob
from typing import Dict, List, Optional

# 導入集中配置
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import PATHS, DATA_FILES

# 模組常數 - 使用 config.py 的路徑定義
DICT_DIR = PATHS['STATIC_DICT']  # 字典檔目錄
OUTPUT_DIR = PATHS['WORD_CLOUD_OUTPUT']  # 文字雲輸出目錄
PDF_DIR = PATHS['ESG_REPORTS']  # PDF 報告書目錄


def _extract_text_from_pdf(pdf_path: str) -> str:
    """
    讀取 PDF 並提取文字
    
    Args:
        pdf_path: PDF 檔案路徑
    
    Returns:
        str: 提取的文字內容
    """
    print(f"正在讀取 PDF: {pdf_path} ...")
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                if (i + 1) % 10 == 0:
                    print(f"  已處理 {i + 1} 頁...")
        print("PDF 讀取完成。")
        return text
    except Exception as e:
        print(f"PDF 讀取失敗: {e}")
        return ""


def _load_dictionaries() -> None:
    """載入自訂詞典"""
    try:
        for filename in ["esg_dict.txt", "fuzzy_dict.txt"]:
            full_path = os.path.join(DICT_DIR, filename)
            if os.path.exists(full_path):
                jieba.load_userdict(full_path)
    except Exception as e:
        print(f"提醒：字典檔讀取失敗 ({e})，將僅使用預設斷詞。")


def _load_stopwords() -> set:
    """
    載入停用詞
    
    Returns:
        set: 停用詞集合
    """
    stopwords_path = os.path.join(DICT_DIR, "stopword_list.txt")
    try:
        with open(stopwords_path, 'r', encoding='utf-8') as f:
            return set(f.read().splitlines())
    except Exception as e:
        print(f"警告：停用詞檔讀取失敗 ({e})，將使用空集合。")
        return set()


def generate_wordcloud(
    year: int,
    company_code: str,
    pdf_path: Optional[str] = None,
    force_regenerate: bool = False
) -> Dict:
    """
    生成 ESG 報告書的文字雲 JSON
    
    Args:
        year: 報告年份
        company_code: 公司代碼
        pdf_path: PDF 檔案路徑（選填，若未提供則自動搜尋）
        force_regenerate: 是否強制重新生成（預設 False，會檢查檔案是否已存在）
    
    Returns:
        dict: {
            'success': bool,           # 是否成功
            'output_file': str,        # JSON 檔案路徑
            'word_count': int,         # 關鍵字數量
            'top_keywords': list,      # 前 10 個關鍵字
            'skipped': bool,           # 是否因已存在而跳過
            'error': str               # 錯誤訊息（若有）
        }
    """
    start_time = time.time()
    
    # === 1. 建立輸出路徑 ===
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_filename = f"{year}_{company_code}_wc.json"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    # === 2. 檔案存在性檢查 ===
    if not force_regenerate and os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # 驗證格式正確
            if isinstance(existing_data, list) and len(existing_data) > 0:
                if all('name' in item and 'value' in item for item in existing_data[:5]):
                    top_10 = existing_data[:10] if len(existing_data) >= 10 else existing_data
                    
                    execution_time = time.time() - start_time
                    print(f"ℹ️ 文字雲 JSON 已存在，跳過生成 (耗時: {execution_time:.2f} 秒)")
                    
                    return {
                        'success': True,
                        'output_file': output_path,
                        'word_count': len(existing_data),
                        'top_keywords': [item['name'] for item in top_10],
                        'skipped': True
                    }
        except (json.JSONDecodeError, KeyError, IOError, TypeError) as e:
            print(f"⚠️ 現有檔案格式錯誤 ({e})，將重新生成")
    
    # === 3. 尋找 PDF 檔案 ===
    if pdf_path is None:
        pattern = os.path.join(PDF_DIR, f"{year}_{company_code}_*.pdf")
        matched_files = glob.glob(pattern)
        
        if not matched_files:
            return {
                'success': False,
                'error': f"找不到符合格式的 PDF 檔案: {pattern}"
            }
        elif len(matched_files) > 1:
            print(f"⚠️ 找到多個符合的檔案，將使用第一個: {matched_files[0]}")
            pdf_path = matched_files[0]
        else:
            pdf_path = matched_files[0]
            print(f"找到檔案: {pdf_path}")
    
    # === 4. 提取文字 ===
    text = _extract_text_from_pdf(pdf_path)
    if not text:
        return {
            'success': False,
            'error': 'PDF 文字提取失敗'
        }
    
    # === 5. 載入詞典和停用詞 ===
    _load_dictionaries()
    stopwords = _load_stopwords()
    
    # === 6. 斷詞並過濾 ===
    words = jieba.lcut(text)
    filtered_words = [
        w for w in words
        if len(w) >= 2 and w != '\n' and w not in stopwords
    ]
    
    # === 7. 計算字頻 ===
    word_counts = Counter(filtered_words)
    
    # === 8. 生成 JSON ===
    word_cloud_json = [
        {"name": word, "value": count}
        for word, count in word_counts.most_common(100)
    ]
    
    # === 9. 儲存檔案 ===
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(word_cloud_json, f, ensure_ascii=False, indent=2)
        
        top_10 = word_cloud_json[:10] if len(word_cloud_json) >= 10 else word_cloud_json
        execution_time = time.time() - start_time
        
        print(f"✅ JSON 檔已儲存至: {output_path}")
        print(f"⏱️ 程式執行時間: {execution_time:.2f} 秒")
        
        return {
            'success': True,
            'output_file': output_path,
            'word_count': len(word_cloud_json),
            'top_keywords': [item['name'] for item in top_10],
            'skipped': False
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'儲存 JSON 失敗: {str(e)}'
        }


# =========================
# 命令列執行入口
# =========================

def main():
    """命令列執行的主函數"""
    print("=== ESG 報告書文字雲生成器 ===\n")
    
    year = input("請輸入年份 (預設 2024): ").strip() or "2024"
    company_code = input("請輸入公司代碼 (預設 1102): ").strip() or "1102"
    force = input("是否強制重新生成？(y/N): ").strip().lower() == 'y'
    
    print()
    result = generate_wordcloud(int(year), company_code, force_regenerate=force)
    
    print("\n" + "=" * 50)
    if result['success']:
        if result.get('skipped'):
            print(f"ℹ️ 文字雲已存在: {result['output_file']}")
        else:
            print(f"✅ 文字雲生成成功: {result['output_file']}")
        print(f"📊 關鍵字數量: {result['word_count']}")
        print(f"🔝 前 10 個關鍵字: {', '.join(result['top_keywords'])}")
    else:
        print(f"❌ 生成失敗: {result.get('error')}")
    print("=" * 50)


if __name__ == "__main__":
    main()
