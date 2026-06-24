import streamlit as st
import csv
import os
import io

st.set_page_config(page_title="SVE 缺卡計算機", page_icon="🃏", layout="wide")
st.title("🃏 Shadowverse Evolve 缺卡計算機")

# ==========================================
# 🌟 初始化：記住組建中的牌組
if "deck_list" not in st.session_state:
    st.session_state.deck_list = {}

# 🌟 小工具 1：存檔
inventory_file = "my_inventory.csv"
def save_inventory():
    with open(inventory_file, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["卡號", "擁有數量"])
        for c_id, q in my_inventory.items():
            if q > 0: writer.writerow([c_id, q])

# 🌟 小工具 2：萃取編號前綴
def get_prefix(card_id):
    if "-" not in card_id: return "其他"
    suffix = card_id.split("-")[1]
    prefix = ""
    for char in suffix:
        if char.isalpha(): prefix += char
        else: break
    return prefix if prefix else "一般編號"
# ==========================================

# 1. 讀取價格表
prices = {}
try:
    with open("cards_price.csv", "r", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            prices[row[0]] = int(row[1])
except FileNotFoundError:
    st.error("找不到價格表！請先執行 crawler.py。")

# 2. 讀取個人庫存
my_inventory = {}
if os.path.exists(inventory_file):
    with open(inventory_file, "r", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if len(row) == 2: my_inventory[row[0]] = int(row[1])

# ==========================================
tab1, tab2 = st.tabs(["🧾 牌組結帳 (計算缺卡)", "🎒 我的背包 (管理庫存)"])

# ----- 分頁 1：結帳區 -----
with tab1:
    st.subheader("🔍 查詢並加入結帳牌組")
    all_cards = list(prices.keys())
    packs = sorted(list(set([card.split('-')[0] for card in all_cards if '-' in card])))
    
    col_p1, col_r1, col_c1, col_q1 = st.columns(4)
    with col_p1:
        deck_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="deck_pack")
    
    cards_in_pack1 = all_cards if deck_pack == "全部" else [c for c in all_cards if c.startswith(deck_pack + "-")]
    prefixes1 = sorted(list(set([get_prefix(c) for c in cards_in_pack1])))
    
    with col_r1:
        deck_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes1, key="deck_prefix")
    cards_in_prefix1 = cards_in_pack1 if deck_prefix == "全部" else [c for c in cards_in_pack1 if get_prefix(c) == deck_prefix]
    
    with col_c1:
        deck_card = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix1, key="deck_card")
    with col_q1:
        deck_qty = st.number_input("4. 需要幾張？", min_value=1, max_value=50, value=1, key="deck_qty")
        
    if st.button("➕ 加入結帳牌組"):
        if deck_card != "請選擇...":
            st.session_state.deck_list[deck_card] = st.session_state.deck_list.get(deck_card, 0) + deck_qty
            st.rerun()

    st.divider()
    st.write("### 🛒 結帳明細")
    if st.session_state.deck_list:
        if st.button("🗑️ 清空牌組"): st.session_state.deck_list = {}; st.rerun()
            
        receipt_list = []
        for c_id, req_qty in st.session_state.deck_list.items():
            owned = my_inventory.get(c_id, 0)
            price = prices.get(c_id, 0)
            receipt_list.append({"卡號": c_id, "需要": req_qty, "已有": owned, "尚缺": max(0, req_qty - owned), "單價": price, "小計": price * max(0, req_qty - owned)})
        st.dataframe(receipt_list, use_container_width=True)
    else: st.info("牌組目前空空如也！")

