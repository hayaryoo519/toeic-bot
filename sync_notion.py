import os
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import database, models
from notion_provider import NotionProvider

notion_provider = NotionProvider()
JST = timezone(timedelta(hours=9), 'JST')

def log_sync(page_id, result, error_message=None):
    db = database.SessionLocal()
    try:
        log_entry = models.SyncLog(
            notion_page_id=page_id,
            result=result,
            error_message=error_message,
            synced_at=datetime.now(JST)
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Failed to log sync: {e}")
    finally:
        db.close()

def sync_from_notion():
    db = database.SessionLocal()
    pages = notion_provider.get_approved_questions()
    
    print(f"Found {len(pages)} approved questions in Notion.")
    
    success_count = 0
    for page in pages:
        page_id = page["id"]
        try:
            # レートリミット対策 (3 requests / sec 制限への配慮)
            time.sleep(0.4)

            # 重複チェック: すでに同じ notion_page_id があればスキップ
            existing_q = db.query(models.Question).filter(models.Question.notion_page_id == page_id).first()
            if existing_q:
                print(f"Question (Page ID: {page_id}) already exists. Updating status to Synced on Notion.")
                notion_provider.update_status(page_id, "Synced")
                log_sync(page_id, "Skip (Already Exists)")
                continue

            # データ抽出
            part = notion_provider.get_property_text(page, "Part")
            passage_text = notion_provider.get_property_text(page, "Passage")
            question_text = notion_provider.get_property_text(page, "Question")
            choice_a = notion_provider.get_property_text(page, "Choice A")
            choice_b = notion_provider.get_property_text(page, "Choice B")
            choice_c = notion_provider.get_property_text(page, "Choice C")
            choice_d = notion_provider.get_property_text(page, "Choice D")
            answer = notion_provider.get_property_text(page, "Answer")
            explanation = notion_provider.get_property_text(page, "Explanation")

            if not question_text or not answer:
                msg = f"Skipping page {page_id} due to missing required fields."
                print(msg)
                log_sync(page_id, "Skip (Incomplete Data)", error_message=msg)
                continue

            passage_id = None
            if part == "Part7" and passage_text:
                existing_p = db.query(models.Passage).filter(models.Passage.content == passage_text).first()
                if existing_p:
                    passage_id = existing_p.id
                else:
                    new_p = models.Passage(content=passage_text, title=None)
                    db.add(new_p)
                    db.flush() 
                    passage_id = new_p.id

            # Question 登録
            new_q = models.Question(
                passage_id=passage_id,
                question=question_text,
                choice_a=choice_a,
                choice_b=choice_b,
                choice_c=choice_c,
                choice_d=choice_d,
                answer=answer,
                explanation=explanation,
                notion_page_id=page_id
            )
            db.add(new_q)
            db.commit()
            
            # Notion 側のステータス更新
            time.sleep(0.4) # 更新時もスリープ
            notion_provider.update_status(page_id, "Synced")
            
            log_sync(page_id, "Success")
            success_count += 1
            print(f"Successfully synced question: {question_text[:30]}...")

        except Exception as e:
            db.rollback()
            error_msg = str(e)
            print(f"Error syncing page {page_id}: {error_msg}")
            log_sync(page_id, "Error", error_message=error_msg)

    db.close()
    return success_count

if __name__ == "__main__":
    count = sync_from_notion()
    print(f"Sync completed. {count} questions newly added.")
