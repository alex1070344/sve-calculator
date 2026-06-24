import streamlit as st
import csv
import io
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="SVE 缺卡計算機", page_icon="🃏", layout="wide")

# ==========================================
# 🌟 初始化：網頁記憶體
if "deck_list" not in st.session_state: st.session_state.deck_list = {}
if "my_inventory" not in st.session_state: st.session_state.my_inventory = {}
if "current_bp_name" not in st.session_state: st.session_state.current_bp_name = ""
if "unsaved_changes" not in st.session_state: st.session_state.unsaved_changes = False

# ==========================================
# 🌟 1. 初始化連線
@st.cache_resource
def init_gspread_client():
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"連線 Google 失敗：{e}")
        return None

client = init_gspread_client()
if not client: st.stop()

# 🌟 2. 鎖定試算表檔案
try:
    # ⚠️⚠️⚠️ 請確保這裡是你的正確 ID ⚠️⚠️⚠️
    sheet_id = "1Re2ZLcJKkFqyGe3sXaieAeB8E9U9k4PxghYbKAuXSZ4" 
    doc = client.open_by_key(sheet_id)
except Exception as e:
    st.error(f"無法開啟試算表：{e}")
    st.stop()

# ==========================================
# 🌟 3. 背包管理系統
worksheets = [ws.title for ws in doc.worksheets()]

with st.sidebar:
    st.title("🎒 我的背包管理")
    selected_backpack = st.selectbox("切換當前背包：", worksheets)
    
    st.divider()
    st.write("### ⚙️ 背包設定")
    with st.expander("➕ 建立全新背包"):
        new_bp_name = st.text_input("輸入新背包名稱：")
        if st.button("🚀 建立背包"):
            if new_bp_name and new_bp_name not in worksheets:
                new_sheet = doc.add_worksheet(title=new_bp_name, rows="1000", cols="2")
                try: new_sheet.update(values=[["卡號", "擁有數量"]], range_name='A1')
                except: new_sheet.update('A1', [["卡號", "擁有數量"]])
                st.success(f"✅ 背包【{new_bp_name}】建立成功！")
                st.rerun()
                
    with st.expander("🗑️ 刪除當前背包"):
        st.warning(f"確定要刪除【{selected_backpack}】？")
        if st.button("🚨 確認刪除"):
            if len(worksheets) <= 1: st.error("最後一個背包無法刪除！")
            else:
                doc.del_worksheet(doc.worksheet(selected_backpack))
                st.success("已刪除！")
                st.rerun()

st.title(f"🃏 SVE 缺卡計算機 ─ 【{selected_backpack}】")

# ==========================================
# 🌟 4. 讀取與儲存邏輯 (智能合併)
current_sheet = doc.worksheet(selected_backpack)

if st.session_state.current_bp_name != selected_backpack:
    try:
        records = current_sheet.get_all_records()
        inv = {}
        for row in records:
            if '卡號' in row and '擁有數量' in row:
                try: inv[str(row['卡號'])] = int(row['擁有數量'])
                except: pass
        st.session_state.my_inventory = inv
        st.session_state.current_bp_name = selected_backpack
        st.session_state.unsaved_changes = False
    except Exception as e:
        st.error(f"讀取背包資料失敗：{e}")

def save_inventory_to_sheets():
    try:
        records = current_sheet.get_all_records()
        cloud_inv = {}
        for row in records:
            if '卡號' in row and '擁有數量' in row:
                try: cloud_inv[str(row['卡號'])] = int(row['擁有數量'])
                except: pass
        
        final_inv = {}
        for c_id, q in cloud_inv.items():
            if c_id not in st.session_state.my_inventory:
                final_inv[c_id] = q
        for c_id, q in st.session_state.my_inventory.items():
            if q > 0:
                final_inv[c_id] = q
        
        data = [["卡號", "擁有數量"]]
        for c_id, q in sorted(final_inv.items()):
            data.append([c_id, q])
            
        current_sheet.clear()
        try: current_sheet.update(values=data, range_name='A1')
        except: current_sheet.update('A1', data)
            
        st.session_state.my_inventory = final_inv
        st.session_state.unsaved_changes = False
        return True
    except Exception as e:
        st.error(f"❌ 雲端同步失敗: {e}")
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
# 🌟 5. 讀取本機價格表與圖片網址
prices = {}
card_images = {} # 存放卡圖網址的字典

