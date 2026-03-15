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
    # 背景を少しグレーがかった白にして高級感を出す
    img = Image.new('RGB', (width, height), color=(245, 247, 249))
    d = ImageDraw.Draw(img)
    
    # 角丸のボタン背景を描画する関数
    def draw_button(draw, x, y, w, h, radius, color):
        draw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=color)

    # ボタンの配置と色 (x, y, w, h, color, text, subtext, icon)
    buttons = [
        (40, 40, 540, 345, (230, 245, 230), "短文問題", "Part 5", "📄"),
        (620, 40, 540, 345, (230, 235, 250), "長文問題", "Part 7", "📚"),
        (40, 425, 540, 345, (250, 240, 230), "復習問題", "Review", "🔄"),
        (620, 425, 540, 345, (240, 240, 240), "成績確認", "Stats", "📊")
    ]
    
    try:
        # サーバー上のローカルフォントを最優先で使用
        font_path = "NotoSansJP-Regular.otf"
        # 10MB越えのフルセット絵文字フォントを使用
        emoji_font_path = "NotoColorEmoji.ttf"
        font_main = ImageFont.truetype(font_path, 65)
        font_sub = ImageFont.truetype(font_path, 35)
        
        try:
            # Color Emoji font (Note: PIL might not render color but it should have the glyphs)
            font_icon = ImageFont.truetype(emoji_font_path, 80)
        except:
            # Fallback to general font if emoji font fails
            font_icon = ImageFont.truetype(font_path, 80)
    except:
        try:
            # Windows 環境用フォールバック
            font_main = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 65)
            font_sub = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 35)
            font_icon = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 80)
        except:
            font_main = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_icon = ImageFont.load_default()

    for x, y, w, h, color, txt, sub, icon in buttons:
        # ボタン影
        d.rounded_rectangle([x+4, y+4, x+w+4, y+h+4], radius=20, fill=(210, 210, 210))
        # ボタン本体
        draw_button(d, x, y, w, h, 20, color)
        
        # テキスト描画 (中央揃え)
        # アイコン
        try:
            ibox = d.textbbox((0, 0), icon, font=font_icon)
            iw = ibox[2] - ibox[0]; ih = ibox[3] - ibox[1]
            d.text((x + w/2 - iw/2, y + h/2 - 80), icon, fill=(50, 50, 50), font=font_icon)
        except: pass

        # メインテキスト
        try:
            mbox = d.textbbox((0, 0), txt, font=font_main)
            mw = mbox[2] - mbox[0]; mh = mbox[3] - mbox[1]
            d.text((x + w/2 - mw/2, y + h/2 + 20), txt, fill=(30, 30, 30), font=font_main)
        except: pass

        # サブテキスト
        try:
            sbox = d.textbbox((0, 0), sub, font=font_sub)
            sw = sbox[2] - sbox[0]; sh = sbox[3] - sbox[1]
            d.text((x + w/2 - sw/2, y + h/2 + 100), sub, fill=(100, 100, 100), font=font_sub)
        except: pass
        
    img.save(filename)
    print(f"[{filename}] generated with premium design.")

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
