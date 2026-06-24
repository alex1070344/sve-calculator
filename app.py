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

current_sheet = doc.worksheet(selected_backpack)

if st.session_state.current_bp_name != selected_backpack:
    try:
        records = current_sheet.get_all_records()
        st.session_state.my_inventory = {str(row['卡號']): int(row['擁有數量']) for row in records if '卡號' in row}
        st.session_state.current_bp_name = selected_backpack
        st.session_state.unsaved_changes = False
    except Exception as e:
        st.error(f"讀取資料失敗：{e}")

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

# ==========================================
# 🌟 3. 載入 CSV 資料 (價格、卡圖、卡名)
prices = {}
card_images = {}
card_names = {}

try:
    with open("cards_price.csv", "r", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        next(reader) 
        for row in reader: 
            if len(row) >= 4:
                prices[row[0]] = int(row[1])
                card_images[row[0]] = row[2]
                card_names[row[0]] = row[3]
except: pass

def get_card_image_url(card_id):
    return card_images.get(card_id) if card_images.get(card_id) else f"https://placehold.co/150x210/1E1E1E/FFD700.png?text={card_id}"

# ==========================================
# 🌟 4. 網頁介面設計
tab1, tab2, tab3 = st.tabs(["🧾 結帳與組牌", "🎒 背包庫存", "🔍 查詢卡片與卡名"])

# ----- 分頁 1：結帳區 -----
with tab1:
    st.subheader("🛒 加入結帳牌組")
    search_term1 = st.text_input("輸入卡號或卡名搜尋 (結帳區)：", key="deck_search")
    options1 = [f"{c} - {card_names.get(c, '未知')}" for c in prices.keys() if search_term1.lower() in c.lower() or search_term1.lower() in card_names.get(c, '').lower()]
    
    col_d1, col_d2 = st.columns([3, 1])
    with col_d1:
        selected_option1 = st.selectbox("選擇卡片：", ["請選擇..."] + options1, key="deck_select")
        if selected_option1 != "請選擇...":
            card_id1 = selected_option1.split(" - ")[0]
            qty1 = st.number_input("需要幾張？", min_value=1, value=1, key="deck_qty")
            if st.button("➕ 加入結帳"):
                st.session_state.deck_list[card_id1] = st.session_state.deck_list.get(card_id1, 0) + qty1
                st.success(f"已加入 {qty1} 張 {card_id1}")
                st.rerun()
    with col_d2:
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
            c1, c2, c_minus, c_q, c_plus = st.columns([3, 2, 1, 1, 1])
            c1.write(f"{c_id} - {card_names.get(c_id, '')}")
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
    search_term2 = st.text_input("輸入卡號或卡名搜尋 (背包區)：", key="inv_search")
    options2 = [f"{c} - {card_names.get(c, '未知')}" for c in prices.keys() if search_term2.lower() in c.lower() or search_term2.lower() in card_names.get(c, '').lower()]
    
    col_i1, col_i2 = st.columns([3, 1])
    with col_i1:
        selected_option2 = st.selectbox("選擇卡片：", ["請選擇..."] + options2, key="inv_select")
        if selected_option2 != "請選擇...":
            card_id2 = selected_option2.split(" - ")[0]
            qty2 = st.number_input("擁有幾張？", min_value=1, value=1, key="inv_qty")
            if st.button("➕ 加入背包 (暫存)"):
                st.session_state.my_inventory[card_id2] = st.session_state.my_inventory.get(card_id2, 0) + qty2
                st.session_state.unsaved_changes = True 
                st.rerun()
    with col_i2:
        if selected_option2 != "請選擇...":
            st.image(get_card_image_url(selected_option2.split(" - ")[0]), width=150)

    st.divider()
    total_backpack_value = sum([prices.get(c_id, 0) * q for c_id, q in st.session_state.my_inventory.items() if q > 0])
    col_title, col_value = st.columns([2, 1])
    with col_title: st.write("### 🎒 我的庫存清單")
    with col_value: st.info(f"💰 **總資產估值： {total_backpack_value} 円**")
    
    if st.session_state.my_inventory and any(v > 0 for v in st.session_state.my_inventory.values()):
        for c_id, qty in sorted(st.session_state.my_inventory.items()):
            if qty > 0:
                c1, c_price, c_minus, c_qty, c_plus = st.columns([4, 2, 1, 1, 1])
                c1.write(f"**{c_id}**<br><small>{card_names.get(c_id, '')}</small>", unsafe_allow_html=True)
                unit_price = prices.get(c_id, 0)
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
    else: st.info("背包空空如也。")

# ----- 分頁 3：單價與卡圖查詢區 -----
with tab3:
    st.subheader("🔍 查詢單張卡片")
    keyword = st.text_input("輸入關鍵字 (支援卡名與編號)：")
    if keyword:
        results = [c for c in prices.keys() if keyword.lower() in c.lower() or keyword.lower() in card_names.get(c, '').lower()]
        if results:
            st.success(f"找到 {len(results)} 筆結果：")
            for c_id in results:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"### {c_id} - {card_names.get(c_id, '')}")
                    st.markdown(f"#### 💸 單價： <span style='color: #4CAF50;'>{prices.get(c_id, 0)} 円</span>", unsafe_allow_html=True)
                with c2:
                    st.image(get_card_image_url(c_id), width=150)
                st.divider()
        else:
            st.warning("找不到相符的卡片！")
