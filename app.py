import streamlit as st
import csv
import io
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
# 🌟 新增：用於影像處理與 Gemini AI 視覺辨識
from PIL import Image
import google.generativeai as genai

st.set_page_config(page_title="SVE 缺卡計算機", page_icon="🃏", layout="wide")

# ==========================================
# 🌟 初始化：網頁記憶體 (Session State)
if "deck_list" not in st.session_state: st.session_state.deck_list = {}
if "my_inventory" not in st.session_state: st.session_state.my_inventory = {}
if "current_bp_name" not in st.session_state: st.session_state.current_bp_name = ""
if "unsaved_changes" not in st.session_state: st.session_state.unsaved_changes = False

# ==========================================
# 🌟 0. 核心引擎：Deck Log API 直連版
def fetch_decklog(deck_code, auto_cheapest=False):
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
                            # 🌟 如果啟用自動找低價，就替換為最便宜的卡號
                            if auto_cheapest:
                                c_id = get_cheapest_version(c_id)
                                
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

# ==========================================
# ==========================================
# 🌟 0.5 核心引擎：Gemini AI 圖片掃描 (升級多卡辨識版)
def scan_card_image(img_file, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        img = Image.open(img_file)
        
        # 🌟 修正提示詞：明確要求 AI 找出「所有」看得到的卡號
        prompt = (
            "這是一張包含多張 Shadowverse Evolve (SVE) 實體卡片的照片。"
            "請運用你的視覺找出照片中「所有」卡片的「卡號」。"
            "卡號格式通常為英文字母加數字，中間有連字號（例如 BP01-001, SD01-005, PR-001, BP15-054）。"
            "請盡可能精準，將你找到的所有卡號全部列出來，用逗號或換行隔開即可，不要回傳任何其他多餘的字或解釋。"
        )
        
        response = model.generate_content([prompt, img])
        scanned_text = response.text.strip().upper()
        
        # 🌟 關鍵修正：改用 re.findall，這會把網頁文字裡「所有符合格式的卡號」通通抓出來變成一個 List
        card_ids = re.findall(r'([A-Z]+[0-9]*-[0-9A-Z]+)', scanned_text)
        
        if card_ids:
            return True, card_ids, scanned_text  # 回傳成功狀態與卡號清單
        else:
            return False, [], scanned_text
    except Exception as e:
        return False, [], str(e)

# ==========================================
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

client = init_gspread_client()
if not client: st.stop()

try:
    # ⚠️⚠️⚠️ 記得換成你的試算表 ID ⚠️⚠️⚠️
    sheet_id = "1Re2ZLcJKkFqyGe3sXaieAeB8E9U9k4PxghYbKAuXSZ4" 
    doc = client.open_by_key(sheet_id)
except Exception as e:
    st.error(f"無法開啟試算表：{e}")
    st.stop()

# ==========================================
# 🌟 2. 讀取與儲存邏輯 (多重背包與智能合併)
worksheets = [ws.title for ws in doc.worksheets()]
with st.sidebar:
    st.title("🎒 背包管理")
    selected_backpack = st.selectbox("切換背包：", worksheets)
    
    st.divider()
    with st.expander("➕ 建立全新背包"):
        new_bp_name = st.text_input("輸入新背包名稱：")
        if st.button("🚀 建立背包"):
            if new_bp_name and new_bp_name not in worksheets:
                new_sheet = doc.add_worksheet(title=new_bp_name, rows="1000", cols="2")
                try: new_sheet.update(values=[["卡號", "擁有數量"]], range_name='A1')
                except: new_sheet.update('A1', [["卡號", "擁有數量"]])
                st.success(f"✅ 建立成功！")
                st.rerun()
                
    with st.expander("🗑️ 刪除當前背包"):
        st.warning(f"確定要刪除【{selected_backpack}】？這將無法復原喔！")
        if st.button("🚨 確認刪除"):
            if len(worksheets) <= 1: 
                st.error("這是最後一個背包了，無法刪除！")
            else:
                doc.del_worksheet(doc.worksheet(selected_backpack))
                st.success("已成功刪除！")
                st.rerun()

current_sheet = doc.worksheet(selected_backpack)

if st.session_state.current_bp_name != selected_backpack:
    try:
        records = current_sheet.get_all_records()
        st.session_state.my_inventory = {str(row['卡號']): int(row['擁有數量']) for row in records if '卡號' in row}
        st.session_state.current_bp_name = selected_backpack
        st.session_state.unsaved_changes = False
    except Exception as e:
        st.error(f"讀取雲端資料失敗：{e}")

def save_inventory_to_sheets():
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

def get_prefix(card_id):
    if "-" not in card_id: return "其他"
    suffix = card_id.split("-")[1]
    prefix = ""
    for char in suffix:
        if char.isalpha(): prefix += char
        else: break
    return prefix if prefix else "一般編號"

# ==========================================
# 🌟 3. 載入 CSV 資料 (價格、卡圖、卡名)
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
except: pass

def get_card_image_url(card_id):
    return card_images.get(card_id) if card_images.get(card_id) else f"https://placehold.co/150x210/1E1E1E/FFD700.png?text={card_id}"

def get_card_version_type(c_id, name):
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

def get_cheapest_version(c_id):
    name = card_names.get(c_id)
    if not name or name not in name_to_ids: return c_id
    
    target_version = get_card_version_type(c_id, name)
    valid_candidates = [cid for cid in name_to_ids[name] if cid in prices and get_card_version_type(cid, name) == target_version]
                
    if not valid_candidates: return c_id
    cheapest_id = min(valid_candidates, key=lambda x: prices.get(x, float('inf')))
    return cheapest_id

all_cards = list(prices.keys())
packs = sorted(list(set([card.split('-')[0] for card in all_cards if '-' in card])))

# ==========================================
# 🌟 4. 網頁介面設計
tab1, tab2, tab3, tab4 = st.tabs(["🧾 牌組結帳 (計算缺卡)", "🎒 我的庫存與資產", "💰 單卡價格與卡圖查詢", "📊 所有背包總覽"])

# ----- 分頁 1：結帳區 -----
with tab1:
    st.subheader("🔍 選擇卡片加入結帳牌組")
    
    col_p1, col_r1, col_c1, col_q1 = st.columns(4)
    with col_p1: deck_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="deck_pack")
    cards_in_pack1 = all_cards if deck_pack == "全部" else [c for c in all_cards if c.startswith(deck_pack + "-")]
    prefixes1 = sorted(list(set([get_prefix(c) for c in cards_in_pack1])))
    
    with col_r1: deck_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes1, key="deck_prefix")
    cards_in_prefix1 = sorted(cards_in_pack1 if deck_prefix == "全部" else [c for c in cards_in_pack1 if get_prefix(c) == deck_prefix])
    
    card_options1 = [f"{c} - {card_names.get(c, '未知')}" for c in cards_in_prefix1]
    with col_c1: selected_option1 = st.selectbox("3. 選擇卡號/卡名：", ["請選擇..."] + card_options1, key="deck_select")
    with col_q1: deck_qty = st.number_input("4. 需要幾張？", min_value=1, max_value=50, value=1, key="deck_qty")
    
    col_btn1, col_img1 = st.columns([4, 1])
    with col_btn1:
        st.write("") 
        if st.button("➕ 加入結帳牌組", key="btn_add_deck"):
            if selected_option1 != "請選擇...":
                c_id = selected_option1.split(" - ")[0]
                st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + deck_qty
                st.success(f"✅ 已將 {deck_qty} 張 【{c_id}】 加入牌組！")
                st.rerun()
                
        # 🌟 擴充：加入 AI 掃描與進階匯入
        with st.expander("📝 進階：批次匯入與 📸 AI 圖片掃描"):
            auto_cheapest = st.checkbox("💸 抄牌或掃描時自動將卡片替換為「同名最低價」版本", value=True, key="chk_cheap_deck")
            st.divider()
            
            # --- AI 掃描區塊 (結帳區) ---
            st.write("#### 📸 AI 圖片上傳辨識")
            gemini_key_deck = st.text_input("輸入 Gemini API Key 來啟用 AI 掃描：", type="password", key="gemini_key_deck")
            st.caption("免費的 Gemini API Key 可於 [Google AI Studio](https://aistudio.google.com/) 取得。")
            
            # 🌟 只保留檔案上傳功能
            active_img_deck = st.file_uploader("📂 上傳卡片圖片", type=["jpg", "jpeg", "png"], key="up_deck")
            
            if active_img_deck:
                if not gemini_key_deck:
                    st.warning("⚠️ 請先在上方輸入 Gemini API Key 才能執行 AI 辨識。")
                else:
                    if st.button("🔍 執行 AI 辨識並加入牌組", type="primary", key="btn_scan_deck"):
                        with st.spinner("AI 正在火力全開解析多張卡圖中..."):
                            success, c_ids, raw_text = scan_card_image(active_img_deck, gemini_key_deck)
                            if success:
                                added_cards = []
                                # 🌟 用迴圈處理清單裡的每一張卡號
                                for c_id in c_ids:
                                    if auto_cheapest: 
                                        c_id = get_cheapest_version(c_id)
                                    if c_id in prices:
                                        st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + 1
                                        added_cards.append(f"{c_id}({card_names.get(c_id, '未知')})")
                                
                                if added_cards:
                                    st.success(f"🎉 成功一口氣掃描並加入 {len(added_cards)} 張卡片！\n\n詳細明細：{', '.join(added_cards)}")
                                    st.rerun()
                                else:
                                    st.warning("雖然掃描到了卡號，但比對後發現都不在我們的資料庫中。")
                            else:
                                st.error(f"辨識失敗，AI 未能找到任何卡號。")
                                
            st.divider()
            
            # --- 原本的批次匯入與 API ---
            col_text, col_csv, col_code = st.columns(3)
            with col_text:
                deck_input = st.text_area("✍️ 貼上牌組文字：", placeholder="例如: BP01-001 3", height=100)
                if st.button("確認匯入文字"):
                    for line in deck_input.strip().split('\n'):
                        parts = line.split()
                        if len(parts) >= 2:
                            c_id = parts[0].strip()
                            try: q = int(parts[1].strip())
                            except: q = 1
                            if c_id in prices: 
                                if auto_cheapest: c_id = get_cheapest_version(c_id)
                                st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                    st.rerun()
            with col_csv:
                deck_csv_file = st.file_uploader("📁 上傳 CSV 牌組", type=["csv"], key="deck_csv_uploader")
                if deck_csv_file is not None and st.button("🚀 確認匯入 CSV"):
                    try:
                        reader = csv.reader(io.StringIO(deck_csv_file.getvalue().decode("utf-8-sig")))
                        first_row = next(reader, None)
                        if first_row and first_row[0].startswith(("BP", "SD", "PR")) and len(first_row) >= 2: 
                            if first_row[0].strip() in prices: 
                                c_id = first_row[0].strip()
                                if auto_cheapest: c_id = get_cheapest_version(c_id)
                                st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + int(first_row[1].strip())
                        for row in reader:
                            if len(row) >= 2:
                                c_id = row[0].strip()
                                try: q = int(row[1].strip())
                                except: q = 1
                                if c_id in prices: 
                                    if auto_cheapest: c_id = get_cheapest_version(c_id)
                                    st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                        st.success("匯入成功！")
                        st.rerun()
                    except Exception as e: st.error(f"檔案讀取失敗：{e}")
            with col_code:
                st.write("#### 🌐 Deck Log 代碼")
                decklog_code = st.text_input("輸入代碼：", key="decklog_code_input")
                if st.button("🚀 雲端抓取牌組"):
                    if decklog_code:
                        with st.spinner("前往 Deck Log 抓取中..."):
                            success, msg = fetch_decklog(decklog_code, auto_cheapest)
                            if success: st.success(msg); st.rerun()
                            else: st.error(msg)

    with col_img1:
        if selected_option1 != "請選擇...":
            st.image(get_card_image_url(selected_option1.split(" - ")[0]), width=150)

    st.divider()
    st.write("### 🧾 結帳明細")
    if st.session_state.deck_list:
        if st.button("🗑️ 清空牌組"): st.session_state.deck_list = {}; st.rerun()
        total_cost = 0
        receipt_list = []
        for c_id, req_qty in st.session_state.deck_list.items():
            owned_qty = st.session_state.my_inventory.get(c_id, 0)
            missing_qty = max(0, req_qty - owned_qty)
            price = prices.get(c_id, 0)
            if missing_qty > 0:
                cost = price * missing_qty
                total_cost += cost
                receipt_list.append({"卡號": c_id, "卡名": card_names.get(c_id, ""), "需要": req_qty, "已有": owned_qty, "尚缺": missing_qty, "單價": price, "小計": cost})
                
        if receipt_list:
            st.dataframe(receipt_list, use_container_width=True)
            st.error(f"### 💸 扣除已有卡片後，補齊還需花費： {total_cost} 円")
        else:
            st.success("🎉 這副牌組的所有卡片你都已經擁有了！")
            
        for c_id, req_qty in list(st.session_state.deck_list.items()):
            c1, c_minus, c_q, c_plus = st.columns([5, 1, 1, 1])
            c1.write(f"**{c_id}** - {card_names.get(c_id, '')}")
            if c_minus.button("➖", key=f"d_minus_{c_id}"):
                st.session_state.deck_list[c_id] -= 1
                if st.session_state.deck_list[c_id] <= 0: del st.session_state.deck_list[c_id]
                st.rerun()
            c_q.markdown(f"### {req_qty}")
            if c_plus.button("➕", key=f"d_plus_{c_id}"):
                st.session_state.deck_list[c_id] += 1
                st.rerun()
    else: st.info("牌組空空如也。")

