import sqlite3
import os

def backfill():
    db_path = 'toeic_bot.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check count
    c.execute("SELECT count(*) FROM questions WHERE level IS NULL OR level = ''")
    count = c.fetchone()[0]
    print(f"Questions without level: {count}")
    
    if count > 0:
        c.execute("UPDATE questions SET level = '730' WHERE level IS NULL OR level = ''")
        conn.commit()
        print(f"Successfully updated {count} questions to level 730.")
    else:
        print("No questions to update.")
        
    conn.close()

if __name__ == '__main__':
    backfill()