try:
    with open("cards_price.csv", "r", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        next(reader) # 跳過標題
        for row in reader: 
            if len(row) >= 2:
                prices[row[0]] = int(row[1])
            # 如果 CSV 裡面有第三個欄位，就把圖片網址存起來
            if len(row) >= 3 and row[2].startswith("http"):
                card_images[row[0]] = row[2]
except: 
    pass

def get_card_image_url(card_id):
    """取得卡圖網址，如果 CSV 沒抓到就給預設假圖"""
    if card_id in card_images and card_images[card_id]:
        return card_images[card_id]
    return f"https://placehold.co/300x420/1E1E1E/FFD700.png?text={card_id}"

# ==========================================
tab1, tab2, tab3 = st.tabs(["🧾 牌組結帳 (計算缺卡)", "🎒 我的庫存與資產", "💰 單卡價格與卡圖查詢"])

# -----------------------------------------------------------
# ----- 分頁 1：結帳區 -----
with tab1:
    st.subheader("🔍 查詢並加入結帳牌組")
    all_cards = list(prices.keys())
    packs = sorted(list(set([card.split('-')[0] for card in all_cards if '-' in card])))
    
    col_p1, col_r1, col_c1, col_q1 = st.columns(4)
    with col_p1: deck_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="deck_pack")
    cards_in_pack1 = all_cards if deck_pack == "全部" else [c for c in all_cards if c.startswith(deck_pack + "-")]
    prefixes1 = sorted(list(set([get_prefix(c) for c in cards_in_pack1])))
    
    with col_r1: deck_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes1, key="deck_prefix")
    cards_in_prefix1 = sorted(cards_in_pack1 if deck_prefix == "全部" else [c for c in cards_in_pack1 if get_prefix(c) == deck_prefix])
    
    with col_c1: deck_card = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix1, key="deck_card")
    with col_q1: deck_qty = st.number_input("4. 需要幾張？", min_value=1, max_value=50, value=1, key="deck_qty")
    
    # 🌟 版面配置：左邊按鈕區，右邊顯示卡圖預覽
    col_btn1, col_img1 = st.columns([3, 1])
    with col_btn1:
        st.write("") # 排版用
        if st.button("➕ 加入結帳牌組"):
            if deck_card != "請選擇...":
                st.session_state.deck_list[deck_card] = st.session_state.deck_list.get(deck_card, 0) + deck_qty
                st.success(f"✅ 已加入 {deck_qty} 張 【{deck_card}】")
                st.rerun()
                
        with st.expander("📝 進階：批次匯入牌組 (支援字體防呆)"):
            col_text, col_csv = st.columns(2)
            with col_text:
                deck_input = st.text_area("✍️ 貼上牌組文字：", height=100)
                if st.button("確認匯入文字"):
                    for line in deck_input.strip().split('\n'):
                        parts = line.split()
                        if len(parts) >= 2:
                            c_id = parts[0].strip()
                            try: q = int(parts[1].strip())
                            except: q = 1
                            if c_id in prices: st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                    st.rerun()
            with col_csv:
                deck_csv_file = st.file_uploader("📁 上傳 CSV 牌組", type=["csv"], key="deck_csv_uploader")
                if deck_csv_file is not None and st.button("🚀 確認匯入 CSV"):
                    try:
                        reader = csv.reader(io.StringIO(deck_csv_file.getvalue().decode("utf-8-sig")))
                        first_row = next(reader, None)
                        if first_row and first_row[0].startswith(("BP", "SD", "PR")) and len(first_row) >= 2: 
                            if first_row[0].strip() in prices: st.session_state.deck_list[first_row[0].strip()] = st.session_state.deck_list.get(first_row[0].strip(), 0) + int(first_row[1].strip())
                        for row in reader:
                            if len(row) >= 2:
                                c_id = row[0].strip()
                                try: q = int(row[1].strip())
                                except: q = 1
                                if c_id in prices: st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                        st.success("匯入成功！")
                        st.rerun()
                    except Exception as e: st.error(f"檔案讀取失敗：{e}")

    with col_img1:
        if deck_card != "請選擇...":
            # 🌟 顯示從 CSV 讀取出來的卡圖
            st.image(get_card_image_url(deck_card), use_container_width=True)

    st.divider()
    st.write("### 🛒 結帳明細")
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
                receipt_list.append({"卡號": c_id, "需要": req_qty, "已有": owned_qty, "尚缺": missing_qty, "單價": price, "小計": cost})
                
        if receipt_list:
            st.dataframe(receipt_list, use_container_width=True)
            st.error(f"### 💸 扣除已有卡片後，補齊還需花費： {total_cost} 円")
        else:
            st.success("🎉 這副牌組的所有卡片你都已經擁有了！")

        for c_id, req_qty in list(st.session_state.deck_list.items()):
            c1, c2, c3, c_minus, c_q, c_plus = st.columns([1.5, 1.5, 3, 1, 1, 1])
            c1.write(c_id.split('-')[0] if '-' in c_id else "其他")
            c2.write(get_prefix(c_id))
            c3.write(c_id)
            if c_minus.button("➖", key=f"d_minus_{c_id}"):
                st.session_state.deck_list[c_id] -= 1
                if st.session_state.deck_list[c_id] <= 0: del st.session_state.deck_list[c_id]
                st.rerun()
            c_q.markdown(f"### {req_qty}")
            if c_plus.button("➕", key=f"d_plus_{c_id}"):
                st.session_state.deck_list[c_id] += 1
                st.rerun()
    else: st.info("牌組空空如也。")

