import json
import argparse
import sys
from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine

# スキーマ初期化
models.Base.metadata.create_all(bind=engine)

def import_data(json_file_path: str):
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)
        
    db: Session = SessionLocal()
    
    psg_count = 0
    q_count = 0
    
    for item in data:
        title = item.get("title")
        content = item.get("content")
        questions_list = item.get("questions", [])
        
        if not questions_list:
            print("Warning: Skipping item with no questions.")
            continue
            
        passage_record = None
        # 長文の判定ルール: contentが存在すればPassageとして登録
        if content:
            passage_record = models.Passage(
                title=title,
                content=content
            )
            db.add(passage_record)
            db.commit()
            db.refresh(passage_record)
            psg_count += 1
            
        for q_data in questions_list:
            question = models.Question(
                passage_id=passage_record.id if passage_record else None,
                question=q_data["question"],
                choice_a=q_data["choice_a"],
                choice_b=q_data["choice_b"],
                choice_c=q_data["choice_c"],
                choice_d=q_data["choice_d"],
                answer=q_data["answer"],
                explanation=q_data["explanation"]
            )
            db.add(question)
            db.commit()
            q_count += 1
            
    db.close()
    print(f"Import completed successfully.")
    print(f"Passages inserted: {psg_count}")
    print(f"Questions inserted: {q_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import questions from JSON file into DB")
    parser.add_argument("json_file", type=str, help="Path to the JSON file")
    args = parser.parse_args()
    
    import_data(args.json_file)
