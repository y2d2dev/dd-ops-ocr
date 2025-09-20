import os
import json
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()


class OCRTextCleaner:
    def __init__(self, api_key=None):
        """
        OCRテキストクリーナーの初期化

        Args:
            api_key (str): Gemini API キー。Noneの場合は環境変数から取得
        """
        if api_key:
            genai.configure(api_key=api_key)
        else:
            # 環境変数からAPIキーを取得
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")
            genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel('gemini-2.5-flash')

    @staticmethod
    def find_common_filename_part(file1_path, file2_path):
        """
        2つのファイル名から共通部分を見つける（最後の数字列のみ）

        Args:
            file1_path (str): 1つ目のファイルパス
            file2_path (str): 2つ目のファイルパス

        Returns:
            str: 共通部分のID（最後の数字列）
        """
        import re

        # ファイル名のみ取得（拡張子なし）
        file1_name = os.path.splitext(os.path.basename(file1_path))[0]
        file2_name = os.path.splitext(os.path.basename(file2_path))[0]

        # アンダースコアで分割してセクションごとに比較
        file1_parts = file1_name.split('_')
        file2_parts = file2_name.split('_')

        # 各部分を比較して共通部分を抽出
        common_parts = []
        for part1 in file1_parts:
            for part2 in file2_parts:
                if part1 == part2 and len(part1) > 3:  # 3文字以上の共通部分のみ
                    if part1 not in common_parts:
                        common_parts.append(part1)

        if common_parts:
            # 数字のみで構成された部分を抽出
            numeric_parts = []
            for part in common_parts:
                if re.match(r'^\d+$', part):  # 数字のみの部分
                    numeric_parts.append(part)

            if numeric_parts:
                # 最後（最大）の数字列を使用
                # 最大2つの数字列
                return '_'.join(sorted(numeric_parts, key=len, reverse=True)[:2])
            else:
                # 数字部分がない場合は全ての共通部分から最後の2つを使用
                return '_'.join(common_parts[-2:]) if len(common_parts) >= 2 else '_'.join(common_parts)
        else:
            # 共通部分がない場合はタイムスタンプを使用
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return timestamp

    def read_txt_file(self, file_path):
        """
        テキストファイルを読み込む

        Args:
            file_path (str): ファイルパス

        Returns:
            str: ファイル内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # UTF-8で読めない場合は他のエンコーディングを試す
            encodings = ['shift_jis', 'cp932', 'euc-jp', 'iso-2022-jp']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise ValueError(
                f"Could not read file {file_path} with any encoding")

    def clean_and_merge_texts(self, text1, text2):
        """
        Gemini APIを使って2つのOCRテキストをクリーンアップし統合する

        Args:
            text1 (str): 1つ目のOCRテキスト
            text2 (str): 2つ目のOCRテキスト

        Returns:
            str: クリーンアップされた統合テキスト
        """

        prompt = f"""
以下は2つの異なるOCRシステムによって出力されたテキストです。これらのテキストを分析し、以下の要件に従って1つの読みやすいテキストに統合してください。出力は結果のみ含めてください。：

要件:
1. 文字情報は一切削除せず、すべて保持してください
2. 重複する内容や明らかな繰り返しは統合し、一度だけ記載してください
3. 補足情報などを入れないで、元のテキストに忠実に従ってください
4. 元のテキストの意味や内容を変更しないでください
5. 数字、日付、固有名詞は特に注意深く扱ってください

OCRテキスト1:
{text1}

OCRテキスト2:
{text2}

