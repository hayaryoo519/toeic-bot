---
description: エージェント（私）にTOEIC問題を作成させてNotionに保存する
---
ChatGPT APIを使わずに、Antigravity（私）が直接TOEIC問題を作成し、NotionデータベースにDraftとして保存します。

### 1. 問題作成の依頼
1. 私に対して「ビジネスをテーマにPart5の問題を1問作って」のように依頼してください。
2. 私が生成した問題案（JSON形式）を提示します。

### 2. 生成データの保存
// turbo
1. 下記コマンドの `[JSONデータ]` 部分に、私が提示したJSONを貼り付けてPowerShellで実行します。
```powershell
.\venv\Scripts\python agent_utils.py push '[JSONデータ]'
```
※WindowsのPowerShellで実行する場合、JSON内の引用符に注意が必要な場合があります。うまくいかない場合は、内容を `temp.json` に保存して `.\venv\Scripts\python agent_utils.py push (Get-Content temp.json -Raw)` とすると確実です。

### 3. 次のステップ
1. 保存後、Notionを開いて `Draft` 状態の問題を確認してください。
2. 必要に応じて `/toeic-agent-check` で私のレビューを受けることができます。
