import os
import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 0) 載入環境變數
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

# 1) 嘗試匯入 DB 函式（缺少也不會讓 A 爆炸）
get_company_reports = None
get_company_updates = None

try:
    from db_service_local import get_company_reports as _get_company_reports  # type: ignore
    get_company_reports = _get_company_reports
except Exception as e:
    print(f"⚠️ 匯入 get_company_reports 失敗：{e}")

try:
    from db_service_local import get_company_updates as _get_company_updates  # type: ignore
    get_company_updates = _get_company_updates
except Exception as e:
    # C 的資料介面可先沒有（你剛剛測到 [] 就是這層資料不足），但主程式仍可保底回覆
    print(f"⚠️ 匯入 get_company_updates 失敗（C 仍可保底回覆）：{e}")

# 2) Flask / LINE 初始化
app = Flask(__name__)

def require_env():
    missing = []
    if not LINE_CHANNEL_ACCESS_TOKEN:
        missing.append("LINE_CHANNEL_ACCESS_TOKEN")
    if not LINE_CHANNEL_SECRET:
        missing.append("LINE_CHANNEL_SECRET")
    if missing:
        raise RuntimeError(
            "❌ .env 缺少必要設定："
            + ", ".join(missing)
            + "\n請確認：\n"
            + "1) 你有建立 .env（不是 .env.example）\n"
            + "2) .env 跟你執行 python 的工作目錄同一層\n"
            + "3) 內容沒有多餘引號或空白\n"
        )

require_env()

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# 3) Session（每個使用者的狀態）
# user_sessions[user_id] 結構：
# {
#   "state": "WAITING_CODE" | "LOCKED",
#   "company_input": "1102" or "亞泥",
#   "company_id": "1102",
#   "company_name": "亞泥",
#   "last_updates": [ {"title":..., "date":..., "content":..., "url":...}, ... ],
#   "awaiting_update_choice": True/False
# }
user_sessions: Dict[str, Dict[str, Any]] = {}

def normalize(text: str) -> str:
    return (text or "").strip().replace(" ", "")

def is_trigger_a(norm: str) -> bool:
    return ("企業ESG分析" in norm) or ("開始分析" in norm)

def is_trigger_b(norm: str) -> bool:
    # 你的 Rich Menu B 文案可能是：⚖【企業 ESG風險分析】 or 風險分析
    return ("ESG風險" in norm) or ("風險分析" in norm) or ("風險快覽" in norm)

def is_trigger_c(norm: str) -> bool:
    # 你的 Rich Menu C 文案可能是：最新消息
    return ("最新消息" in norm) or ("企業最新消息" in norm) or ("動態" in norm)

def is_choice_number(norm: str) -> Optional[int]:
    # 使用者回覆 1~9 看詳情
    m = re.fullmatch(r"[1-9]", norm)
    if not m:
        return None
    return int(norm)

