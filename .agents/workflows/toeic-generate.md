---
description: AIを使用して新しいTOEIC問題（Part5/Part7）を自動生成する
---
AI（ChatGPT）を使用して、新しいTOEIC問題を生成し、NotionデータベースにDraftとして保存します。

### 1. 生成コマンドの実行
// turbo
1. 下記コマンドをPowerShellで実行して生成を開始します。
```powershell
# 例: Part5の問題を3問生成する場合
.\venv\Scripts\python ai_generator.py --count 3 --part Part5 --theme "Business"
```

### 2. 生成オプションの解説
- `--count [数値]`: 生成する問題数（1〜10推奨）
- `--part [Part5|Part7]`: 問題形式の指定
- `--theme [文字列]`: 問題のテーマ（"Business", "Travel", "Daily Life" など）

### 3. 生成後の確認
1. 生成が完了すると "Successfully saved to Notion as Draft." と表示されます。
2. Notionデータベースを開き、新しく追加された問題をレビューしてください。
3. 内容に問題がなければ、ステータスを `Approved` に変更します。

### 4. 完了
LINEボットで `/sync` と送信すると、`Approved` になった問題が自動的に出題プールに追加されます。
