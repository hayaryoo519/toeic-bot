import os
import random
import traceback
from datetime import datetime, date, timedelta, timezone
from urllib.parse import parse_qsl
import threading

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, PushMessageRequest,
    FlexMessage, FlexContainer, FlexCarousel, FlexBubble,
    QuickReply, QuickReplyItem, MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, PostbackEvent, FollowEvent
)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import models, schemas, database, config
from database import engine
from sync_notion import sync_from_notion
from backup_db import backup_database
from ai_generator import run_generation_batch

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# LINE API 準備
configuration = Configuration(access_token=config.settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.settings.LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

scheduler = BackgroundScheduler()

JST = timezone(timedelta(hours=9), 'JST')



def now_jst():
    return datetime.now(JST)

def date_jst():
    return datetime.now(JST).date()

def create_explanation_flex(question, is_correct, user_choice, current_combo):
    title = "🟢 正解！" if is_correct else "🔴 不正解..."
    bg_color = "#1DB446" if is_correct else "#E63946"
    
    combo_text = ""
    if is_correct and current_combo >= 2:
        if current_combo >= 10:
            combo_text = f"🔥 {current_combo}連勝!! 神がかってます！"
        elif current_combo >= 5:
            combo_text = f"🔥 {current_combo}連勝! 素晴らしい勢い！"
        else:
            combo_text = f"✨ {current_combo}連続正解中！"

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "lg"
                }
            ],
            "backgroundColor": bg_color
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "正解", "size": "xs", "color": "#aaaaaa"},
                        {"type": "text", "text": f"{question.answer}", "size": "xl", "weight": "bold", "color": "#111111"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "あなたの回答", "size": "xs", "color": "#aaaaaa"},
                        {"type": "text", "text": f"{user_choice}", "size": "md", "color": "#555555"}
                    ]
                },
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "contents": [
                        {"type": "text", "text": "解説", "size": "xs", "color": "#aaaaaa"},
                        {"type": "text", "text": question.explanation, "wrap": True, "size": "sm", "color": "#333333", "margin": "sm"}
                    ]
                }
            ]
        }
    }
    
    if combo_text:
        bubble["body"]["contents"].insert(0, {
            "type": "text",
            "text": combo_text,
            "weight": "bold",
            "size": "md",
            "color": "#FF4500",
            "margin": "sm",
            "align": "center"
        })

    container = FlexBubble.from_dict(bubble)
    return FlexMessage(alt_text="回答解説", contents=container)

@app.on_event("startup")
def start_scheduler():
    scheduler.start()
    scheduler.add_job(
        send_daily_question,
        trigger=CronTrigger(hour=7, minute=0, timezone='Asia/Tokyo'),
        id="daily_push",
        replace_existing=True
    )
    # Notion同期ジョブ (毎日深夜3時)
    scheduler.add_job(
        sync_from_notion,
        trigger=CronTrigger(hour=3, minute=0, timezone='Asia/Tokyo'),
        id="notion_sync",
        replace_existing=True
    )
    # DBバックアップジョブ (毎週日曜 深夜2時)
    scheduler.add_job(
        backup_database,
        trigger=CronTrigger(day_of_week='sun', hour=2, minute=0, timezone='Asia/Tokyo'),
        id="db_backup",
        replace_existing=True
    )

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    if signature is None:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")

    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Please check your channel access token/channel secret.")

    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    db = database.SessionLocal()
    line_user_id = event.source.user_id
    user = db.query(models.User).filter(models.User.line_user_id == line_user_id).first()
    if not user:
        user = models.User(line_user_id=line_user_id, created_at=now_jst())
        db.add(user)
        db.commit()
    db.close()
    
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="友達追加ありがとうございます！\n1日1問TOEICの問題を配信します！")]
        )
    )