統合された読みやすいテキストを出力してください：
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini API呼び出しでエラーが発生しました: {e}")
            # フォールバック：単純な結合
            return f"{text1}\n\n--- テキスト2 ---\n\n{text2}"

    def validate_filename_patterns(self, file1_path, file2_path):
        """
        ファイル名の規則をチェックする
        
        Args:
            file1_path (str): 1つ目のファイルパス
            file2_path (str): 2つ目のファイルパス
            
        Returns:
            tuple: (is_valid, error_message, timestamp)
        """
        import re
        
        # ファイル名のみ取得
        file1_name = os.path.basename(file1_path)
        file2_name = os.path.basename(file2_path)
        
        # 期待されるファイル名パターン
        document_ai_pattern = r'^document_ai_integrated_(\d{8}_\d{6})\.txt$'
        gemini_pattern = r'^gemini_integrated_(\d{8}_\d{6})\.txt$'
        
        # パターンマッチング
        doc_ai_match = re.match(document_ai_pattern, file1_name)
        gemini_match = re.match(gemini_pattern, file2_name)
        
        # file1がdocument_ai、file2がgeminiの場合
        if doc_ai_match and gemini_match:
            timestamp1 = doc_ai_match.group(1)
            timestamp2 = gemini_match.group(1)
            if timestamp1 == timestamp2:
                return True, None, timestamp1
            else:
                return False, f"タイムスタンプが一致しません: {timestamp1} vs {timestamp2}", None
        
        # file1がgemini、file2がdocument_aiの場合（順序逆転）
        doc_ai_match = re.match(document_ai_pattern, file2_name)
        gemini_match = re.match(gemini_pattern, file1_name)
        
        if doc_ai_match and gemini_match:
            timestamp1 = gemini_match.group(1)
            timestamp2 = doc_ai_match.group(1)
            if timestamp1 == timestamp2:
                return True, None, timestamp1
            else:
                return False, f"タイムスタンプが一致しません: {timestamp1} vs {timestamp2}", None
        
        # 期待されるパターンと一致しない場合
        expected_formats = [
            "document_ai_integrated_YYYYMMDD_HHMMSS.txt",
            "gemini_integrated_YYYYMMDD_HHMMSS.txt"
        ]
        return False, f"ファイル名が期待される形式と一致しません。期待される形式: {expected_formats}", None

    def process_files(self, file1_path, file2_path, output_path=None):
        """
        2つのOCRファイルを処理して統合する

        Args:
            file1_path (str): 1つ目のファイルパス
            file2_path (str): 2つ目のファイルパス
            output_path (str): 出力ファイルパス（Noneの場合は自動生成）

        Returns:
            str: 出力ファイルパス
        """
        
        # ファイル名規則のバリデーション
        print("ファイル名規則をチェック中...")
        is_valid, error_message, timestamp = self.validate_filename_patterns(file1_path, file2_path)
        
        if not is_valid:
            raise ValueError(f"ファイル名規則エラー: {error_message}")
        
        print(f"✓ ファイル名規則チェック完了。タイムスタンプ: {timestamp}")

        print(f"ファイル1を読み込み中: {file1_path}")
        text1 = self.read_txt_file(file1_path)

        print(f"ファイル2を読み込み中: {file2_path}")
        text2 = self.read_txt_file(file2_path)

        print("Gemini APIでテキストをクリーンアップ中...")
        cleaned_text = self.clean_and_merge_texts(text1, text2)

        # 出力ファイル名を生成
        if output_path is None:
            # バリデーションで取得したタイムスタンプを使用
            common_part = timestamp

            # 入力ファイルがある最初のディレクトリを取得
            input_dir = os.path.dirname(file1_path)

            # outputディレクトリを作成
            output_dir = os.path.join(input_dir, 'output')
            os.makedirs(output_dir, exist_ok=True)

            # 新しいファイル名形式
            output_filename = f"merged_ocr_{common_part}.txt"
            output_path = os.path.join(output_dir, output_filename)

            # メタデータファイル名
            meta_filename = f"merged_ocr_meta_{common_part}.json"
            meta_path = os.path.join(output_dir, meta_filename)
        else:
            meta_path = output_path.replace('.txt', '_meta.json')

        # 結果を保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)

        print(f"クリーンアップされたテキストを保存しました: {output_path}")

        # メタデータも保存
        metadata = {
            'input_files': [file1_path, file2_path],
            'output_file': output_path,
            'processed_at': datetime.now().isoformat(),
            'text1_length': len(text1),
            'text2_length': len(text2),
            'output_length': len(cleaned_text),
            'common_filename_part': timestamp,
            'validation_passed': True,
            'file_pattern': 'document_ai_integrated & gemini_integrated'
        }

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return output_path


def main():
    """
    メイン実行関数
    """
    import argparse

    parser = argparse.ArgumentParser(description='OCRテキストクリーナー')
    parser.add_argument('file1', help='1つ目のOCRテキストファイル')
    parser.add_argument('file2', help='2つ目のOCRテキストファイル')
    parser.add_argument('-o', '--output', help='出力ファイルパス')
    parser.add_argument('--api-key', help='Gemini API キー')

    args = parser.parse_args()

    try:
        cleaner = OCRTextCleaner(api_key=args.api_key)
        output_path = cleaner.process_files(
            args.file1, args.file2, args.output)
        print(f"処理完了: {output_path}")
    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()
