---
description: NotionにあるDraft問題をエージェント（私）がチェック・承認する
---
Notionに保存されている `Draft` 状態の問題を、Antigravity（私）が読み取って内容をレビューし、承認プロセスを進めます。

### 1. Draft問題の読み込み
// turbo
1. PowerShellで以下のコマンドを実行して、チェック待ちの問題リストを取得します。
```powershell
.\venv\Scripts\python agent_utils.py list-drafts
```
2. 出力されたJSONリストを私に提示して、「これらをチェックして」と依頼してください。

### 2. レビューと修正
1. 提示された問題に対して、私がTOEICの観点からレビューを行い、必要があれば修正案を提示します。
2. あなたが内容に納得したら、「これで承認して」と指示してください。

### 3. 承認の実行
// turbo
1. 承認する問題の `page_id`（list-draftsで確認したもの）を使って、以下のコマンドを実行します。
```powershell
.\venv\Scripts\python agent_utils.py approve "[page_id]"
```

### 4. 反映
1. 承認（Approved）になった問題は、次回の `/sync` （LINEボット側）で出題プールに追加されます。