@handler.add(PostbackEvent)
def handle_postback(event):
    db = database.SessionLocal()
    line_user_id = event.source.user_id
    data = event.postback.data
    
    # data format: delivery_id=1&question_id=2&choice=A
    try:
        params = dict(parse_qsl(data))
        delivery_id = int(params.get("delivery_id"))
        question_id = int(params.get("question_id"))
        choice = params.get("choice")
    except Exception:
        db.close()
        return

    user = db.query(models.User).filter(models.User.line_user_id == line_user_id).first()
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    
    if not user or not question:
        db.close()
        return

    # Check if this question was already answered for this delivery
    existing_answer = db.query(models.Answer).filter(
        models.Answer.delivery_id == delivery_id,
        models.Answer.question_id == question_id
    ).first()
    
    if existing_answer:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="この問題は既に回答済みです！")]
            )
        )
        db.close()
        return

    is_correct = (choice == question.answer)
    
    # コンボ更新
    if is_correct:
        user.current_combo += 1
        if user.current_combo > user.max_combo:
            user.max_combo = user.current_combo
    else:
        user.current_combo = 0
    
    answer = models.Answer(
        delivery_id=delivery_id,
        user_id=user.id,
        question_id=question_id,
        is_correct=is_correct,
        answered_at=now_jst()
    )
    db.add(answer)
    db.commit()

    flex_msg = create_explanation_flex(question, is_correct, choice, user.current_combo)

    quick_reply = QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="短文問題 📄", text="短文")),
            QuickReplyItem(action=MessageAction(label="長文問題 📚", text="長文")),
            QuickReplyItem(action=MessageAction(label="復習 🔄", text="復習")),
        ]
    )
    
    # QuickReplyをFlexMessageに付与
    flex_msg.quick_reply = quick_reply

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[flex_msg]
        )
    )
    db.close()

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    db = database.SessionLocal()
    line_user_id = event.source.user_id
    
    user = db.query(models.User).filter(models.User.line_user_id == line_user_id).first()
    if not user:
        user = models.User(line_user_id=line_user_id, created_at=now_jst())
        db.add(user)
        db.commit()

    user_text = event.message.text
    if user_text == "短文":
        # レベル選択のクイックリプライを表示
        quick_reply = QuickReply(
            items=[
                QuickReplyItem(action=MessageAction(label="600点レベル", text="600点レベル")),
                QuickReplyItem(action=MessageAction(label="730点レベル", text="730点レベル")),
                QuickReplyItem(action=MessageAction(label="860点レベル", text="860点レベル")),
                QuickReplyItem(action=MessageAction(label="990点レベル", text="990点レベル")),
            ]
        )
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="目標スコアを選んでください 🎯", quick_reply=quick_reply)]
            )
        )
    elif user_text in ["長文", "復習"] or "点レベル" in user_text:
        try:
            req_type = None
            review_only = False
            target_level = None
            
            if "点レベル" in user_text:
                req_type = models.ContentType.question
                if "600" in user_text: target_level = 600
                elif "730" in user_text: target_level = 730
                elif "860" in user_text: target_level = 860
                elif "990" in user_text: target_level = 990
            elif user_text == "長文":
                req_type = models.ContentType.passage
            elif user_text == "復習":
                review_only = True
                
            send_question_to_user(user, db, requested_type=req_type, review_only=review_only, target_level=target_level, reply_token=event.reply_token)
        except Exception as e:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"エラーが発生しました: {str(e)}")]
                )
            )
            traceback.print_exc()
    elif user_text == "成績":
        reply_stats(user, event.reply_token, db)
    elif user_text == "/sync":
        if config.settings.ADMIN_USER_ID and line_user_id != config.settings.ADMIN_USER_ID:
            # 管理者以外には応答しない、または制限メッセージを出す（今回は何もしない）
            db.close()
            return
        
        try:
            count = sync_from_notion()
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"🔄 同期が完了しました！\n新たに {count} 件の問題を追加しました。")]
                )
            )
        except Exception as e:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"❌ 同期エラー: {str(e)}")]
                )
            )
    elif user_text.startswith("/generate"):
        if config.settings.ADMIN_USER_ID and line_user_id != config.settings.ADMIN_USER_ID:
            db.close()
            return
        
        # 引数の解析 (例: /generate 5 Part7)
        parts = user_text.split()
        count = 3
        part_type = "Random"
        
        if len(parts) > 1 and parts[1].isdigit():
            count = int(parts[1])
            if count > 10: count = 10 # 最大10件制限
        
        if len(parts) > 2:
            suggested_part = parts[2].capitalize()
            if suggested_part in ["Part5", "Part7"]:
                part_type = suggested_part
        
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"🤖 AI問題生成を開始します...\n・個数: {count}件\n・パート: {part_type}\n・テーマ: ランダム\n\n完了するとNotionにDraftとして保存されます。")]
            )
        )
        # バックグラウンドで実行
        thread = threading.Thread(target=run_generation_batch, kwargs={"count": count, "part": part_type, "theme": "Random"})
        thread.start()
    else:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"「問題」「短文」「長文」「成績」「復習」のいずれかを送信してください！")]
            )
        )
    db.close()

