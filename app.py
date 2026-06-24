import streamlit as st
import csv
import io
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="SVE 缺卡計算機", page_icon="🃏", layout="wide")
st.title("🃏 Shadowverse Evolve 缺卡計算機 (雲端連線版)")

# ==========================================
# 🌟 初始化：讓網頁記住你正在組建的牌組
if "deck_list" not in st.session_state:
    st.session_state.deck_list = {}

# 🌟 雲端工具 1：連線並讀取 Google Sheets 庫存
def load_inventory_from_sheets():
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open("SVE_Inventory").sheet1
        records = sheet.get_all_records()
        
        inv = {}
        for row in records:
            if '卡號' in row and '擁有數量' in row:
                inv[str(row['卡號'])] = int(row['擁有數量'])
        return inv, sheet
    except Exception as e:
        st.error(f"❌ 連線 Google Sheets 失敗，請確認 Secrets 設定與共用權限。錯誤訊息: {e}")
        return {}, None

# 🌟 雲端工具 2：將記憶體中的庫存同步覆寫至 Google Sheets
def save_inventory_to_sheets(sheet, inv_dict):
    if sheet is None:
        st.error("⚠️ 無法儲存，試算表連線未建立。")
        return
    try:
        data = [["卡號", "擁有數量"]]
        for c_id, q in inv_dict.items():
            if q > 0:
                data.append([c_id, q])
        
        sheet.clear()
        sheet.update('A1', data)
    except Exception as e:
        st.error(f"❌ 同步至 Google Sheets 失敗: {e}")

# 🌟 小工具 3：萃取「編號前綴」
def get_prefix(card_id):
    if "-" not in card_id: return "其他"
    suffix = card_id.split("-")[1]
    prefix = ""
    for char in suffix:
        if char.isalpha(): prefix += char
        else: break
    return prefix if prefix else "一般編號"
# ==========================================

