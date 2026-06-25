import streamlit as st
import csv
import io
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import re
from PIL import Image
import google.generativeai as genai

# 🌟 1. 初始化 Google Sheet 連線
@st.cache_resource
def init_gspread_client():
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google 認證失敗: {e}")
        return None

# 🌟 2. 載入 CSV 資料 (價格、卡圖、卡名、同名映射)
@st.cache_data
def load_card_data():
    prices = {}
    card_images = {}
    card_names = {}
    name_to_ids = {}

    try:
        with open("cards_price.csv", "r", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            next(reader) 
            for row in reader: 
                if len(row) >= 2:
                    prices[row[0]] = int(row[1])
                if len(row) >= 3 and row[2].startswith("http"):
                    card_images[row[0]] = row[2]
                if len(row) >= 4:
                    card_names[row[0]] = row[3]
                    if row[3] not in name_to_ids:
                        name_to_ids[row[3]] = []
                    name_to_ids[row[3]].append(row[0])
    except Exception as e:
        print(f"Error loading CSV: {e}")
        pass
        
    all_cards = list(prices.keys())
    packs = sorted(list(set([card.split('-')[0] for card in all_cards if '-' in card])))
    
    return prices, card_images, card_names, name_to_ids, all_cards, packs

# 🌟 3. 取得卡片圖片網址
def get_card_image_url(card_id, card_images):
    return card_images.get(card_id) if card_images.get(card_id) else f"https://placehold.co/150x210/1E1E1E/FFD700.png?text={card_id}"

# 🌟 4. 判斷卡片進化類型
def get_card_version_type(c_id, name, name_to_ids):
    match = re.match(r"^(.*?)(\d+)$", c_id)
    if not match: return "unknown"
    
    prefix = match.group(1)
    num_str = match.group(2)
    num = int(num_str)
    num_len = len(num_str)
    
    prev_id = f"{prefix}{(num-1):0{num_len}d}"
    next_id = f"{prefix}{(num+1):0{num_len}d}"
    
    same_name_ids = name_to_ids.get(name, [])
    
    if prev_id in same_name_ids: return "evolved"
    elif next_id in same_name_ids: return "unevolved"
    else: return "unknown"

# 🌟 5. 取得同名最低價版本
def get_cheapest_version(c_id, card_names, name_to_ids, prices):
    name = card_names.get(c_id)
    if not name or name not in name_to_ids: return c_id
    
    target_version = get_card_version_type(c_id, name, name_to_ids)
    valid_candidates = [cid for cid in name_to_ids[name] if cid in prices and get_card_version_type(cid, name, name_to_ids) == target_version]
                
    if not valid_candidates: return c_id
    cheapest_id = min(valid_candidates, key=lambda x: prices.get(x, float('inf')))
    return cheapest_id

# 🌟 6. 取得卡號前綴
def get_prefix(card_id):
    if "-" not in card_id: return "其他"
    suffix = card_id.split("-")[1]
    prefix = ""
    for char in suffix:
        if char.isalpha(): prefix += char
        else: break
    return prefix if prefix else "一般編號"

# 🌟 7. 儲存庫存至 Google Sheets
def save_inventory_to_sheets(current_sheet):
    try:
        records = current_sheet.get_all_records()
        cloud_inv = {str(row['卡號']): int(row['擁有數量']) for row in records if '卡號' in row}
        
        final_inv = {}
        for c_id, q in cloud_inv.items():
            if c_id not in st.session_state.my_inventory:
                final_inv[c_id] = q
        for c_id, q in st.session_state.my_inventory.items():
            if q > 0:
                final_inv[c_id] = q
        
        data = [["卡號", "擁有數量"]] + [[c_id, q] for c_id, q in sorted(final_inv.items())]
        current_sheet.clear()
        try: current_sheet.update(values=data, range_name='A1')
        except: current_sheet.update('A1', data)
            
        st.session_state.my_inventory = final_inv
        st.session_state.unsaved_changes = False
        return True
    except Exception as e:
        st.error(f"❌ 同步失敗: {e}")
        return False

# 🌟 8. 核心引擎：Deck Log API 直連版
def fetch_decklog(deck_code, auto_cheapest, card_names, name_to_ids, prices):
    api_url = f"https://decklog.bushiroad.com/system/app/api/view/{deck_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://decklog.bushiroad.com/view/{deck_code}" 
    }
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            cards_found = 0
            for list_name in ["list", "sub_list", "p_list"]:
                if list_name in data and isinstance(data[list_name], list):
                    for card in data[list_name]:
                        c_id = card.get("card_number")
                        qty = card.get("num", 1) 
                        if c_id:
                            if auto_cheapest:
                                c_id = get_cheapest_version(c_id, card_names, name_to_ids, prices)
                                
                            st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + qty
                            cards_found += 1
            if cards_found > 0:
                return True, f"🎉 API 破解成功！瞬間精準匯入了 {cards_found} 種卡片！"
            else:
                debug_info = str(data)[:300]
                return False, f"連線成功但抓不到卡片！官方實際內容：\n{debug_info}"
        return False, f"連線 API 失敗 (狀態碼: {res.status_code})"
    except Exception as e:
        return False, f"API 解析發生錯誤: {e}"

# 🌟 9. 核心引擎：Gemini AI 圖片多卡辨識
def scan_card_image(img_file, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        img = Image.open(img_file)
        
        prompt = (
            "這是一張包含多張 Shadowverse Evolve (SVE) 實體卡片的照片。"
            "請運用你的視覺找出照片中「所有」卡片的「卡號」。"
            "卡號格式通常為英文字母加數字，中間有連字號（例如 BP01-001, SD01-005, PR-001, BP15-054）。"
            "請盡可能精準，將你找到的所有卡號全部列出來，用逗號或換行隔開即可，不要回傳任何其他多餘的字或解釋。"
        )
        
        response = model.generate_content([prompt, img])
        scanned_text = response.text.strip().upper()
        
        card_ids = re.findall(r'([A-Z]+[0-9]*-[0-9A-Z]+)', scanned_text)
        
        if card_ids:
            return True, card_ids, scanned_text
        else:
            return False, [], scanned_text
    except Exception as e:
        return False, [], str(e)