def reply_stats(user: models.User, reply_token: str, db):
    answers = db.query(models.Answer).filter(models.Answer.user_id == user.id).order_by(models.Answer.answered_at.desc()).all()
    
    total = len(answers)
    if total == 0:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="まだ回答データがありません。")]
            )
        )
        return

    corrects = sum(1 for a in answers if a.is_correct)
    rate = int((corrects / total) * 100)
    
    # Part 5 vs Part 7 separation
    part5_total = 0
    part5_correct = 0
    part7_total = 0
    part7_correct = 0

    ans_q = db.query(models.Answer, models.Question).join(
        models.Question, models.Answer.question_id == models.Question.id
    ).filter(models.Answer.user_id == user.id).all()

    for a, q in ans_q:
        if q.passage_id is None:
            part5_total += 1
            if a.is_correct:
                part5_correct += 1
        else:
            part7_total += 1
            if a.is_correct:
                part7_correct += 1
                
    part5_rate = int((part5_correct / part5_total) * 100) if part5_total > 0 else 0
    part7_rate = int((part7_correct / part7_total) * 100) if part7_total > 0 else 0
    
    recent_marks = ["🟢" if a.is_correct else "🔴" for a in answers[:5]]
    recent_str = " ".join(recent_marks)

    # Streak calculation
    unique_dates = sorted(list(set([a.answered_at.astimezone(JST).date() for a in answers])), reverse=True)
    streak = 0
    today = date_jst()
    yesterday = today - timedelta(days=1)
    
    if unique_dates:
        first_date = unique_dates[0]
        if first_date == today or first_date == yesterday:
            streak = 1
            curr_date = first_date
            for d in unique_dates[1:]:
                if d == curr_date - timedelta(days=1):
                    streak += 1
                    curr_date = d
                else:
                    break

    # Build Flex Message
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📊 学習スコア",
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "xl"
                }
            ],
            "backgroundColor": "#1DB446"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "全体正答率", "size": "sm", "color": "#555555", "flex": 1},
                        {"type": "text", "text": f"{rate}% ({corrects}/{total})", "size": "sm", "color": "#111111", "align": "end", "weight": "bold", "flex": 1}
                    ]
                },
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "単文(Part 5)", "size": "sm", "color": "#555555", "flex": 1},
                        {"type": "text", "text": f"{part5_rate}% ({part5_correct}/{part5_total})", "size": "sm", "color": "#111111", "align": "end", "weight": "bold", "flex": 1}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {"type": "text", "text": "長文(Part 7)", "size": "sm", "color": "#555555", "flex": 1},
                        {"type": "text", "text": f"{part7_rate}% ({part7_correct}/{part7_total})", "size": "sm", "color": "#111111", "align": "end", "weight": "bold", "flex": 1}
                    ]
                },
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "🔥連続学習", "size": "sm", "color": "#555555", "flex": 1},
                        {"type": "text", "text": f"{streak} 日", "size": "sm", "color": "#FF4500", "align": "end", "weight": "bold", "flex": 1}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "📝最近の5問", "size": "sm", "color": "#555555"},
                        {"type": "text", "text": recent_str, "size": "lg", "align": "center", "margin": "sm"}
                    ]
                },
                {"type": "separator", "margin": "md"},
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#FF4500",
                    "margin": "md",
                    "action": {
                        "type": "message",
                        "label": "✍️間違えた問題を復習",
                        "text": "復習"
                    }
                }
            ]
        }
    }

    container = FlexBubble.from_dict(bubble)
    flex_msg = FlexMessage(alt_text="成績確認", contents=container)

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[flex_msg]
        )
    )

