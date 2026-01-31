"""
Vertex AI 遷移驗證腳本
此腳本用於驗證 Vertex AI 配置是否正確，並測試基本功能。
"""

# 必要套件 google-cloud-aiplatform
# 確保登入 gcloud
# 環境變數 GCP_PROJECT_ID
# 環境變數 GCP_LOCATION

#===測試邏輯===
# 1. 優先使用 GCP_PROJECT_ID → Vertex AI
# 2. 若未設定，則使用 GEMINI_API_KEY → GenAI SDK
# 3. 兩者都未設定 → 報錯

import os
import sys
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

def test_environment_variables():
    """檢查必要的環境變數"""
    print("=" * 60)
    print("1. 檢查環境變數")
    print("=" * 60)
    
    project_id = os.getenv("GCP_PROJECT_ID")
    location = os.getenv("GCP_LOCATION")
    api_key = os.getenv("GEMINI_API_KEY")
    
    print(f"GCP_PROJECT_ID: {project_id or '❌ 未設定'}")
    print(f"GCP_LOCATION: {location or '使用預設值 asia-northeast1'}")
    print(f"GEMINI_API_KEY: {'✅ 已設定 (備用)' if api_key else '未設定 (純 Vertex AI 模式)'}")
    
    if project_id:
        print("\n✅ 將使用 Vertex AI")
        return True, "vertex"
    elif api_key:
        print("\n⚠️ 將回退到 GenAI SDK")
        return True, "genai"
    else:
        print("\n❌ 錯誤：請至少設定 GCP_PROJECT_ID 或 GEMINI_API_KEY")
        return False, None

def test_vertex_ai_import():
    """測試 Vertex AI SDK 是否正確安裝"""
    print("\n" + "=" * 60)
    print("2. 測試 Vertex AI SDK")
    print("=" * 60)
    
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part
        print("✅ Vertex AI SDK 已正確安裝")
        return True
    except ImportError as e:
        print(f"❌ Vertex AI SDK 導入失敗: {e}")
        print("請執行: pip install google-cloud-aiplatform")
        return False

def test_genai_sdk_import():
    """測試 GenAI SDK 是否正確安裝（備用）"""
    print("\n" + "=" * 60)
    print("3. 測試 GenAI SDK (備用)")
    print("=" * 60)
    
    try:
        from google import genai
        from google.genai import types
        print("✅ GenAI SDK 已正確安裝")
        return True
    except ImportError as e:
        print(f"⚠️ GenAI SDK 未安裝（可選）: {e}")
        return False

def test_vertex_ai_init():
    """測試 Vertex AI 初始化"""
    print("\n" + "=" * 60)
    print("4. 測試 Vertex AI 初始化")
    print("=" * 60)
    
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("⚠️ 跳過（未設定 GCP_PROJECT_ID）")
        return True
    
    try:
        import vertexai
        location = os.getenv("GCP_LOCATION", "asia-northeast1")
        
        print(f"初始化 Vertex AI...")
        print(f"  專案: {project_id}")
        print(f"  區域: {location}")
        
        vertexai.init(project=project_id, location=location)
        print("✅ Vertex AI 初始化成功")
        return True
    except Exception as e:
        print(f"❌ Vertex AI 初始化失敗: {e}")
        print("\n可能的原因：")
        print("1. 未執行 gcloud auth application-default login")
        print("2. Vertex AI API 未啟用")
        print("3. 服務帳戶權限不足")
        return False

def test_model_creation():
    """測試模型創建"""
    print("\n" + "=" * 60)
    print("5. 測試模型創建")
    print("=" * 60)
    
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("⚠️ 跳過（使用 GenAI SDK 模式）")
        return True
    
    try:
        from vertexai.generative_models import GenerativeModel
        
        model = GenerativeModel("gemini-2.0-flash-exp")
        print("✅ 模型創建成功 (gemini-2.0-flash-exp)")
        return True
    except Exception as e:
        print(f"❌ 模型創建失敗: {e}")
        print("\n嘗試使用備用模型...")
        
        try:
            model = GenerativeModel("gemini-1.5-flash-002")
            print("✅ 模型創建成功 (gemini-1.5-flash-002)")
            return True
        except Exception as e2:
            print(f"❌ 備用模型也失敗: {e2}")
            return False

def test_imports_from_project():
    """測試專案模組導入"""
    print("\n" + "=" * 60)
    print("6. 測試專案模組導入")
    print("=" * 60)
    
    # 將專案根目錄加入 Python 路徑
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    try:
        from config import PATHS, DATA_FILES
        print("✅ config.py 導入成功")
    except ImportError as e:
        print(f"❌ config.py 導入失敗: {e}")
        return False
    
    try:
        from src import gemini_api
        print("✅ gemini_api.py 導入成功")
    except ImportError as e:
        print(f"❌ gemini_api.py 導入失敗: {e}")
        return False
    
    try:
        from src import run_prompt2_gemini
        print("✅ run_prompt2_gemini.py 導入成功")
    except ImportError as e:
        print(f"❌ run_prompt2_gemini.py 導入失敗: {e}")
        return False
    
    return True

def main():
    """主測試函數"""
    print("\n" + "=" * 60)
    print("Vertex AI 遷移驗證測試")
    print("=" * 60)
    
    tests = [
        ("環境變數檢查", test_environment_variables),
        ("Vertex AI SDK", test_vertex_ai_import),
        ("GenAI SDK (備用)", test_genai_sdk_import),
        ("Vertex AI 初始化", test_vertex_ai_init),
        ("模型創建", test_model_creation),
        ("專案模組導入", test_imports_from_project),
    ]
    
    results = []
    mode = None
    
    for name, test_func in tests:
        try:
            if name == "環境變數檢查":
                success, mode = test_func()
            else:
                success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ 測試 '{name}' 發生異常: {e}")
            results.append((name, False))
    
    # 顯示測試總結
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ 通過" if success else "❌ 失敗"
        print(f"{status} - {name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n總計: {passed}/{total} 項測試通過")
    
    if mode == "vertex":
        print("\n🎉 恭喜！您的環境已配置為使用 Vertex AI")
    elif mode == "genai":
        print("\n⚠️ 目前使用 GenAI SDK 備用模式")
    
    if passed == total:
        print("\n✅ 所有測試通過！可以開始使用 Vertex AI 了")
        return 0
    else:
        print("\n⚠️ 部分測試失敗，請檢查上述錯誤訊息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
