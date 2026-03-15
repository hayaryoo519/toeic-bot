---
description: TOEIC Bot に新しい問題（クイズ）を追加する手順
---
以下の手順に従って、新しい問題を追加してください。

### 1. JSON ファイルの作成
ローカルのプロジェクトルートにある `sample_questions.json` を参考に、新しい問題データを含んだ JSON ファイル（例：`new_questions.json`）を作成してください。

### 2. インポートの実行
// turbo
1. PowerShellで以下のコマンドを実行して、データベースに登録します。
```powershell
.\venv\Scripts\python import_questions.py new_questions.json
```

### 3. 完了確認
LINE で「問題」と送信し、新しい問題が出題されるか確認してください。
