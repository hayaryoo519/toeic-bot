import os
import json
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
if not ACCESS_TOKEN:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN not found in .env")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def create_rich_menu_image(filename="rich_menu.png"):
    width, height = 1200, 810
    img = Image.new('RGB', (width, height), color=(250, 250, 250))
    d = ImageDraw.Draw(img)
    
    # 枠線を引く
    d.line([(600, 0), (600, 810)], fill=(200, 200, 200), width=2)
    d.line([(0, 405), (1200, 405)], fill=(200, 200, 200), width=2)
    
    # テキストを描画
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 60)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", 60)
        except:
            font = ImageFont.load_default()

    # (x, y, text, color)
    labels = [
        (300, 202, "📄 短文問題\n(Part 5)", (0, 100, 0)),
        (900, 202, "📚 長文問題\n(Part 7)", (0, 50, 150)),
        (300, 607, "🔄 復習問題\n(Review)", (150, 50, 0)),
        (900, 607, "📊 成績確認\n(Stats)", (100, 100, 100))
    ]
    
    for x, y, text, color in labels:
        try:
            bbox = d.textbbox((0, 0), text, font=font, align="center")
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            # 古いPillow対応
            tw, th = d.textsize(text, font=font)
        
        d.text((x - tw/2, y - th/2), text, fill=color, font=font, align="center")
        
    img.save(filename)
    print(f"[{filename}] generated.")

def get_existing_menus():
    res = requests.get("https://api.line.me/v2/bot/richmenu/list", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    if res.status_code == 200:
        return res.json().get("richmenus", [])
    return []

def delete_old_menus():
    menus = get_existing_menus()
    for m in menus:
        print(f"Deleting existing menu: {m['richMenuId']}")
        requests.delete(f"https://api.line.me/v2/bot/richmenu/{m['richMenuId']}", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})

def setup_rich_menu():
    # 古いメニューを削除する
    delete_old_menus()

    print("Creating Rich Menu object...")
    payload = {
        "size": {
            "width": 1200,
            "height": 810
        },
        "selected": True,
        "name": "TOEIC Menu",
        "chatBarText": "メニュー",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 600, "height": 405},
                "action": {"type": "message", "text": "短文"}
            },
            {
                "bounds": {"x": 600, "y": 0, "width": 600, "height": 405},
                "action": {"type": "message", "text": "長文"}
            },
            {
                "bounds": {"x": 0, "y": 405, "width": 600, "height": 405},
                "action": {"type": "message", "text": "復習"}
            },
            {
                "bounds": {"x": 600, "y": 405, "width": 600, "height": 405},
                "action": {"type": "message", "text": "成績"}
            }
        ]
    }
    
    res = requests.post("https://api.line.me/v2/bot/richmenu", headers=HEADERS, json=payload)
    if res.status_code != 200:
        print("Failed to create rich menu:", res.text)
        return
        
    rich_menu_id = res.json()["richMenuId"]
    print(f"Rich Menu created: {rich_menu_id}")
    
    print("Uploading image...")
    img_path = "rich_menu.png"
    with open(img_path, 'rb') as f:
        img_headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "image/png"
        }
        res_img = requests.post(f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content", headers=img_headers, data=f)
        if res_img.status_code != 200:
            print("Failed to upload image:", res_img.text)
            return
            
    print("Setting as default menu...")
    res_def = requests.post(f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}", headers=HEADERS)
    if res_def.status_code != 200:
        print("Failed to set default:", res_def.text)
    else:
        print("Successfully set default rich menu!")

if __name__ == "__main__":
    create_rich_menu_image()
    setup_rich_menu()
