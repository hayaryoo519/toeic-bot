---
description: AIを使用して新しいTOEIC問題を自動生成する（かんたんモード）
---
AI（ChatGPT）を使用して、新しいTOEIC問題を生成し、NotionデータベースにDraftとして保存します。

### 1. 生成コマンドの実行
// turbo
1. 下記コマンドをPowerShellで実行します（標準的な設定で1問生成します）。
```powershell
.\venv\Scripts\python ai_generator.py --count 1 --part Part5 --theme "Random"
```

### 2. オプションでのカスタマイズ
さらに細かく指定したい場合は、以下のオプションを変更して実行してください。
- `--count [数値]`: 生成する問題数
- `--part [Part5|Part7]`: 問題形式（Part5: 短文穴埋め, Part7: 長文読解）
- `--theme [テーマ]`: "Business", "Travel", "Daily Life" など

### 3. 次のステップ
1. 生成完了後、Notionを開いて内容を確認します。
2. 問題なければNotion上のステータスを `Approved` に変更します。
3. LINEボットで `/sync` と送信すると、ボットに反映されます。
