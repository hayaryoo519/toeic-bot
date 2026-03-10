import os
import random
import traceback
from datetime import datetime, date, timedelta, timezone
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, PushMessageRequest,
    FlexMessage, FlexContainer, FlexCarousel, FlexBubble
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, PostbackEvent, FollowEvent
)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import models, schemas, database, config
from database import engine

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

@app.on_event("startup")
def start_scheduler():
    scheduler.start()
    scheduler.add_job(
        send_daily_question,
        trigger=CronTrigger(hour=7, minute=0, timezone='Asia/Tokyo'),
        id="daily_push",
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
    
    answer = models.Answer(
        delivery_id=delivery_id,
        user_id=user.id,
        question_id=question_id,
        is_correct=is_correct,
        answered_at=now_jst()
    )
    db.add(answer)
    db.commit()

    if is_correct:
         result_text = "🟢 正解です！\n\n"
    else:
         result_text = f"🔴 不正解です...\n正解は {question.answer} です。\n\n"
    
    explanation_text = result_text + "【解説】\n" + question.explanation

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=explanation_text)]
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
    if user_text in ["問題", "短文", "長文"]:
        try:
            req_type = None
            if user_text == "短文":
                req_type = models.ContentType.question
            elif user_text == "長文":
                req_type = models.ContentType.passage
                
            send_question_to_user(user, db, requested_type=req_type)
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
    else:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"「問題」「短文」「長文」「成績」のいずれかを送信してください！")]
            )
        )
    db.close()

def reply_stats(user: models.User, reply_token: str, db):
    answers = db.query(models.Answer).filter(models.Answer.user_id == user.id).order_by(models.Answer.answered_at.desc()).all()
    
    total = len(answers)
    if total == 0:
        msg = "まだ回答データがありません。"
    else:
        corrects = sum(1 for a in answers if a.is_correct)
        rate = int((corrects / total) * 100)
        
        recent_marks = ["○" if a.is_correct else "×" for a in answers[:5]]
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

        msg = f"回答数: {total}\n正答率: {rate}%\n\n連続学習: {streak}日🔥\n\n最近の結果\n{recent_str}"

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=msg)]
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

def send_question_to_user(user: models.User, db, requested_type: models.ContentType = None):
    content_type, content_id = select_question_content(user.id, db, requested_type)
    
    if not content_type:
        push_req = PushMessageRequest(
            to=user.line_user_id,
            messages=[TextMessage(text="追加の学習問題がありません。追加をお待ち下さい！")]
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
    else:
        passage = db.query(models.Passage).get(content_id)
        questions = db.query(models.Question).filter(models.Question.passage_id == content_id).all()
        flex_msg = build_passage_carousel_obj(passage, questions, delivery.id)

    push_req = PushMessageRequest(
        to=user.line_user_id,
        messages=[flex_msg]
    )
    line_bot_api.push_message_with_http_info(push_req)

def select_question_content(user_id: int, db, requested_type: models.ContentType = None):
    candidates = []
    
    should_review = random.random() < 0.3
    if should_review:
        three_days_ago = now_jst() - timedelta(days=3)
        recent_answers = db.query(models.Answer).filter(models.Answer.user_id == user_id).order_by(models.Answer.answered_at.desc()).limit(200).all()
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

    if not candidates:
        delivered = db.query(models.Delivery).filter(models.Delivery.user_id == user_id).all()
        delivered_set = set([(d.content_type, d.content_id) for d in delivered])
        
        all_q = db.query(models.Question).filter(models.Question.passage_id == None).all()
        all_p = db.query(models.Passage).all()
        
        all_content = []
        if requested_type is None or requested_type == models.ContentType.question:
            all_content.extend([(models.ContentType.question, q.id) for q in all_q])
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
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": header_text,
                    "weight": "bold",
                    "size": "md",
                    "color": "#1DB446"
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
    return {
        "type": "button",
        "style": "secondary",
        "action": {
            "type": "postback",
            "label": f"{label_char}. {text}"[:20],
            "data": f"delivery_id={delivery_id}&question_id={question_id}&choice={label_char}",
            "displayText": f"{label_char} を選択しました。"
        }
    }

def build_question_flex_message_obj(question: models.Question, delivery_id: int):
    bubble = build_question_bubble(question, delivery_id, "【単文問題】")
    container = FlexBubble.from_dict(bubble)
    return FlexMessage(alt_text="本日の問題が届きました", contents=container)

def build_passage_carousel_obj(passage: models.Passage, questions: list, delivery_id: int):
    bubbles = []
    
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
    bubbles.append(passage_bubble)
    
    for i, q in enumerate(questions):
        if i >= 11:
            break
        q_bubble = build_question_bubble(q, delivery_id, f"設問 {i+1}")
        bubbles.append(q_bubble)
        
    container = FlexCarousel.from_dict({"type": "carousel", "contents": bubbles})
    return FlexMessage(alt_text="長文問題が届きました", contents=container)