# -----------------------------------------------------------
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
    
    with col_c2: card_to_add = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix2, key="inv_card")
    with col_q2: qty_to_add = st.number_input("4. 擁有幾張？", min_value=0, max_value=50, value=1, key="inv_qty")
        
    col_btn2, col_img2 = st.columns([3, 1])
    with col_btn2:
        st.write("")
        if st.button("➕ 加入背包 (暫存)"):
            if card_to_add != "請選擇...":
                st.session_state.my_inventory[card_to_add] = st.session_state.my_inventory.get(card_to_add, 0) + qty_to_add
                st.session_state.unsaved_changes = True 
                st.rerun()

    with col_img2:
        if card_to_add != "請選擇...":
            # 🌟 顯示卡圖
            st.image(get_card_image_url(card_to_add), use_container_width=True)

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
            h1, h2, h3, h_price, h_minus, h_qty, h_plus = st.columns([1.5, 1.5, 2.5, 2, 1, 1, 1])
            h1.markdown("**📦 卡包**"); h2.markdown("**✨ 前綴**"); h3.markdown("**🏷️ 卡號**")
            h_price.markdown("**💸 單價 (小計)**"); h_qty.markdown("**數量**")
            st.markdown("---")
            
            filtered_inv.sort()
            for c_id in filtered_inv:
                qty = st.session_state.my_inventory[c_id]
                unit_price = prices.get(c_id, 0)
                subtotal = unit_price * qty
                
                c1, c2, c3, c_price, c_minus, c_qty, c_plus = st.columns([1.5, 1.5, 2.5, 2, 1, 1, 1])
                c1.write(c_id.split('-')[0] if '-' in c_id else "其他")
                c2.write(get_prefix(c_id)); c3.write(c_id)
                c_price.markdown(f"<span style='color: #4CAF50;'>{unit_price} 円</span><br><small style='color: gray;'>(計: {subtotal})</small>", unsafe_allow_html=True)
                
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

    # ==========================================
    # 備份與還原區塊
    st.write("")
    with st.expander(f"⚙️ 進階功能：匯出與匯入【{selected_backpack}】"):
        col_dl, col_ul = st.columns(2)
        with col_dl:
            st.write("#### ⬇️ 下載備份檔")
            if st.session_state.my_inventory:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["卡號", "擁有數量"])
                for c_id, q in st.session_state.my_inventory.items():
                    if q > 0: writer.writerow([c_id, q])
                st.download_button(label="📥 下載庫存 CSV 備份", data=output.getvalue(), file_name=f"{selected_backpack}_inventory.csv", mime="text/csv")
            else: st.warning("目前背包無資料。")
                
        with col_ul:
            st.write("#### ⬆️ 上傳還原檔")
            uploaded_file = st.file_uploader("選擇你的 CSV 備份檔", type=["csv"], key="inventory_csv_uploader")
            if uploaded_file is not None:
                import_mode = st.radio("請選擇匯入模式：", ("🔄 取代現有背包", "➕ 增加至現有背包"))
                if st.button("🚀 執行匯入 (需手動儲存)"):
                    try:
                        reader = csv.reader(io.StringIO(uploaded_file.getvalue().decode("utf-8-sig")))
                        next(reader, None)
                        if import_mode.startswith("🔄"): st.session_state.my_inventory.clear()
                        for row in reader:
                            if len(row) >= 2: st.session_state.my_inventory[row[0]] = st.session_state.my_inventory.get(row[0], 0) + int(row[1]) if not import_mode.startswith("🔄") else int(row[1])
                        st.session_state.unsaved_changes = True 
                        st.success("🎉 資料匯入成功！請記得按下上方的「儲存至雲端」按鈕。")
                        st.rerun()
                    except Exception as e: st.error(f"檔案格式錯誤：{e}")

