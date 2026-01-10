import jieba
import os
from collections import Counter
import pdfplumber
import time
import json
import glob

start_time = time.time()

def extract_text_from_pdf(pdf_path):
    '''
    讀取 PDF 並提取文字（返回字符串）
    '''
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

# 設定參數 (用於 demo 或從外部傳入)
company_code = "1102" 
year = "2024"

# 取得 PDF 所在目錄的絕對路徑
base_dir = os.path.dirname(os.path.abspath(__file__))  # word_cloud 資料夾
pdf_dir = os.path.join(base_dir, "..", "temp_data", "esgReport")
pdf_dir = os.path.abspath(pdf_dir)  # 轉換為絕對路徑

# 使用 glob 匹配符合格式的 PDF 檔案: {year}_{company_code}_*.pdf
pattern = os.path.join(pdf_dir, f"{year}_{company_code}_*.pdf")
matched_files = glob.glob(pattern)

if not matched_files:
    error_msg = f"找不到符合格式的 PDF 檔案: {pattern}\n請確認檔案存在於: {pdf_dir}"
    print(error_msg)
    raise FileNotFoundError(error_msg)
elif len(matched_files) > 1:
    error_msg = f"找到多個符合的檔案: {matched_files}\n將使用第一個檔案: {matched_files[0]}"
    print(error_msg)
    text = extract_text_from_pdf(matched_files[0])
else:
    print(f"找到檔案: {matched_files[0]}")
    text = extract_text_from_pdf(matched_files[0])

##### 讀取自訂辭檔 #####
filePath = os.path.dirname(os.path.abspath(__file__))

try:
    for filename in ["esg_dict.txt", "fuzzy_dict.txt"]:
        full_path = f"{filePath}/{filename}"
        jieba.load_userdict(full_path)
except Exception as e:
    print(f"提醒：字典檔讀取失敗 ({e})，將僅使用預設斷詞。")

#####讀取停用詞檔#####
with open(f'{filePath}/stopword_list.txt', 'r', encoding='utf-8') as f:
    stopwords = set(f.read().splitlines())

# 3. 斷詞並過濾雜訊
words = jieba.lcut(text)

# 過濾掉停用詞、標點符號和單字 (長度 < 2 的通常是雜訊，如 "的", "在")
filtered_words = [w for w in words if len(w) >= 2 and w != '\n' and w not in stopwords]

# 4. 計算字頻，使用Counter將輸入轉化為次數
word_counts = Counter(filtered_words)

# 輸出JSON檔供前端生成文字雲
word_cloud_json = [{"name": word, "value": count} for word, count in word_counts.most_common(100)]
output_dir = os.path.join(base_dir, "wc_output")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 輸出 JSON 檔名格式: {year}_{company_code}_wc.json
output_filename = f"{year}_{company_code}_wc.json"
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
