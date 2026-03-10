from database import SessionLocal, engine
import models

def seed_data():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 既存のデータがないか確認
    if db.query(models.Question).first() is None:
        q1 = models.Question(
            type="single",
            question="The meeting was postponed _____ the manager was absent.",
            choice_a="because",
            choice_b="although",
            choice_c="unless",
            choice_d="despite",
            answer="A",
            explanation="文脈的に理由を表す接続詞 because が適切です。（〜のために）"
        )
        
        q2 = models.Question(
            type="single",
            question="Please submit the final report _____ Friday at the latest.",
            choice_a="in",
            choice_b="on",
            choice_c="by",
            choice_d="until",
            answer="C",
            explanation="期限を表す「〜までに」は by を用います。「金曜日までに」。"
        )

        db.add_all([q1, q2])
        db.commit()
        print("シードデータを追加しました。")
    else:
        print("すでにデータが存在します。")

    db.close()

if __name__ == "__main__":
    seed_data()