# 1. 讀取價格表 (本機 CSV)
prices = {}
try:
    with open("cards_price.csv", "r", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            prices[row[0]] = int(row[1])
except FileNotFoundError:
    st.error("找不到價格表！請確保 GitHub 專案內有執行 crawler.py 產生的 cards_price.csv。")

# 2. 從 Google Sheets 載入最新的個人庫存
my_inventory, gsheet = load_inventory_from_sheets()

# ==========================================
tab1, tab2 = st.tabs(["🧾 牌組結帳 (計算缺卡)", "🎒 我的背包 (管理庫存)"])

# -----------------------------------------------------------
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
            st.success(f"✅ 已將 {deck_qty} 張 【{deck_card}】 加入牌組！")
            st.rerun()

    # 🌟 結帳區大改版：加入 CSV 牌組匯入功能
    with st.expander("📝 進階：批次匯入牌組 (文字 / CSV)"):
        col_text, col_csv = st.columns(2)
        
        # 左側：文字貼上
        with col_text:
            st.write("#### ✍️ 文字貼上")
            deck_input = st.text_area("貼上牌組清單 (卡號與數量用空白隔開)：", height=100)
            if st.button("確認匯入文字"):
                lines = deck_input.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        c_id = parts[0].strip()
                        try: q = int(parts[1].strip())
                        except: q = 1
                        st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                st.rerun()
                
        # 右側：CSV 上傳
        with col_csv:
            st.write("#### 📁 上傳 CSV 牌組檔")
            st.caption("格式：第一欄填卡號，第二欄填數量")
            deck_csv_file = st.file_uploader("選擇你的 CSV 牌組檔", type=["csv"], key="deck_csv_uploader")
            
            if deck_csv_file is not None:
                if st.button("🚀 確認匯入 CSV 牌組"):
                    try:
                        stringio = io.StringIO(deck_csv_file.getvalue().decode("utf-8-sig"))
                        reader = csv.reader(stringio)
                        # 假設第一行可能是標題 (如 "卡號", "數量")，先讀取但不強迫跳過，以防沒有標題
                        first_row = next(reader, None)
                        if first_row and not (first_row[0].startswith("BP") or first_row[0].startswith("SD") or first_row[0].startswith("PR")):
                            # 如果第一行的開頭不像卡號，就當作它是標題跳過
                            pass
                        else:
                            # 如果是卡號，就直接加進去
                            if len(first_row) >= 2:
                                st.session_state.deck_list[first_row[0].strip()] = st.session_state.deck_list.get(first_row[0].strip(), 0) + int(first_row[1].strip())
                        
                        # 繼續讀取剩下的行數
                        for row in reader:
                            if len(row) >= 2:
                                c_id = row[0].strip()
                                try: q = int(row[1].strip())
                                except: q = 1
                                st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                                
                        st.success("🎉 CSV 牌組已成功匯入！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"檔案讀取失敗，請確認格式。詳細錯誤：{e}")

    st.divider()
    
    st.write("### 🛒 結帳明細")
    if st.session_state.deck_list:
        if st.button("🗑️ 清空目前牌組"):
            st.session_state.deck_list = {}
            st.rerun()
            
        total_cost = 0
        receipt_list = []
        
        for c_id, req_qty in st.session_state.deck_list.items():
            owned_qty = my_inventory.get(c_id, 0)
            missing_qty = max(0, req_qty - owned_qty)
            price = prices.get(c_id, 0)
            
            if missing_qty > 0:
                cost = price * missing_qty
                total_cost += cost
                receipt_list.append({
                    "卡號": c_id,
                    "需要": req_qty,
                    "已有": owned_qty,
                    "尚缺": missing_qty,
                    "單價 (円)": price,
                    "小計 (円)": cost
                })
                
        if receipt_list:
            st.dataframe(receipt_list, use_container_width=True)
            st.error(f"### 💸 扣除已有卡片後，補齊還需花費： {total_cost} 円")
        else:
            st.success("🎉 太神啦！這副牌組的所有卡片你都已經擁有了，不需要花半毛錢！")

        st.write("#### 調整目前牌組數量")
        for c_id, req_qty in list(st.session_state.deck_list.items()):
            c1, c2, c3, c_minus, c_q, c_plus = st.columns([1.5, 1.5, 3, 1, 1, 1])
            c1.write(c_id.split('-')[0] if '-' in c_id else "其他")
            c2.write(get_prefix(c_id))
            c3.write(c_id)
            
            if c_minus.button("➖", key=f"d_minus_{c_id}"):
                st.session_state.deck_list[c_id] -= 1
                if st.session_state.deck_list[c_id] <= 0:
                    del st.session_state.deck_list[c_id]
                st.rerun()
                
            c_q.markdown(f"### {req_qty}")
            
            if c_plus.button("➕", key=f"d_plus_{c_id}"):
                st.session_state.deck_list[c_id] += 1
                st.rerun()
    else:
        st.info("牌組目前空空如也，請從上方查詢並加入卡片！")

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
        
    if st.button("➕ 新增至雲端背包"):
        if card_to_add != "請選擇...":
            current_qty = my_inventory.get(card_to_add, 0)
            my_inventory[card_to_add] = current_qty + qty_to_add
            save_inventory_to_sheets(gsheet, my_inventory)
            st.success(f"✅ 成功將 {qty_to_add} 張 【{card_to_add}】 加進雲端背包！")
            st.rerun()

    st.divider()
    
    st.write("### 🎒 我的雲端庫存清單")
    
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
                    save_inventory_to_sheets(gsheet, my_inventory)
                    st.rerun()
                    
                c_qty.markdown(f"### {qty}")
                
                if c_plus.button("➕", key=f"inv_plus_{c_id}"):
                    my_inventory[c_id] += 1
                    save_inventory_to_sheets(gsheet, my_inventory)
                    st.rerun()
            st.markdown("---")
        else:
            st.warning("沒有符合過濾條件的卡片。")
    else:
        st.info("雲端背包空空如也，快去上方登記吧！")

    # ==========================================
    # 備份與還原區塊 (與雲端資料庫連動)
    st.write("")
    with st.expander("⚙️ 進階功能：匯出與匯入背包資料"):
        col_dl, col_ul = st.columns(2)
        
        with col_dl:
            st.write("#### ⬇️ 下載備份檔")
            if my_inventory:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["卡號", "擁有數量"])
                for c_id, q in my_inventory.items():
                    if q > 0: writer.writerow([c_id, q])
                csv_data = output.getvalue()
                
                st.download_button(label="📥 點我下載庫存 CSV 備份", data=csv_data, file_name="my_sve_inventory.csv", mime="text/csv")
            else:
                st.warning("目前背包無資料，無法下載。")
                
        with col_ul:
            st.write("#### ⬆️ 上傳還原檔至雲端")
            uploaded_file = st.file_uploader("選擇你的 CSV 備份檔", type=["csv"], key="inventory_csv_uploader")
            
            if uploaded_file is not None:
                import_mode = st.radio(
                    "請選擇匯入模式：",
                    ("🔄 取代現有背包 (清除雲端原本所有資料)", "➕ 增加至現有背包 (將數量疊加計算)")
                )
                
                if st.button("🚀 執行上傳並同步至雲端"):
                    try:
                        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8-sig"))
                        reader = csv.reader(stringio)
                        next(reader, None) # 跳過標題列
                        
                        if import_mode.startswith("🔄"):
                            my_inventory.clear()
                            for row in reader:
                                if len(row) >= 2:
                                    my_inventory[row[0]] = int(row[1])
                            st.success("🎉 雲端背包資料已成功覆蓋！")
                        else:
                            for row in reader:
                                if len(row) >= 2:
                                    c_id = row[0]
                                    qty = int(row[1])
                                    my_inventory[c_id] = my_inventory.get(c_id, 0) + qty
                            st.success("🎉 新卡片數量已成功疊加至雲端背包！")
                            
                        save_inventory_to_sheets(gsheet, my_inventory)
                        st.rerun()
                    except Exception as e:
                        st.error(f"檔案格式錯誤，無法還原。詳細錯誤：{e}")
