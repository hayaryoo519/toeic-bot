---
description: TOEIC Bot に新しい問題（クイズ）を追加する手順
---
以下の手順に従って、新しい問題を追加してください。

### 1. JSON ファイルの作成
ローカルのプロジェクトルートにある `sample_questions.json` を参考に、新しい問題データを含んだ JSON ファイル（例：`new_questions.json`）を作成してください。

### 2. サーバーへファイルを送信
// turbo
1. 下記コマンドをローカルのパワーシェルで実行して、ファイルをサーバーに送信します。
```powershell
scp new_questions.json haya-ryoo@192.168.0.13:~/apps/toeic-bot/
```

### 3. サーバーでインポートを実行
// turbo
1. SSH ターミナルで以下のコマンドを実行して、データベースに登録します。
```bash
cd ~/apps/toeic-bot
venv/bin/python3 import_questions.py new_questions.json
```

### 4. 完了確認
LINE で「問題」と送信し、新しい問題が出題されるか確認してください。
