# OCRテキストクリーナー - ファイル名規則ガードレール

## 概要

`clean_ocr_result.py`にファイル名規則のバリデーション機能（ガードレール）を追加しました。
この機能により、以下の2種類のファイルの統合処理が安全に実行できます：

1. `document_ai_integrated_{YYYYMMDD_HHMMSS}.txt`
2. `gemini_integrated_{YYYYMMDD_HHMMSS}.txt`

## 追加された機能

### `validate_filename_patterns(file1_path, file2_path)`

2つのファイルパスを受け取り、以下をチェックします：

- ファイル名が正しい命名規則に従っているか
- 一方が `document_ai_integrated_` で始まり、もう一方が `gemini_integrated_` で始まるか
- 両ファイルのタイムスタンプが一致するか

### 戻り値

```python
(is_valid, error_message, timestamp)
```

- `is_valid`: ブール値（True: 有効, False: 無効）
- `error_message`: エラーの場合の詳細メッセージ
- `timestamp`: 抽出されたタイムスタンプ（YYYYMMDD_HHMMSS形式）

## 使用例

### 正常なケース

```python
cleaner = OCRTextCleaner()

# 正しい形式のファイルペア
file1 = "document_ai_integrated_20250910_083042.txt"
file2 = "gemini_integrated_20250910_083042.txt"

# 順序は問いません
file1 = "gemini_integrated_20250910_083042.txt"
file2 = "document_ai_integrated_20250910_083042.txt"

# 処理実行
output_path = cleaner.process_files(file1, file2)
```

### エラーケース

以下の場合はエラーが発生します：

1. **タイムスタンプが一致しない**
   ```
   document_ai_integrated_20250910_083042.txt
   gemini_integrated_20250910_084500.txt
   ```

2. **ファイル名形式が正しくない**
   ```
   wrong_format_file.txt
   gemini_integrated_20250910_083042.txt
   ```

3. **同じプレフィックスのファイル**
   ```
   document_ai_integrated_20250910_083042.txt
   document_ai_integrated_20250910_083042.txt
   ```

## 出力ファイル名

バリデーションに成功した場合、出力ファイル名は以下の形式になります：

```
merged_ocr_{YYYYMMDD_HHMMSS}.txt
merged_ocr_meta_{YYYYMMDD_HHMMSS}.json
```

例：
```
merged_ocr_20250910_083042.txt
merged_ocr_meta_20250910_083042.json
```

## エラーハンドリング

バリデーションに失敗した場合、`ValueError` が発生し、処理が中止されます：

```python
try:
    output_path = cleaner.process_files(file1, file2)
except ValueError as e:
    print(f"ファイル名規則エラー: {e}")
```

## コマンドライン使用

```bash
python utils/clean_ocr_result.py \
    result/document_ai_integrated_20250910_083042.txt \
    result/gemini_integrated_20250910_083042.txt
```

## テスト

バリデーション機能のテストは `test_validation_simple.py` で実行できます：

```bash
python3 test_validation_simple.py
```

このテストでは、さまざまなファイル名パターンでのバリデーション結果を確認できます。
