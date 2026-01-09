import os
from dotenv import load_dotenv  
import google.generativeai as genai
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 【重要】請確保你的 DB 檔名與函式名正確
# 如果他們改了檔名，請修改下面這一行
from db_service import get_company_reports 

app = Flask(__name__)

# --- 1. 設定與初始化 (.env 版) ---
load_dotenv() 

# 從環境變數抓取 (大小寫必須與 .env 檔案完全一致)
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# LINE Bot 初始化
configuration = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# Gemini 初始化
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 暫存使用者鎖定的公司
user_sessions = {}

# --- 2. 極簡 Prompt 函式 (已針對 LINE 閱讀優化) ---
def get_gemini_summary(mode, data):
    if mode == "risk":
        prompt = (
            "你是一位專業 ESG 稽核員。請針對數據進行「極簡條列式」風險分析。\n"
            "規則：\n"
            "1. 僅列出 5 個核心重點，每點不超過 25 字。\n"
            "2. 使用「●」作為開頭。\n"
            f"數據內容：{data}"
        )
    else:  # news
        prompt = (
            "你是一位財經新聞主編。請針對最新動態進行「五點精華摘要」。\n"
            "規則：\n"
            "1. 僅列出 5 則最關鍵消息。\n"
            "2. 使用「📍」作為開頭，每點不超過 20 字。\n"
            f"內容：{data}"
        )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI 摘要生成失敗：{str(e)}"

# --- 3. 路由與事件處理 ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

def send_reply(event, text):
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=text)]
        )
    )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text

    # 按鈕 A：鎖定公司
    if user_text == "🏢 【鎖定查詢公司】":
        user_sessions[user_id] = "1102"
        send_reply(event, "✅ 已鎖定查詢公司：亞泥 (1102)\n現在您可以點擊 B 或 C 按鈕進行分析。")

    # 按鈕 B：風險分析
    elif user_text == "⚠️ 【ESG 風險分析】":
        company = user_sessions.get(user_id)
        if company:
            reports = get_company_reports(company)
            if reports:
                # 這裡根據你的截圖欄位可能叫 'report_claim' 或 'summary'
                # 我先維持你上傳檔案中的欄位名
                raw_data = reports[0].get('report_claim', "無數據")
                summary = get_gemini_summary("risk", raw_data)
                send_reply(event, f"⚖️ 【ESG 極簡風險稽核】\n------------------\n{summary}")
            else:
                send_reply(event, "❌ 找不到該公司的風險數據。")
        else:
            send_reply(event, "💡 請先按 A 選擇查詢的公司。")

    # 按鈕 C：最新消息
    elif user_text == "📰 【最新動態摘要】":
        company = user_sessions.get(user_id)
        if company:
            reports = get_company_reports(company)
            if reports:
                raw_data = reports[0].get('report_claim', "無數據")
                summary = get_gemini_summary("news", raw_data)
                send_reply(event, f"📢 【ESG 五點精華摘要】\n------------------\n{summary}")
            else:
                send_reply(event, "❌ 找不到最新消息數據。")
        else:
            send_reply(event, "💡 請先按 A 選擇查詢的公司。")

    # 按鈕 E：公司資訊
    elif user_text == "🏭 【公司資訊】":
        company = user_sessions.get(user_id)
        if company:
            reports = get_company_reports(company)
            if reports:
                # 根據你的 code 抓取外部證據與連結
                evidence = reports[0].get('external_evidence', '無資訊')
                url = reports[0].get('external_evidence_url', '無連結')
                reply = f"🏢 亞泥 (1102) 外部查核資訊：\n\n{evidence}\n\n🔗 來源：{url}"
                send_reply(event, reply)
            else:
                send_reply(event, "❌ 無法取得公司資訊。")
        else:
            send_reply(event, "💡 請先按 A 選擇公司。")

    # 按鈕 F：幫助
    elif user_text == "📘 【使用說明】":
        send_reply(event, "🌟 ESG-LAB 智能助理：\nA.鎖定公司\nB.風險分析\nC.精選動態\nD.數據圖表\nE.查核證據\nF.幫助說明")

if __name__ == "__main__":
    app.run(port=5000)