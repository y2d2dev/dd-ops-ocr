#!/usr/bin/env python3
"""
Vertex AI統合テストスクリプト
"""
import os
import sys

def test_imports():
    """インポートテスト"""
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig, Image
        print("✅ Vertex AI imports successful")
        return True
    except ImportError as e:
        print(f"❌ Vertex AI imports failed: {e}")
        return False

def test_environment():
    """環境変数テスト"""
    project_id = os.getenv('GCP_PROJECT_ID')
    location = os.getenv('GCP_LOCATION', 'us-central1')

    if not project_id:
        print("❌ GCP_PROJECT_ID environment variable not set")
        return False

    print(f"✅ GCP_PROJECT_ID is set: {project_id}")
    print(f"✅ GCP_LOCATION is set: {location}")
    return True

def test_vertex_ai_initialization():
    """Vertex AI初期化テスト"""
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        project_id = os.getenv('GCP_PROJECT_ID')
        location = os.getenv('GCP_LOCATION', 'us-central1')

        if not project_id:
            print("❌ Cannot test initialization: GCP_PROJECT_ID not set")
            return False

        # 初期化テスト（実際のAPI呼び出しは行わない）
        vertexai.init(project=project_id, location=location)
        model = GenerativeModel('gemini-2.5-flash')

        print("✅ Vertex AI initialization successful")
        return True

    except Exception as e:
        print(f"❌ Vertex AI initialization failed: {e}")
        return False

def test_modules():
    """プロジェクトモジュールのインポートテスト"""
    try:
        # step6のテスト
        sys.path.append('/app/src')
        # インポートの代わりに直接ファイルを実行
        import importlib.util

        # step6のテスト
        spec = importlib.util.spec_from_file_location("gemini_ocr_engine", "/app/src/modules/step6/01_gemini_ocr_engine.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        GeminiOCREngine = module.GeminiOCREngine
        print("✅ Step6 GeminiOCREngine import successful")

        # step4のテスト
        spec = importlib.util.spec_from_file_location("page_count_evaluator", "/app/src/modules/step4/01_page_count_evaluator.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        PageCountEvaluator = module.PageCountEvaluator
        print("✅ Step4 PageCountEvaluator import successful")

        return True

    except ImportError as e:
        print(f"❌ Module imports failed: {e}")
        return False

def main():
    """メインテスト関数"""
    print("=== Vertex AI Integration Test ===")

    tests = [
        ("Import Test", test_imports),
        ("Environment Test", test_environment),
        ("Vertex AI Initialization Test", test_vertex_ai_initialization),
        ("Module Import Test", test_modules)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append(result)

    print("\n=== Summary ===")
    passed = sum(results)
    total = len(results)

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())