# ----- 分頁 2：背包區 -----
with tab2:
    if st.session_state.unsaved_changes:
        st.warning("⚠️ 你的背包目前有【尚未儲存】的變更！離開前請記得存檔。")
        if st.button("💾 將變更儲存至 Google 雲端", type="primary", use_container_width=True):
            if save_inventory_to_sheets():
                st.success("🎉 雲端儲存成功！")
                st.rerun()
                
    st.subheader("📝 登記新卡片")
    col_p2, col_r2, col_c2, col_q2 = st.columns(4)
    with col_p2: inv_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="inv_pack")
    cards_in_pack2 = all_cards if inv_pack == "全部" else [c for c in all_cards if c.startswith(inv_pack + "-")]
    prefixes2 = sorted(list(set([get_prefix(c) for c in cards_in_pack2])))
    
    with col_r2: inv_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes2, key="inv_prefix")
    cards_in_prefix2 = sorted(cards_in_pack2 if inv_prefix == "全部" else [c for c in cards_in_pack2 if get_prefix(c) == inv_prefix])
    
    card_options2 = [f"{c} - {card_names.get(c, '未知')}" for c in cards_in_prefix2]
    with col_c2: selected_option2 = st.selectbox("3. 選擇卡號/卡名：", ["請選擇..."] + card_options2, key="inv_select")
    with col_q2: qty_to_add = st.number_input("4. 擁有幾張？", min_value=1, value=1, key="inv_qty")
    
    col_btn2, col_img2 = st.columns([4, 1])
    with col_btn2:
        st.write("")
        if st.button("➕ 加入背包 (暫存)", key="btn_add_inv"):
            if selected_option2 != "請選擇...":
                c_id = selected_option2.split(" - ")[0]
                st.session_state.my_inventory[c_id] = st.session_state.my_inventory.get(c_id, 0) + qty_to_add
                st.session_state.unsaved_changes = True 
                st.rerun()
                
        # 🌟 背包區的 AI 圖片掃描擴充
        with st.expander("📸 AI 智慧圖片掃描入庫 (上傳圖片)"):
            st.write("上傳卡圖照片，讓 AI 自動幫你找出卡號並登記入庫！")
            gemini_key_inv = st.text_input("輸入 Gemini API Key：", type="password", key="gemini_key_inv")
            
            # 🌟 只保留檔案上傳功能
            active_img_inv = st.file_uploader("📂 上傳圖片", type=["jpg", "jpeg", "png"], key="up_inv")
            
            if active_img_inv:
                if not gemini_key_inv:
                    st.warning("⚠️ 請先輸入 Gemini API Key 才能執行 AI 辨識。")
                else:
                    if st.button("🔍 執行 AI 辨識並加入背包", type="primary", key="btn_scan_inv"):
                        with st.spinner("AI 正在精準定位多張卡圖並登記入庫..."):
                            success, c_ids, raw_text = scan_card_image(active_img_inv, gemini_key_inv)
                            if success:
                                added_count = 0
                                # 🌟 用迴圈把辨識到的卡片通通 +1 張
                                for c_id in c_ids:
                                    if c_id in prices:
                                        st.session_state.my_inventory[c_id] = st.session_state.my_inventory.get(c_id, 0) + 1
                                        added_count += 1
                                
                                if added_count > 0:
                                    st.session_state.unsaved_changes = True
                                    st.success(f"🎉 跨時空多卡辨識成功！已自動將 {added_count} 張卡片暫存入庫！(別忘了按下上方的儲存鈕喔！)")
                                    st.rerun()
                                else:
                                    st.warning("辨識出的卡號皆不在我們的價格資料庫中。")
                            else:
                                st.error(f"辨識失敗，AI 看到的內容是：{raw_text}")
    with col_img2:
        if selected_option2 != "請選擇...":
            st.image(get_card_image_url(selected_option2.split(" - ")[0]), width=150)

    st.divider()
    total_backpack_value = sum([prices.get(c_id, 0) * q for c_id, q in st.session_state.my_inventory.items() if q > 0])
    col_title, col_value = st.columns([2, 1])
    with col_title: st.write("### 🎒 我的庫存清單")
    with col_value: st.info(f"💰 **總資產估值： {total_backpack_value} 円**")
    
    if st.session_state.my_inventory and any(v > 0 for v in st.session_state.my_inventory.values()):
        col_f1, col_f2 = st.columns(2)
        owned_packs = sorted(list(set([k.split('-')[0] for k, v in st.session_state.my_inventory.items() if '-' in k and v > 0])))
        with col_f1: filter_pack = st.selectbox("過濾卡包", ["全部"] + owned_packs)
        filtered_inv = [k for k, v in st.session_state.my_inventory.items() if v > 0]
        if filter_pack != "全部": filtered_inv = [k for k in filtered_inv if k.startswith(filter_pack + "-")]
            
        owned_prefixes = sorted(list(set([get_prefix(k) for k in filtered_inv])))
        with col_f2: filter_prefix = st.selectbox("過濾前綴", ["全部"] + owned_prefixes)
        if filter_prefix != "全部": filtered_inv = [k for k in filtered_inv if get_prefix(k) == filter_prefix]

        if filtered_inv:
            st.markdown("---")
            h1, h_price, h_minus, h_qty, h_plus = st.columns([4, 2, 1, 1, 1])
            h1.markdown("**📦 卡片資訊**"); h_price.markdown("**💸 單價 (小計)**"); h_qty.markdown("**數量**")
            st.markdown("---")
            
            for c_id in sorted(filtered_inv):
                qty = st.session_state.my_inventory[c_id]
                unit_price = prices.get(c_id, 0)
                
                c1, c_price, c_minus, c_qty, c_plus = st.columns([4, 2, 1, 1, 1])
                c1.write(f"**{c_id}**<br><small>{card_names.get(c_id, '')}</small>", unsafe_allow_html=True)
                c_price.markdown(f"<span style='color: #4CAF50;'>{unit_price} 円</span><br><small style='color: gray;'>(計: {unit_price * qty})</small>", unsafe_allow_html=True)
                
                if c_minus.button("➖", key=f"inv_minus_{c_id}"):
                    st.session_state.my_inventory[c_id] -= 1
                    if st.session_state.my_inventory[c_id] < 0: st.session_state.my_inventory[c_id] = 0
                    st.session_state.unsaved_changes = True
                    st.rerun()
                c_qty.markdown(f"### {qty}")
                if c_plus.button("➕", key=f"inv_plus_{c_id}"):
                    st.session_state.my_inventory[c_id] += 1
                    st.session_state.unsaved_changes = True 
                    st.rerun()
        else: st.warning("無符合條件的卡片。")
    else: st.info("背包空空如也。")

    with st.expander(f"⚙️ 進階功能：匯出與匯入【{selected_backpack}】"):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["卡號", "擁有數量"])
        for c_id, q in st.session_state.my_inventory.items():
            if q > 0: writer.writerow([c_id, q])
        st.download_button(label="📥 下載庫存 CSV 備份", data=output.getvalue(), file_name=f"{selected_backpack}_inventory.csv", mime="text/csv")

