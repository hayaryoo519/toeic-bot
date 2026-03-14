import os
import shutil
from datetime import datetime
import config

def backup_database():
    """
    SQLiteデータベースファイルをバックアップディレクトリにコピーします。
    """
    db_path = config.settings.DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return

    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"toeic_bot_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        shutil.copy2(db_path, backup_path)
        print(f"Backup created successfully: {backup_path}")
        
        # 古いバックアップを削除（直近7件のみ保持）
        backups = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("toeic_bot_")],
            key=os.path.getmtime,
            reverse=True
        )
        if len(backups) > 7:
            for old_backup in backups[7:]:
                os.remove(old_backup)
                print(f"Removed old backup: {old_backup}")
                
    except Exception as e:
        print(f"Failed to create backup: {e}")

if __name__ == "__main__":
    backup_database()
