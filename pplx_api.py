#➡️需和app.py, index.htnl整合code⬅️
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS #pip install flask-cors
import requests
import json
import os
from perplexity import Perplexity
from google import genai
from dotenv import load_dotenv
load_dotenv()
from pplx_api.config import SystemConfig


app = Flask(__name__)
CORS(app)
# 載入 API 金鑰
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
perplexity_client = Perplexity(api_key=os.environ.get("PERPLEXITY_API_KEY"))
config = SystemConfig('esg_news_system.json')

# 常數配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = config.get_timeout()

def generate_urls_with_gemini(company, year):
    """使用 Gemini 生成 ESG 新聞 URL"""
    try:
        
        PROMPT = config.get_gemini_prompt(company, year)
        
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=PROMPT,
            config={
                'temperature': 0,
                'max_tokens' : 500,
                'response_mime_type': 'application/json'
            }
        )
        
        result = json.loads(response.text)
        if isinstance(result, list):
            return result
        # 如果它包在 urls 鍵值裡，則取出來
        if isinstance(result, dict):
            return result.get('urls', result.get('news_list', []))
            
        return []
    except Exception as e:
        print(f"解析失敗: {e}")
        return []

def verify_single_url(url):
    """驗證單一 URL 的有效性"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        
        if response.status_code == 200:
            # 提取頁面標題
            text = response.text
            title_start = text.find('<title>') + 7
            title_end = text.find('</title>', title_start)
            page_title = text[title_start:title_end].strip() if title_start > 6 else "無法解析標題"
            
            return {
                "url": url,
                "is_valid": True,
                "page_title": page_title,
                "status_code": response.status_code
            }
        else:
            return {
                "url": url,
                "is_valid": False,
                "page_title": None,
                "status_code": response.status_code
            }
    
    except requests.exceptions.RequestException as e:
        return {
            "url": url,
            "is_valid": False,
            "page_title": None,
            "error": str(e)
        }

def verify_urls_batch(urls):
    """批次驗證多個 URL"""
    results = {
        "valid_urls": [],
        "invalid_urls": [],
        "valid_count": 0
    }
    
    for url in urls:
        result = verify_single_url(url)
        if result["is_valid"]:
            results["valid_urls"].append(result)
            results["valid_count"] += 1
        else:
            results["invalid_urls"].append(result)
    
    return results

def search_with_perplexity(company, year):
    """使用 Perplexity 即時搜索 ESG 新聞"""
    try:
        prompt = f"""提供「{company}」在{year}年的2-4個ESG相關新聞URL。
        要求：
        1. URL 必須真實存在且可訪問
        2. 與 ESG 主題相關
        僅輸出 JSON 格式：
        {{
            "news_list": [
                {{"title": "標題", "url": "網址"}}
            ]
        }}"""
        
        response = perplexity_client.chat.completions.create(
            model="sonar",
            messages=[
                {"role": "system", "content": "你是 ESG 新聞搜索專家，只輸出有效的 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0
            # response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # 驗證 Perplexity 返回的 URL
        news_list = result.get('news_list', [])
        verified_news = []
        
        for news in news_list:
            url_check = verify_single_url(news['url'])
            if url_check['is_valid']:
                news['validation_status'] = 'verified'
                verified_news.append(news)
        
        return verified_news
    
    except Exception as e:
        print(f"Perplexity 搜索失敗: {e}")
        return []


@app.route('/')
def home():
    return render_template('index.html') 

@app.route('/api/search-esg-news', methods=['POST'])  #html尾部的const區塊需來fetch這欄
def search_esg_news():
    """主要 API 端點"""
    try:
        # 步驟 1: 接收並驗證輸入
        data = request.json
        company = data.get('company_name', '').strip()
        year = data.get('year')
        
        if not company or not year:
            return jsonify({"error": "缺少必要資訊"}), 400
        
        # 步驟 2: 呼叫 Gemini 生成 URL
        gemini_urls = generate_urls_with_gemini(company, year)
        
        if not gemini_urls:
            # Gemini 失敗，直接使用 Perplexity
            final_results = search_with_perplexity(company, year)
            return jsonify({
                'company': company,
                'year': year,
                'news_list': final_results,
                'source': 'perplexity_only',
                'gemini_failed': True
            })
        
        # 步驟 3: 驗證 Gemini 生成的 URL
        validated_results = verify_urls_batch(gemini_urls)
        
        # 步驟 4: 決策點
        if validated_results['valid_count'] > 0:
            # 有有效 URL，直接回傳
            news_list = [
                {
                    'title': news['page_title'],
                    'url': news['url'],
                    'source': 'gemini_verified',
                    'validation_status': 'verified'
                }
                for news in validated_results['valid_urls']
            ]
            
            return jsonify({
                'company': company,
                'year': year,
                'news_list': news_list,
                'source': 'gemini',
                'used_fallback': False,
                'stats': {
                    'valid_count': validated_results['valid_count'],
                    'invalid_count': len(validated_results['invalid_urls'])
                }
            })
        else:
            # 全部無效，使用 Perplexity 備援
            perplexity_results = search_with_perplexity(company, year)
            
            return jsonify({
                'company': company,
                'year': year,
                'news_list': perplexity_results,
                'source': 'perplexity_fallback',
                'used_fallback': True,
                'gemini_urls_failed': len(gemini_urls)
            })
    
    except Exception as e:
        return jsonify({"error": f"伺服器錯誤: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)