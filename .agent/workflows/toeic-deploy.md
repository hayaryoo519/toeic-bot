---
description: TOEIC Bot のデプロイ・再起動・状態確認の手順
---
サーバー上での管理作業を行うための手順です。

### 1. サービスの再起動
コードを更新したり、設定を変更した場合は再起動が必要です。
// turbo
1. SSH ターミナルで実行：
```bash
sudo systemctl restart toeic-bot.service
```

### 2. 状態確認
// turbo
1. 下記コマンドで各サービスが正常に動いているか確認します。
```bash
# Bot 本体
sudo systemctl status toeic-bot.service
# トンネル (Cloudflare)
sudo systemctl status cloudflared.service
```

### 3. ログのリアルタイム確認
// turbo
1. 動作ログを確認する場合はこちら。
```bash
# Bot のログ
sudo journalctl -u toeic-bot.service -f
# トンネルのログ
sudo journalctl -u cloudflared.service -f
```
