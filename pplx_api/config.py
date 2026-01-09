import json
import os

class SystemConfig:
    def __init__(self, config_file='esg_news_system.json'):
        # 1. 取得 config.py 本身所在的「資料夾絕對路徑」 __file__ 代表這份 config.py 檔案
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 2. 將資料夾路徑與檔名組合在一起
        # 這樣會產生類似 C:\Users\Project\esg_news_system_json.json 的路徑
        full_path = os.path.join(current_dir, config_file)
        with open(full_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def get_gemini_prompt(self, company, year):
        # 從 JSON 讀取 prompt 模板
        template = self.config['workflow']['step_2_gemini_task']['prompt_template']['user']
        return template.replace('{company_name}', company).replace('{year}', str(year))
    
    def get_timeout(self):
        return self.config['error_handling']['global_timeout']