# -----------------------------------------------------------
# ----- 分頁 3：單價與卡圖查詢區 -----
with tab3:
    st.subheader("🔍 查詢單張卡片價格與卡圖")
    
    col_p3, col_r3, col_c3 = st.columns(3)
    with col_p3: search_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="search_pack")
    cards_in_pack3 = all_cards if search_pack == "全部" else [c for c in all_cards if c.startswith(search_pack + "-")]
    prefixes3 = sorted(list(set([get_prefix(c) for c in cards_in_pack3])))
    
    with col_r3: search_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes3, key="search_prefix")
    cards_in_prefix3 = sorted(cards_in_pack3 if search_prefix == "全部" else [c for c in cards_in_pack3 if get_prefix(c) == search_prefix])
    
    with col_c3: search_card = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix3, key="search_card")
        
    st.divider()
    
    if search_card != "請选择...":
        col_info3, col_img3 = st.columns([2, 1])
        with col_info3:
            card_price = prices.get(search_card, 0)
            st.markdown(f"### 🏷️ 卡號： **{search_card}**")
            st.markdown(f"### 💸 目前單價： **<span style='color: #4CAF50;'>{card_price} 円</span>**", unsafe_allow_html=True)
            
            # 加入背包按鈕 (捷徑)
            st.write("---")
            add_qty = st.number_input("快速加入背包張數：", min_value=1, max_value=50, value=1, key="quick_add_qty")
            if st.button("➕ 快速登記至目前的背包", type="primary"):
                st.session_state.my_inventory[search_card] = st.session_state.my_inventory.get(search_card, 0) + add_qty
                st.session_state.unsaved_changes = True
                st.success(f"已暫存 {add_qty} 張 {search_card}！請記得切換回背包頁面存檔。")
        with col_img3:
            # 🌟 顯示大張卡圖
            st.image(get_card_image_url(search_card), use_container_width=True)
    else:
        st.info("👆 請從上方選單選擇，或使用下方的快速搜尋。")
        
    st.write("---")
    st.write("#### ⚡ 快速關鍵字搜尋")
    st.caption("可以直接輸入部分卡號 (例如打 '001' 或 'BP01-001')")
    quick_search = st.text_input("輸入卡號關鍵字：", key="quick_search_input")
    
    if quick_search:
        results = [c for c in all_cards if quick_search.upper() in c.upper()]
        if results:
            st.success(f"✅ 找到 {len(results)} 筆符合的卡片：")
            search_list = [{"卡號": c_id, "單價 (円)": prices.get(c_id, 0)} for c_id in sorted(results)]
            st.dataframe(search_list, use_container_width=True)
        else:
            st.warning("找不到符合的卡片，請確認輸入的關鍵字是否正確！")