# ----- 分頁 3：單價與卡圖查詢區 -----
with tab3:
    st.subheader("🔍 選擇卡片或搜尋關鍵字")
    col_p3, col_r3, col_c3 = st.columns(3)
    with col_p3: search_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="search_pack")
    cards_in_pack3 = all_cards if search_pack == "全部" else [c for c in all_cards if c.startswith(search_pack + "-")]
    prefixes3 = sorted(list(set([get_prefix(c) for c in cards_in_pack3])))
    
    with col_r3: search_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes3, key="search_prefix")
    cards_in_prefix3 = sorted(cards_in_pack3 if search_prefix == "全部" else [c for c in cards_in_pack3 if get_prefix(c) == search_prefix])
    
    card_options3 = [f"{c} - {card_names.get(c, '未知')}" for c in cards_in_prefix3]
    with col_c3: selected_option3 = st.selectbox("3. 選擇卡號/卡名：", ["請選擇..."] + card_options3, key="search_select")

    st.divider()
    if selected_option3 != "請選擇...":
        c_id_dropdown = selected_option3.split(" - ")[0]
        col_info_d, col_img_d = st.columns([3, 1])
        with col_info_d:
            st.markdown(f"### 🏷️ {c_id_dropdown}")
            st.markdown(f"#### 🃏 卡名：**{card_names.get(c_id_dropdown, '未知')}**")
            st.markdown(f"#### 💸 價格：<span style='color: #4CAF50;'>{prices.get(c_id_dropdown, 0)} 円</span>", unsafe_allow_html=True)
            
            st.write("")
            quick_qty_d = st.number_input(f"想要快速加入幾張到【{selected_backpack}】？", min_value=1, value=1, key="q_qty_drop")
            if st.button(f"🚀 快速加到背包", key="q_btn_drop"):
                st.session_state.my_inventory[c_id_dropdown] = st.session_state.my_inventory.get(c_id_dropdown, 0) + quick_qty_d
                st.session_state.unsaved_changes = True
                st.success(f"已暫存 {quick_qty_d} 張！記得切換回背包存檔。")
        with col_img_d: st.image(get_card_image_url(c_id_dropdown), width=180)
    else: st.info("👆 請從上方選單選擇，或使用下方的快速搜尋。")

    st.write("---")
    st.subheader("⚡ 關鍵字快速搜尋 (支援卡名、日文、卡號)")
    keyword = st.text_input("請輸入卡名或卡號關鍵字：", key="global_search_input")
    if keyword:
        results = [c for c in prices.keys() if keyword.lower() in c.lower() or keyword.lower() in card_names.get(c, '').lower()]
        if results:
            st.success(f"🎉 成功找到 {len(results)} 筆結果：")
            for c_id in sorted(results):
                col_info3, col_img3 = st.columns([3, 1])
                with col_info3:
                    st.markdown(f"### 🏷️ {c_id}")
                    st.markdown(f"#### 🃏 卡名：**{card_names.get(c_id, '未知')}**")
                    st.markdown(f"#### 💸 價格：<span style='color: #4CAF50;'>{prices.get(c_id, 0)} 円</span>", unsafe_allow_html=True)
                    quick_qty = st.number_input(f"想要快速加入幾張？", min_value=1, value=1, key=f"q_qty_{c_id}")
                    if st.button(f"🚀 快速加到背包", key=f"q_btn_{c_id}"):
                        st.session_state.my_inventory[c_id] = st.session_state.my_inventory.get(c_id, 0) + quick_qty
                        st.session_state.unsaved_changes = True
                        st.success(f"已成功暫存！")
                with col_img3: st.image(get_card_image_url(c_id), width=180)
                st.divider()