# -----------------------------------------------------------
# ----- 分頁 2：背包區 -----
with tab2:
    st.subheader("📝 登記新抽到的卡片")
    
    col_p2, col_r2, col_c2, col_q2 = st.columns(4)
    with col_p2:
        inv_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="inv_pack")
        
    cards_in_pack2 = all_cards if inv_pack == "全部" else [c for c in all_cards if c.startswith(inv_pack + "-")]
    prefixes2 = sorted(list(set([get_prefix(c) for c in cards_in_pack2])))
    
    with col_r2:
        inv_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes2, key="inv_prefix")
        
    cards_in_prefix2 = cards_in_pack2 if inv_prefix == "全部" else [c for c in cards_in_pack2 if get_prefix(c) == inv_prefix]
    
    with col_c2:
        card_to_add = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix2, key="inv_card")
    with col_q2:
        qty_to_add = st.number_input("4. 擁有幾張？", min_value=0, max_value=50, value=1, key="inv_qty")
        
    if st.button("➕ 新增至背包"):
        if card_to_add != "請選擇...":
            current_qty = my_inventory.get(card_to_add, 0)
            my_inventory[card_to_add] = current_qty + qty_to_add
            save_inventory()
            st.success(f"✅ 成功將 {qty_to_add} 張 【{card_to_add}】 加入背包！")
            st.rerun()

    st.divider()
    
    st.write("### 🎒 我的庫存清單")
    
    if my_inventory and any(v > 0 for v in my_inventory.values()):
        st.write("🔍 **過濾你的背包庫存：**")
        col_f1, col_f2 = st.columns(2)
        
        owned_packs = sorted(list(set([k.split('-')[0] for k, v in my_inventory.items() if '-' in k and v > 0])))
        with col_f1:
            filter_pack = st.selectbox("過濾卡包", ["全部"] + owned_packs)
            
        filtered_inv = [k for k, v in my_inventory.items() if v > 0]
        if filter_pack != "全部":
            filtered_inv = [k for k in filtered_inv if k.startswith(filter_pack + "-")]
            
        owned_prefixes = sorted(list(set([get_prefix(k) for k in filtered_inv])))
        with col_f2:
            filter_prefix = st.selectbox("過濾編號前綴", ["全部"] + owned_prefixes)
            
        if filter_prefix != "全部":
            filtered_inv = [k for k in filtered_inv if get_prefix(k) == filter_prefix]

        if filtered_inv:
            st.markdown("---")
            h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1.5, 3, 1, 1, 1])
            h1.markdown("**📦 卡包**")
            h2.markdown("**✨ 編號前綴**")
            h3.markdown("**🏷️ 卡號**")
            h5.markdown("**擁有數量**")
            st.markdown("---")
            
            filtered_inv.sort()
            
            for c_id in filtered_inv:
                qty = my_inventory[c_id]
                c1, c2, c3, c_minus, c_qty, c_plus = st.columns([1.5, 1.5, 3, 1, 1, 1])
                c1.write(c_id.split('-')[0] if '-' in c_id else "其他")
                c2.write(get_prefix(c_id))
                c3.write(c_id)
                
                if c_minus.button("➖", key=f"inv_minus_{c_id}"):
                    my_inventory[c_id] -= 1
                    if my_inventory[c_id] < 0: my_inventory[c_id] = 0
                    save_inventory()
                    st.rerun()
                    
                c_qty.markdown(f"### {qty}")
                
                if c_plus.button("➕", key=f"inv_plus_{c_id}"):
                    my_inventory[c_id] += 1
                    save_inventory()
                    st.rerun()
            st.markdown("---")
        else:
            st.warning("沒有符合過濾條件的卡片。")
    else:
        st.info("背包空空如也，快去上方登記吧！")

    # ==========================================
    # 🌟 升級版：備份與還原區塊 (加入取代/合併選項)
    st.write("")
    with st.expander("⚙️ 進階功能：匯出與匯入背包資料"):
        col_dl, col_ul = st.columns(2)
        
        with col_dl:
            st.write("#### ⬇️ 下載備份檔")
            if os.path.exists(inventory_file):
                with open(inventory_file, "r", encoding="utf-8-sig") as file:
                    csv_data = file.read()
                st.download_button(label="📥 點我下載 my_inventory.csv", data=csv_data, file_name="my_sve_inventory.csv", mime="text/csv")
            else:
                st.warning("目前還沒有建立背包檔案。")
                
        with col_ul:
            st.write("#### ⬆️ 上傳還原檔")
            uploaded_file = st.file_uploader("選擇你的 CSV 備份檔", type=["csv"])
            
            if uploaded_file is not None:
                # 新增 UI 讓使用者選擇上傳模式
                import_mode = st.radio(
                    "請選擇匯入模式：",
                    ("🔄 取代現有背包 (清除原本所有資料)", "➕ 增加至現有背包 (將數量疊加計算)")
                )
                
                if st.button("🚀 執行上傳"):
                    try:
                        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8-sig"))
                        reader = csv.reader(stringio)
                        next(reader, None) # 跳過標題列
                        
                        if import_mode.startswith("🔄"):
                            # 模式一：取代 (先清空)
                            my_inventory.clear()
                            for row in reader:
                                if len(row) >= 2:
                                    my_inventory[row[0]] = int(row[1])
                            st.success("🎉 背包資料已成功覆蓋！")
                        else:
                            # 模式二：增加 (數量相加)
                            for row in reader:
                                if len(row) >= 2:
                                    c_id = row[0]
                                    qty = int(row[1])
                                    my_inventory[c_id] = my_inventory.get(c_id, 0) + qty
                            st.success("🎉 新卡片數量已成功疊加至現有背包！")
                            
                        save_inventory() 
                        st.rerun()
                    except Exception as e:
                        st.error(f"檔案格式錯誤，無法還原。詳細錯誤：{e}")