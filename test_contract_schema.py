#!/usr/bin/env python3
"""
convert_to_contract_schema関数のローカルテスト用スクリプト
"""
import os
import sys
import json
from typing import Optional, Dict, Any
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境変数チェック
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY環境変数が設定されていません")
    print("以下のコマンドで設定してください:")
    print("export GEMINI_API_KEY='your-api-key-here'")
    sys.exit(1)

try:
    import google.generativeai as genai
except ImportError:
    print("Error: google-generativeai パッケージがインストールされていません")
    print("以下のコマンドでインストールしてください:")
    print("pip install google-generativeai")
    sys.exit(1)

def read_local_file(file_path: str) -> Optional[str]:
    """
    ローカルファイルを読み取る（GCS用の関数の代わり）
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"ファイル読み取りエラー: {str(e)}")
        return None

def convert_to_contract_schema_local(text_file_path: str) -> Optional[Dict[str, Any]]:
    """
    ローカルテキストファイルをGeminiの構造化出力を使って契約書スキーマに変換
    
    Args:
        text_file_path: ローカルのテキストファイルパス
    
    Returns:
        構造化された契約書データまたはNone
    """
    try:
        # Gemini APIの設定
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 契約書スキーマの定義
        contract_schema = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "info": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "party": {"type": "string"},  # カンマ区切りの当事者名
                        "start_date": {"type": "string"},  # 空文字列で対応
                        "end_date": {"type": "string"},  # 空文字列で対応
                        "conclusion_date": {"type": "string"}  # 空文字列で対応
                    },
                    "required": ["title", "party"]
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "articles": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "article_number": {"type": "string"},  # "第1条" または "署名欄"
                                    "title": {"type": "string"},
                                    "content": {"type": "string"},
                                    "table_number": {"type": "string"}  # 表の場合のみ
                                },
                                "required": ["content", "title"]  # titleも必須にする
                            }
                        }
                    },
                    "required": ["articles"]
                }
            },
            "required": ["success", "info", "result"]
        }
        
        # ローカルファイルから内容を読み取り
        file_content = read_local_file(text_file_path)
        if not file_content:
            logger.warning(f"ファイル内容を読み取れませんでした: {text_file_path}")
            return None
        
        # ファイル名を取得
        basename = os.path.basename(text_file_path)
        
        # Geminiモデルの初期化（構造化出力対応）
        model = genai.GenerativeModel(
            'gemini-2.5-pro',
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": contract_schema
            }
        )
        
        # プロンプトの作成
        prompt = f"""
以下のOCR処理済みテキストを解析し、契約書の構造化データとして抽出してください。

ファイル名: {basename}

テキスト内容:
{file_content}

抽出指示:
1. success: 常にtrue
2. info部分:
   - title: 契約書のタイトル（見つからない場合はファイル名を使用）
   - party: 契約当事者をカンマ区切りで記載（例: "株式会社A,株式会社B"）
   - start_date: 契約開始日（YYYY-MM-DD形式、見つからない場合は空文字列）
   - end_date: 契約終了日（YYYY-MM-DD形式、見つからない場合は空文字列）
   - conclusion_date: 契約締結日（YYYY-MM-DD形式、見つからない場合は空文字列）

3. result部分:
   - articles: 契約条項の配列（全ての条項を漏れなく抽出）
     - article_number: 条項番号（例: "第1条"、"第2条"、番号がない場合は"署名欄"等）
     - title: 条項のタイトル（見出しがない場合は内容から要約）
     - content: 条項の完全な内容（省略禁止）
     - table_number: 表がある場合のみ表番号

重要な注意事項:
- テキスト内の全ての条項を必ず抽出してください（第1条から最後まで）
- 各条項のcontentは完全にコピーし、省略や要約は行わないでください
- 条項番号が明記されていない部分（前文、署名欄、付記等）も独立した条項として扱ってください
- 日付は可能な限りYYYY-MM-DD形式に変換してください
- 表や図がある場合はHTML形式でcontentに含めてください
- 署名欄も必ず1つの条項として扱ってください
- 出力は必ず完全なJSON形式で、途中で切れることなく最後まで出力してください
"""
        
        # Geminiに送信して構造化出力を取得
        print(f"Geminiに送信中... (ファイル: {basename})")
        response = model.generate_content(prompt)
        
        # JSONとしてパース
        structured_data = json.loads(response.text)
        
        articles_count = len(structured_data.get('result', {}).get('articles', []))
        logger.info(f"構造化完了: {articles_count}個の条項を抽出しました")
        
        return structured_data
        
    except Exception as e:
        logger.error(f"Gemini構造化出力エラー: {str(e)}")
        return None

def save_result(data: Dict[str, Any], output_file: str):
    """
    結果をJSONファイルに保存
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"結果を保存しました: {output_file}")
    except Exception as e:
        print(f"保存エラー: {str(e)}")

def main():
    """
    メイン関数
    """
    if len(sys.argv) < 2:
        print("使用方法: python test_contract_schema.py <テキストファイルパス> [出力ファイルパス]")
        print("例: python test_contract_schema.py example.txt result.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "structured_contract.json"
    
    # ファイル存在チェック
    if not os.path.exists(input_file):
        print(f"エラー: ファイルが見つかりません: {input_file}")
        sys.exit(1)
    
    print(f"入力ファイル: {input_file}")
    print(f"出力ファイル: {output_file}")
    print("-" * 50)
    
    # 構造化実行
    result = convert_to_contract_schema_local(input_file)
    
    if result:
        # 結果の概要を表示
        info = result.get('info', {})
        articles = result.get('result', {}).get('articles', [])
        
        print("\n=== 抽出結果の概要 ===")
        print(f"タイトル: {info.get('title', 'N/A')}")
        print(f"当事者: {info.get('party', 'N/A')}")
        print(f"締結日: {info.get('conclusion_date', 'N/A')}")
        print(f"開始日: {info.get('start_date', 'N/A')}")
        print(f"終了日: {info.get('end_date', 'N/A')}")
        print(f"抽出条項数: {len(articles)}個")
        
        print("\n=== 条項一覧 ===")
        for i, article in enumerate(articles[:10]):  # 最初の10個のみ表示
            article_num = article.get('article_number', 'N/A')
            title = article.get('title', 'N/A')
            content_preview = article.get('content', '')[:100] + "..." if len(article.get('content', '')) > 100 else article.get('content', '')
            print(f"{i+1}. [{article_num}] {title}")
            print(f"    内容: {content_preview}")
        
        if len(articles) > 10:
            print(f"... 他{len(articles)-10}個の条項")
        
        # 結果を保存
        save_result(result, output_file)
        
        print("\n✅ テスト完了")
    else:
        print("❌ 構造化に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()