def send_daily_question():
    db = database.SessionLocal()
    users = db.query(models.User).all()
    for user in users:
        try:
            send_question_to_user(user, db)
        except Exception as e:
            print(f"Failed to send to {user.line_user_id}: {e}")
            traceback.print_exc()
    db.close()

def send_question_to_user(user: models.User, db, requested_type: models.ContentType = None, review_only: bool = False, target_level: int = None, reply_token: str = None):
    content_type, content_id = select_question_content(user.id, db, requested_type, review_only, target_level)
    
    if not content_type:
        msg_text = "🎉 現在、復習可能な（今日まだ出題されていない）間違えた問題はありません！素晴らしいです！" if review_only else "追加の学習問題がありません。追加をお待ち下さい！"
        if reply_token:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=msg_text)]
                )
            )
        else:
            push_req = PushMessageRequest(
                to=user.line_user_id,
                messages=[TextMessage(text=msg_text)]
            )
            line_bot_api.push_message_with_http_info(push_req)
        return

    today = date_jst()
    existing_delivery = db.query(models.Delivery).filter(
        models.Delivery.user_id == user.id,
        models.Delivery.content_type == content_type,
        models.Delivery.content_id == content_id,
        models.Delivery.delivered_date == today
    ).first()
    
    if existing_delivery:
        if reply_token:
            msg_text = "本日の問題はすべて出題済みです！\n明日また挑戦するか、サーバーに問題を追加してください。"
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=msg_text)]
                )
            )
        return

    delivery = models.Delivery(
        user_id=user.id,
        content_type=content_type,
        content_id=content_id,
        delivered_at=now_jst(),
        delivered_date=today
    )
    db.add(delivery)
    db.commit()
    
    if content_type == models.ContentType.question:
        question = db.query(models.Question).get(content_id)
        flex_msg = build_question_flex_message_obj(question, delivery.id)
        messages_to_send = [flex_msg]
    else:
        passage = db.query(models.Passage).get(content_id)
        questions = db.query(models.Question).filter(models.Question.passage_id == content_id).all()
        messages_to_send = build_passage_messages(passage, questions, delivery.id)

    if reply_token:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages_to_send
            )
        )
    else:
        push_req = PushMessageRequest(
            to=user.line_user_id,
            messages=messages_to_send
        )
        line_bot_api.push_message_with_http_info(push_req)

def select_question_content(user_id: int, db, requested_type: models.ContentType = None, review_only: bool = False, target_level: int = None):
    candidates = []
    
    should_review = True if review_only else random.random() < 0.3
    if should_review:
        today = date_jst()
        three_days_ago = now_jst() - timedelta(days=3)
        recent_answers = db.query(models.Answer).filter(models.Answer.user_id == user_id).order_by(models.Answer.answered_at.desc()).limit(500).all()
        q_latest_correct = {}
        for a in recent_answers:
            if a.question_id not in q_latest_correct:
                q_latest_correct[a.question_id] = a.is_correct
        
        incorrect_q_ids = [qid for qid, is_corr in q_latest_correct.items() if not is_corr]
        
        if incorrect_q_ids:
            review_candidates = []
            for qid in incorrect_q_ids:
                q = db.query(models.Question).get(qid)
                c_type = models.ContentType.passage if q.passage_id else models.ContentType.question
                
                if requested_type and c_type != requested_type:
                    continue
                    
                c_id = q.passage_id if q.passage_id else q.id
                
                if review_only:
                    recent_delivery = db.query(models.Delivery).filter(
                        models.Delivery.user_id == user_id,
                        models.Delivery.content_type == c_type,
                        models.Delivery.content_id == c_id,
                        models.Delivery.delivered_date == today
                    ).first()
                else:
                    recent_delivery = db.query(models.Delivery).filter(
                        models.Delivery.user_id == user_id,
                        models.Delivery.content_type == c_type,
                        models.Delivery.content_id == c_id,
                        models.Delivery.delivered_at >= three_days_ago
                    ).first()

                if not recent_delivery:
                    review_candidates.append((c_type, c_id))
            
            if review_candidates:
                candidates = list(set(review_candidates))

    if review_only:
        if candidates:
            return random.choice(candidates)
        return None, None

    if not candidates:
        delivered = db.query(models.Delivery).filter(models.Delivery.user_id == user_id).all()
        delivered_set = set([(d.content_type, d.content_id) for d in delivered])
        
        all_q = db.query(models.Question).filter(models.Question.passage_id == None).all()
        all_p = db.query(models.Passage).all()
        
        all_content = []
        if requested_type is None or requested_type == models.ContentType.question:
            query = db.query(models.Question).filter(models.Question.passage_id == None)
            if target_level:
                query = query.filter(models.Question.level == target_level)
            all_content.extend([(models.ContentType.question, q.id) for q in query.all()])
        if requested_type is None or requested_type == models.ContentType.passage:
            all_content.extend([(models.ContentType.passage, p.id) for p in all_p])
        
        new_content = [c for c in all_content if c not in delivered_set]
        if new_content:
            candidates = new_content
        else:
            if all_content:
                candidates = all_content

    if candidates:
        return random.choice(candidates)
    return None, None