# 4) OpenAI 摘要（B / C 可共用）
def summarize_with_openai(prompt: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    try:
        # 新版 openai 套件（openai>=1.x）
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "你是嚴謹的ESG分析助理，輸出需精簡、條列、避免浮誇。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content or ""
        return text.strip()
    except Exception as e:
        print(f"⚠️ OpenAI 摘要失敗：{e}")
        return None

# 5) B：把 DB 資料整理成「5~8行」風險快覽（含保底）
def build_b_risk_brief(company_id: str, company_name: str) -> str:
    if not get_company_reports:
        return "⚠️ 目前無法讀取資料庫（DB 模組未載入），請稍後再試。"

    rows = []
    try:
        # 這裡用 company_id 作為 user_input（你的 DB 函式支援 id 或 name）
        rows = get_company_reports(company_id) or []
    except Exception as e:
        return f"⚠️ 讀取資料庫失敗：{e}"

    # 若 DB 沒資料，仍要回話
    if not rows:
        return (
            f"⚖️【{company_name} ESG風險快覽】\n"
            "• 目前資料庫尚無可用報告資料。\n"
            "• 建議：先由爬蟲/匯入補齊 company_report。\n"
            "• 你也可以先測試 C（最新消息）按鈕。"
        )

    # 取前幾筆資料當摘要素材（避免 prompt 太長）
    sample = rows[:6]
    # 把可能有用的欄位拼成素材（欄位名不確定，所以用 get）
    bullets = []
    for r in sample:
        esg = r.get("esg_domain") or r.get("ESG領域") or ""
        topic = r.get("sasb_topic") or r.get("SASB細項") or r.get("topic") or ""
        claim = r.get("report_claim") or r.get("聲稱") or ""
        evidence = r.get("external_evidence") or r.get("新聞/官方資料") or ""
        risk = r.get("risk_score") or r.get("風險評分") or ""
        line = f"- ({esg}/{topic}) claim:{claim} evidence:{evidence} risk:{risk}"
        bullets.append(line)

    prompt = (
        f"公司：{company_id} {company_name}\n"
        "以下是資料庫中的ESG相關片段，請你整理成【企業 ESG風險快覽】。\n"
        "規則：\n"
        "1) 用繁體中文\n"
        "2) 輸出 5~8 行，以 '• ' 條列\n"
        "3) 必須包含：一行總結、以及一行風險評分（若素材沒有分數就用 '資料不足'）\n"
        "4) 內容要像 demo 用：精簡、可讀、可直接貼到 LINE\n\n"
        "素材：\n" + "\n".join(bullets)
    )

    llm = summarize_with_openai(prompt)
    if llm:
        # 確保有標題
        if "【" not in llm[:20]:
            llm = f"⚖️【{company_name} ESG風險快覽】\n" + llm
        return llm

    # 保底（不走 LLM）
    # 盡量從資料抓到一個風險分數
    risk_score = None
    for r in sample:
        v = r.get("risk_score") or r.get("風險評分")
        if v is not None and str(v).strip() != "":
            risk_score = v
            break

    return (
        f"⚖️【{company_name} ESG風險快覽】\n"
        "• 已取得資料庫報告片段，摘要模式：保底（未呼叫 LLM）。\n"
        f"• 片段數：{len(rows)}（取樣 {len(sample)}）\n"
        f"• 風險評分：{risk_score if risk_score is not None else '資料不足'}\n"
        "• 建議：補齊外部佐證/時間欄位，可提升可解釋性。\n"
        "• 可繼續點 C 查看最新消息。"
    )

# 6) C：最新消息列表 + 回覆數字看詳情（空資料也要回）
def build_c_updates_list(company_id: str, company_name: str, updates: List[Dict[str, Any]]) -> str:
    header = f"📢 {company_name}最新消息（更新至 2026/01）"
    if not updates:
        return (
            f"{header}\n"
            "• 目前資料庫尚無『最新消息』資料。\n"
            "• 你可以先由爬蟲/匯入建立 company_news 表，或先用 B 看風險快覽。"
        )

    lines = [header]
    for idx, u in enumerate(updates[:4], start=1):
        title = str(u.get("title") or "動態").strip()
        date = str(u.get("date") or "").strip()
        # 顯示短一點，避免換行爆版
        title = title.replace("\n", " ")
        if len(title) > 22:
            title = title[:22] + "…"
        suffix = f" - {date}" if date else ""
        lines.append(f"▶ {idx}. {title}{suffix}（回覆 {idx} 查看詳情）")
    return "\n".join(lines)

def build_c_update_detail(company_name: str, chosen: Dict[str, Any], idx: int) -> str:
    title = str(chosen.get("title") or "動態").strip()
    date = str(chosen.get("date") or "").strip()
    content = str(chosen.get("content") or "").strip()
    url = str(chosen.get("url") or "").strip()

    # 若內容過長，截短（LINE 一則訊息不要爆）
    if len(content) > 600:
        content = content[:600] + "…"

    msg = [f"📌【{company_name} 最新消息 #{idx}】"]
    if date:
        msg.append(f"日期：{date}")
    msg.append(f"標題：{title}")
    if content:
        msg.append("\n內容摘要：\n" + content)
    if url:
        msg.append("\n更多連結：\n" + url)
    return "\n".join(msg)

# 7) Callback
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK", 200

# 8) Message Handler
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    norm = normalize(text)

    print("收到訊息：", repr(text), " / norm:", repr(norm))

    sess = user_sessions.get(user_id, {})

    # (0) 若正在等使用者輸入「選擇編號」看 C 詳情
    if sess.get("awaiting_update_choice"):
        choice = is_choice_number(norm)
        if choice is not None:
            updates = sess.get("last_updates") or []
            if 1 <= choice <= len(updates):
                detail = build_c_update_detail(sess.get("company_name", "公司"), updates[choice - 1], choice)
                send_reply(event, detail)
            else:
                send_reply(event, "❌ 編號超出範圍，請回覆 1~4")
            return
        # 不是數字就不擋，讓使用者仍可按其他按鈕

    # (A) 開始分析
    if is_trigger_a(norm):
        user_sessions[user_id] = {"state": "WAITING_CODE"}
        send_reply(
            event,
            "✅ A 已成功觸發！\n"
            "請輸入公司代碼或公司名稱（例如：1102 或 亞泥）"
        )
        return

    # (A2) 等公司代碼
    if sess.get("state") == "WAITING_CODE":
        # 目前 demo 仍以 1102/亞泥 為主（你之後可擴充 DB 查 company 表）
        if norm in ["1102", "亞泥", "亞洲水泥", "亞洲水泥股份有限公司"]:
            user_sessions[user_id] = {
                "state": "LOCKED",
                "company_input": norm,
                "company_id": "1102",
                "company_name": "亞泥",
                "awaiting_update_choice": False,
                "last_updates": []
            }
            send_reply(event, "✅ 已鎖定：1102（亞泥）\n請點選 B（風險）或 C（最新消息）")
        else:
            send_reply(event, "❌ 目前 demo 僅支援：1102 / 亞泥\n請重新輸入。")
        return

    # 需要先鎖定公司才可做 B / C
    if sess.get("state") != "LOCKED":
        # 使用者若直接按 B/C，友善引導去按 A
        if is_trigger_b(norm) or is_trigger_c(norm):
            send_reply(event, "⚠️ 請先點 A（開始分析）並輸入公司代碼/名稱完成鎖定。")
        return

    company_id = sess.get("company_id", "1102")
    company_name = sess.get("company_name", "亞泥")

    # (B) 風險分析
    if is_trigger_b(norm):
        brief = build_b_risk_brief(company_id, company_name)
        # B 的結果回完後，不要卡住數字選單狀態
        sess["awaiting_update_choice"] = False
        user_sessions[user_id] = sess
        send_reply(event, brief)
        return

    # (C) 最新消息（列表）
    if is_trigger_c(norm):
        updates: List[Dict[str, Any]] = []
        if get_company_updates:
            try:
                updates = get_company_updates(company_id, 4) or []
                # 確保是 list[dict]
                if not isinstance(updates, list):
                    updates = []
            except Exception as e:
                print(f"⚠️ 取得最新消息失敗：{e}")
                updates = []

        # 存 session 讓使用者回覆 1~4 看詳情
        sess["last_updates"] = updates[:4]
        sess["awaiting_update_choice"] = True if updates else False
        user_sessions[user_id] = sess

        msg = build_c_updates_list(company_id, company_name, updates)
        send_reply(event, msg)
        return

    # 其他訊息不回（避免亂回）
    return

# 9) Reply helper
def send_reply(event, text: str):
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=text)]
        )
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
