import os
import json
import argparse
import time
from datetime import datetime, timezone, timedelta
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from dotenv import load_dotenv
from notion_provider import NotionProvider
import database, models

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
notion_provider = NotionProvider()
JST = timezone(timedelta(hours=9), 'JST')

SYSTEM_PROMPT = """あなたはプロのTOEIC問題作成者です。
指示された条件に従って、TOEIC形式の英語問題を作成し、必ず以下の純粋なJSONオブジェクト形式で出力してください。
余計な解説文やmarkdownのコードブロック記法(```json)は含めないでください。

{
  "question": "問題文 (空所に必ず 1 つの '______' (アンダーバー 6 つ) を含めること)",
  "choice_a": "選択肢 A",
  "choice_b": "選択肢 B",
  "choice_c": "選択肢 C",
  "choice_d": "選択肢 D",
  "answer": "A, B, C, D のいずれか1文字",
  "explanation": "日本語による文法事項や語彙の解説。なぜ正解がそれなのか、および他の選択肢がなぜ間違いなのかも含めて詳しく記述してください。",
  "passage": "長文テキスト (Part 7 の場合のみ。120〜200語程度に制限すること。Part 5 の場合はnullまたは空文字)",
  "part": "Part5 または Part7"
}
"""

REVIEW_PROMPT = """あなたは英語教育の専門家です。
提供されたTOEIC形式の問題が以下の基準を満たしているか厳格にチェックしてください。

1. 正解が客観的に1つだけに定まるか
2. 文法的に誤りがないか
3. 選択肢(Distractors)がTOEICとして自然か
4. 解説において「他の選択肢がなぜ間違いか」まで丁寧に記述されているか
5. Part 7の場合、長文が120〜200語の範囲内に収まっているか

問題に不備がある場合は 'NG: [理由]'、問題なければ 'OK' とだけ返答してください。
"""

def call_openai_with_retry(messages, response_format=None, model="gpt-4o-mini", max_retries=3):
    for i in range(max_retries):
        try:
            params = {
                "model": model,
                "messages": messages
            }
            if response_format:
                params["response_format"] = response_format
            
            response = client.chat.completions.create(**params)
            return response
        except (APIError, RateLimitError, APITimeoutError) as e:
            if i == max_retries - 1:
                raise e
            print(f"OpenAI API error (attempt {i+1}/{max_retries}): {e}. Retrying in 2 seconds...")
            time.sleep(2)
    return None

def log_generation(prompt, generated_question, review_result):
    db = database.SessionLocal()
    try:
        log_entry = models.AIGenerationLog(
            prompt=prompt,
            generated_question=json.dumps(generated_question, ensure_ascii=False) if isinstance(generated_question, dict) else generated_question,
            review_result=review_result,
            created_at=datetime.now(JST)
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Failed to log generation: {e}")
    finally:
        db.close()

def generate_single_question(part="Part5", theme="Business"):
    prompt = f"TOEIC {part} 形式の問題を1問作成してください。テーマは「{theme}」です。"
    if part == "Part7":
        prompt += " 長文の長さは120語から200語の間にしてください。"
    
    # 1. 生成
    response = call_openai_with_retry(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    question_data = json.loads(response.choices[0].message.content)
    
    # 2. セルフレビュー
    review_response = call_openai_with_retry(
        messages=[
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": json.dumps(question_data, ensure_ascii=False)}
        ]
    )
    review_result = review_response.choices[0].message.content.strip()
    
    # ログ保存
    log_generation(prompt, question_data, review_result)
    
    if "OK" in review_result:
        return question_data
    else:
        print(f"Review failed, regenerating... Reason: {review_result}")
        return generate_single_question(part, theme) # 再試行

THEMES = [
    "Office and Business", "Meetings and Appointments", "Travel and Transportation",
    "Dining and Restaurants", "Financial and Accounting", "Marketing and Sales",
    "Technical and IT", "Human Resources and Hiring", "Purchasing and Shopping",
    "Real Estate", "Healthcare", "Conferences and Events"
]

def run_generation_batch(count=1, part="Part5", theme="Random"):
    import random
    print(f"Starting generation batch: count={count}, part={part}, theme={theme}")
    
    for i in range(count):
        current_theme = theme
        if theme == "Random":
            current_theme = random.choice(THEMES)
            
        current_part = part
        if part == "Random":
            current_part = random.choice(["Part5", "Part7"])
            
        print(f"Generating question {i+1}/{count} (Part: {current_part}, Theme: {current_theme})...")
        try:
            q_data = generate_single_question(current_part, current_theme)
            notion_provider.create_question(q_data, status="Draft")
            print(f"Successfully saved to Notion as Draft.")
        except Exception as e:
            print(f"Error generating question: {e}")

def main():
    parser = argparse.ArgumentParser(description='TOEIC AI Question Generator')
    parser.add_argument('--count', type=int, default=1, help='Number of questions to generate')
    parser.add_argument('--part', type=str, default='Part5', choices=['Part5', 'Part7'], help='TOEIC Part')
    parser.add_argument('--theme', type=str, default='Random', help='Theme of the question or "Random"')
    args = parser.parse_args()

    run_generation_batch(args.count, args.part, args.theme)

if __name__ == "__main__":
    main()