def build_question_bubble(question: models.Question, delivery_id: int, header_text="TOEIC問題"):
    level_badge = []
    if question.level:
        level_badge.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FF4500",
            "cornerRadius": "sm",
            "paddingStart": "8px",
            "paddingEnd": "8px",
            "paddingTop": "2px",
            "paddingBottom": "2px",
            "contents": [
                {
                    "type": "text",
                    "text": f"Score {question.level}",
                    "color": "#FFFFFF",
                    "size": "xxs",
                    "weight": "bold"
                }
            ]
        })

    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": header_text,
                            "weight": "bold",
                            "size": "sm",
                            "color": "#1DB446",
                            "flex": 1
                        }
                    ] + level_badge
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": question.question,
                    "wrap": True,
                    "margin": "md",
                    "size": "md"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                build_choice_button("A", question.choice_a, delivery_id, question.id),
                build_choice_button("B", question.choice_b, delivery_id, question.id),
                build_choice_button("C", question.choice_c, delivery_id, question.id),
                build_choice_button("D", question.choice_d, delivery_id, question.id)
            ]
        }
    }

def build_choice_button(label_char, text, delivery_id, question_id):
    full_text = f"({label_char}) {text}"
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#E8ECEF",
        "cornerRadius": "md",
        "paddingAll": "12px",
        "action": {
            "type": "postback",
            "label": full_text[:40],
            "data": f"delivery_id={delivery_id}&question_id={question_id}&choice={label_char}",
            "displayText": f"{label_char} を選択しました。"
        },
        "contents": [
            {
                "type": "text",
                "text": full_text,
                "wrap": True,
                "color": "#111111",
                "align": "center",
                "size": "sm"
            }
        ]
    }

def build_question_flex_message_obj(question: models.Question, delivery_id: int):
    bubble = build_question_bubble(question, delivery_id, "【単文問題】")
    container = FlexBubble.from_dict(bubble)
    return FlexMessage(alt_text="本日の問題が届きました", contents=container)

def build_passage_messages(passage: models.Passage, questions: list, delivery_id: int):
    messages = []
    
    passage_bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "【長文問題】" if not passage.title else f"【長文】{passage.title}",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446"
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": passage.content,
                    "wrap": True,
                    "margin": "md",
                    "size": "sm"
                }
            ]
        }
    }
    messages.append(FlexMessage(alt_text="長文問題が届きました", contents=FlexBubble.from_dict(passage_bubble)))
    
    for i, q in enumerate(questions):
        if i >= 4: # LINEの1回の送信メッセージ上限(5件)に合わせて、本文1+設問4までに制限
            break
        q_bubble = build_question_bubble(q, delivery_id, f"設問 {i+1}")
        messages.append(FlexMessage(alt_text=f"設問 {i+1}", contents=FlexBubble.from_dict(q_bubble)))
        
    return messages
