import jieba
import os
import matplotlib.pyplot as plt
from collections import Counter
from wordcloud import WordCloud
import pdfplumber
import time
import json

start_time = time.time()


def extract_text_from_pdf(pdf_path):
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

# 指定 PDF 路徑 (請依需求修改)
pdf_file_path = r"../esgReport/亞泥2024永續報告書.pdf"

# 取得 PDF 絕對路徑
base_dir = os.path.dirname(os.path.abspath(__file__)) # word_cloud 資料夾
# 因為檔案是在 word_cloud/esgReport 下，所以直接接 base_dir
pdf_full_path = os.path.join(base_dir, "esgReport", "亞泥2024永續報告書.pdf")

# 如果檔案不存在，嘗試另一個範例或報錯
if not os.path.exists(pdf_full_path):
    print(f"找不到檔案: {pdf_full_path}")
    # Fallback to hardcoded text if file not found (or raise error)
    text = '''本公司深知氣候變遷對全球環境帶來的嚴峻挑戰... (檔案讀取失敗，使用預設文字)'''
else:
    text = extract_text_from_pdf(pdf_full_path)

#####讀取自訂辭檔#####
filePath = os.path.dirname(os.path.abspath(__file__))

custom_keywords = set()
try:
    for filename in ["esg_dict.txt", "fuzzy_dict.txt"]:
        full_path = f"{filePath}/{filename}"
        jieba.load_userdict(full_path)
        with open(full_path, "r", encoding="utf-8") as f:
            for line in f:
                custom_keywords.add(line.split()[0])

except Exception as e:
    print(f"提醒：字典檔讀取失敗 ({e})，將僅使用預設斷詞。")

#####讀取停用詞檔#####
with open(f'{filePath}/stopword_list.txt', 'r', encoding='utf-8') as f:
    stopwords = set(f.read().splitlines())

# 3. 斷詞並過濾雜訊
words = jieba.lcut(text)

# 過濾掉標點符號和單字 (長度 < 2 的通常是雜訊，如 "的", "在")
filtered_words = [w for w in words if len(w) >= 2 and w != '\n']

# 4. 計算字頻，使用Counter將輸入轉化為次數
word_counts = Counter(filtered_words)

# 5. 進行關鍵詞統計
keywords_found = {k: v for k, v in word_counts.items() if k in custom_keywords}
total_keyword_count = sum(keywords_found.values())

# --- 顯示結果 ---

print(f"【總詞彙量 (去除標點後)】: {len(filtered_words)}")
print("-" * 30)

print(f"【全文章 - 出現頻率最高的 5 個詞】:")
for word, count in word_counts.most_common(5):
    print(f"{word}: {count}")
print("-" * 30)

print(f"【自訂關鍵詞統計 (共 {total_keyword_count} 次)】:")
for word, count in keywords_found.items():
    print(f"  - {word}: {count}")

# 輸出JSON檔供前端生成文字雲
print("-" * 30)
print("正在輸出JSON檔...")

word_cloud_json = [{"name": word, "value": count} for word, count in word_counts.most_common(100)]
output_dir = os.path.join(base_dir, "wc_output")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# demo用
company_code = "1102" 
year = "2024"

# 檔名範例 company_code_year_wc.json
output_filename = f"{company_code}_{year}_wc.json"
output_path = os.path.join(output_dir, output_filename)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(word_cloud_json, f, ensure_ascii=False, indent=2)

print(f"JSON檔已儲存至: {output_path}")

#==========生成文字雲png==========
# # 6. 生成文字雲
# print("-" * 30)
# print("正在生成文字雲...")
# text_for_cloud = " ".join(filtered_words)

# # Windows 預設字體路徑 (微軟正黑體)
# font_path = "C:/Windows/Fonts/msjh.ttc"

# 建立 WordCloud 物件
# wc = WordCloud(
#     font_path=font_path,
#     stopwords=stopwords,
#     width=800,
#     height=400,
#     max_words=80,
#     background_color="white",
#     prefer_horizontal=0.9
# ).generate(text_for_cloud)

# # 顯示文字雲
# plt.figure(figsize=(10, 5))
# plt.imshow(wc, interpolation="bilinear")
# plt.axis("off")
# plt.title("ESG Word Cloud", fontsize=20)

# # 確保輸出目錄存在
# output_dir = os.path.join(base_dir, "wc_output")
# if not os.path.exists(output_dir):
#     os.makedirs(output_dir)
# # 先存檔，再顯示 (避免 show() 清空畫布導致存成白圖)
# output_path = os.path.join(output_dir, "company_num_word_cloud.png")
# plt.savefig(output_path)
# print(f"文字雲已儲存至: {output_path}")

# plt.show()
#==========生成文字雲png==========


end_time = time.time()
execution_time = end_time - start_time
print(f"程式執行時間: {execution_time:.2f} 秒")

# 待加強功能---
# 需分成讀取PDF以及抓取現有資料