# -----------------------------------------------------------
# 🌟 ----- 新增分頁 4：所有背包總覽 -----
with tab4:
    st.subheader("📊 全背包庫存交叉大總覽")
    st.caption("點擊下方按鈕將會即時連線掃描 Google Sheet 內的所有分頁背包，並進行數據自動整合與資產清算。")
    
    if st.button("🔄 讀取並整合所有背包數據", type="primary", use_container_width=True):
        with st.spinner("正在穿越雲端，掃描所有背包分頁中...請稍候..."):
            try:
                # 建立一個大字典來存放整合資料
                # 結構: { 卡號: { "背包A": 數量, "背包B": 數量, ... } }
                master_data = {}
                
                # 1. 逐一掃描所有分頁
                for ws_title in worksheets:
                    ws = doc.worksheet(ws_title)
                    rows = ws.get_all_records()
                    for row in rows:
                        if '卡號' in row and '擁有數量' in row:
                            c_id = str(row['卡號']).strip()
                            try: q = int(row['擁有數量'])
                            except: q = 0
                            
                            if q > 0:
                                if c_id not in master_data:
                                    master_data[c_id] = {t: 0 for t in worksheets}
                                master_data[c_id][ws_title] = q
                
                # 2. 轉換為漂亮的 Pandas DataFrame 來進行前端展示
                if master_data:
                    table_rows = []
                    grand_total_value = 0
                    
                    for c_id, bp_qtys in sorted(master_data.items()):
                        total_qty = sum(bp_qtys.values())
                        unit_price = prices.get(c_id, 0)
                        subtotal_value = unit_price * total_qty
                        grand_total_value += subtotal_value
                        
                        # 打包每一行的資訊
                        row_dict = {
                            "卡號": c_id,
                            "卡牌名稱": card_names.get(c_id, "未知"),
                            "單價 (円)": unit_price
                        }
                        # 動態加入各個背包的欄位
                        for ws_title in worksheets:
                            row_dict[f"🎒 {ws_title}"] = bp_qtys[ws_title]
                            
                        row_dict["📊 合計張外"] = total_qty
                        row_dict["💰 總價值 (円)"] = subtotal_value
                        table_rows.append(row_dict)
                        
                    df = pd.DataFrame(table_rows)
                    
                    # 呈現資產大總管結果
                    st.write("")
                    st.success(f"### 👑 全庫存終極總資產： **{grand_total_value} 円**")
                    st.caption(f"💡 目前總共跨背包收集了 {len(master_data)} 種不同的卡片。")
                    
                    # 顯示超大交叉對照表
                    st.dataframe(df, use_container_width=True, height=500)
                else:
                    st.info("雲端上所有的背包好像都是空空的喔！")
            except Exception as e:
                st.error(f"跨背包整合失敗：{e}")
