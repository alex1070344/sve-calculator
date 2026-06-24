import streamlit as st
import csv
import io
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="SVE 缺卡計算機", page_icon="🃏", layout="wide")

# ==========================================
# 🌟 初始化 Google Sheets 連線 (使用 cache 避免重複登入)
@st.cache_resource
def init_gspread_client():
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"連線 Google 失敗，請確認 Secrets 設定。錯誤: {e}")
        return None

client = init_gspread_client()
if not client:
    st.stop()
    
try:
    sheet_id = "1Re2ZLcJKkFqyGe3sXaieAeB8E9U9k4PxghYbKAuXSZ4" 
    doc = client.open_by_key(sheet_id)
except Exception as e:
    st.error(f"無法開啟試算表，請確認 ID 是否正確且已分享給服務帳號！詳細錯誤：{e}")
    st.stop()

# ==========================================
# 🌟 側邊欄：多重背包切換與管理系統
worksheets = [ws.title for ws in doc.worksheets()]

with st.sidebar:
    st.title("🎒 我的背包管理")
    selected_backpack = st.selectbox("切換當前背包：", worksheets)
    
    st.divider()
    st.write("### ⚙️ 背包設定")
    
    # 新增背包
    with st.expander("➕ 建立全新背包"):
        new_bp_name = st.text_input("輸入新背包名稱：", placeholder="例如：交易用卡本")
        if st.button("🚀 建立背包"):
            if new_bp_name and new_bp_name not in worksheets:
                new_sheet = doc.add_worksheet(title=new_bp_name, rows="1000", cols="2")
                # 兼容新舊版 gspread 寫法
                try:
                    new_sheet.update(values=[["卡號", "擁有數量"]], range_name='A1')
                except TypeError:
                    new_sheet.update('A1', [["卡號", "擁有數量"]])
                st.success(f"✅ 背包【{new_bp_name}】建立成功！")
                st.rerun()
            elif new_bp_name in worksheets:
                st.warning("⚠️ 這個背包名稱已經存在囉！")
                
    # 刪除背包
    with st.expander("🗑️ 刪除當前背包"):
        st.warning(f"確定要刪除【{selected_backpack}】嗎？此動作無法復原！")
        if st.button("🚨 確認刪除"):
            if len(worksheets) <= 1:
                st.error("這是你最後一個背包了，無法刪除！")
            else:
                doc.del_worksheet(doc.worksheet(selected_backpack))
                st.success(f"已刪除背包【{selected_backpack}】！")
                st.rerun()

st.title(f"🃏 SVE 缺卡計算機 ─ 目前背包：【{selected_backpack}】")

# ==========================================
# 🌟 雲端工具：載入與儲存當前背包
current_sheet = doc.worksheet(selected_backpack)

def load_inventory_from_sheets(sheet):
    try:
        records = sheet.get_all_records()
        inv = {}
        for row in records:
            if '卡號' in row and '擁有數量' in row:
                try:
                    inv[str(row['卡號'])] = int(row['擁有數量'])
                except ValueError:
                    pass
        return inv
    except Exception as e:
        st.error(f"讀取資料失敗：{e}")
        return {}

def save_inventory_to_sheets(sheet, inv_dict):
    try:
        data = [["卡號", "擁有數量"]]
        for c_id, q in inv_dict.items():
            if q > 0:
                data.append([c_id, q])
        sheet.clear()
        
        # 兼容新舊版 gspread 寫入語法，這是導致前面「假死」的主因
        try:
            sheet.update(values=data, range_name='A1')
        except TypeError:
            sheet.update('A1', data)
        return True
    except Exception as e:
        st.error(f"❌ 同步至 Google Sheets 失敗: {e}")
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

# 2. 載入目前選定背包的庫存
my_inventory = load_inventory_from_sheets(current_sheet)

# 初始化暫存牌組
if "deck_list" not in st.session_state:
    st.session_state.deck_list = {}

# ==========================================
tab1, tab2 = st.tabs(["🧾 牌組結帳 (計算缺卡)", "🎒 我的庫存與資產"])

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
    cards_in_prefix1 = cards_in_pack1 if deck_prefix == "全部" else [c for c in cards_in_pack1 if get_prefix(c) == deck_prefix]
    # 👇 新增這行：將過濾好的清單強制按字母/數字排序！
    cards_in_prefix1 = sorted(cards_in_prefix1)
    with col_c1: deck_card = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix1, key="deck_card")
    with col_q1: deck_qty = st.number_input("4. 需要幾張？", min_value=1, max_value=50, value=1, key="deck_qty")
        
    if st.button("➕ 加入結帳牌組"):
        if deck_card != "請選擇...":
            st.session_state.deck_list[deck_card] = st.session_state.deck_list.get(deck_card, 0) + deck_qty
            st.success(f"✅ 已將 {deck_qty} 張 【{deck_card}】 加入牌組！")
            st.rerun()

    with st.expander("📝 進階：批次匯入牌組 (文字 / CSV)"):
        col_text, col_csv = st.columns(2)
        with col_text:
            st.write("#### ✍️ 文字貼上")
            deck_input = st.text_area("貼上牌組清單 (卡號與數量用空白隔開)：", height=100)
            if st.button("確認匯入文字"):
                for line in deck_input.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 2:
                        c_id = parts[0].strip()
                        try: q = int(parts[1].strip())
                        except: q = 1
                        st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                st.rerun()
                
        with col_csv:
            st.write("#### 📁 上傳 CSV 牌組檔")
            st.caption("格式：第一欄填卡號，第二欄填數量")
            deck_csv_file = st.file_uploader("選擇你的 CSV 牌組檔", type=["csv"], key="deck_csv_uploader")
            if deck_csv_file is not None and st.button("🚀 確認匯入 CSV 牌組"):
                try:
                    reader = csv.reader(io.StringIO(deck_csv_file.getvalue().decode("utf-8-sig")))
                    first_row = next(reader, None)
                    if first_row and (first_row[0].startswith("BP") or first_row[0].startswith("SD") or first_row[0].startswith("PR")):
                        if len(first_row) >= 2: st.session_state.deck_list[first_row[0].strip()] = st.session_state.deck_list.get(first_row[0].strip(), 0) + int(first_row[1].strip())
                    for row in reader:
                        if len(row) >= 2:
                            c_id = row[0].strip()
                            try: q = int(row[1].strip())
                            except: q = 1
                            st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + q
                    st.success("🎉 CSV 牌組已成功匯入！")
                    st.rerun()
                except Exception as e: st.error(f"檔案讀取失敗：{e}")

    st.divider()
    st.write("### 🛒 結帳明細")
    if st.session_state.deck_list:
        if st.button("🗑️ 清空目前牌組"): st.session_state.deck_list = {}; st.rerun()
        total_cost = 0
        receipt_list = []
        for c_id, req_qty in st.session_state.deck_list.items():
            owned_qty = my_inventory.get(c_id, 0)
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
            st.success("🎉 太神啦！這副牌組的所有卡片你都已經擁有了，不需要花半毛錢！")

        st.write("#### 調整目前牌組數量")
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
    else:
        st.info("牌組目前空空如也，請從上方查詢並加入卡片！")

# -----------------------------------------------------------
# ----- 分頁 2：背包區 (🌟 修復假死 Bug) -----
with tab2:
    st.subheader(f"📝 登記新卡片至【{selected_backpack}】")
    
    col_p2, col_r2, col_c2, col_q2 = st.columns(4)
    with col_p2: inv_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="inv_pack")
    cards_in_pack2 = all_cards if inv_pack == "全部" else [c for c in all_cards if c.startswith(inv_pack + "-")]
    prefixes2 = sorted(list(set([get_prefix(c) for c in cards_in_pack2])))
    
    with col_r2: inv_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes2, key="inv_prefix")
    cards_in_prefix2 = cards_in_pack2 if inv_prefix == "全部" else [c for c in cards_in_pack2 if get_prefix(c) == inv_prefix]

    cards_in_prefix2 = sorted(cards_in_prefix2)
    
    with col_c2: card_to_add = st.selectbox("3. 選擇卡號：", ["請選擇..."] + cards_in_prefix2, key="inv_card")
    with col_q2: qty_to_add = st.number_input("4. 擁有幾張？", min_value=0, max_value=50, value=1, key="inv_qty")
        
    if st.button("➕ 新增至雲端背包"):
        if card_to_add != "請選擇...":
            my_inventory[card_to_add] = my_inventory.get(card_to_add, 0) + qty_to_add
            # 移除了 st.rerun()，讓使用者能清楚看見成功或失敗的訊息
            if save_inventory_to_sheets(current_sheet, my_inventory):
                st.success(f"✅ 成功將 {qty_to_add} 張 【{card_to_add}】 加入！")

    st.divider()
    
    try:
        # 🌟 計算總資產價值
        total_backpack_value = sum([prices.get(c_id, 0) * q for c_id, q in my_inventory.items() if q > 0])
        
        col_title, col_value = st.columns([2, 1])
        with col_title:
            st.write("### 🎒 我的雲端庫存清單")
        with col_value:
            st.info(f"💰 **本背包總資產估值： {total_backpack_value} 円**")
        
        if my_inventory and any(v > 0 for v in my_inventory.values()):
            st.write("🔍 **過濾你的背包庫存：**")
            col_f1, col_f2 = st.columns(2)
            owned_packs = sorted(list(set([k.split('-')[0] for k, v in my_inventory.items() if '-' in k and v > 0])))
            with col_f1: filter_pack = st.selectbox("過濾卡包", ["全部"] + owned_packs)
            filtered_inv = [k for k, v in my_inventory.items() if v > 0]
            if filter_pack != "全部": filtered_inv = [k for k in filtered_inv if k.startswith(filter_pack + "-")]
                
            owned_prefixes = sorted(list(set([get_prefix(k) for k in filtered_inv])))
            with col_f2: filter_prefix = st.selectbox("過濾編號前綴", ["全部"] + owned_prefixes)
            if filter_prefix != "全部": filtered_inv = [k for k in filtered_inv if get_prefix(k) == filter_prefix]

            if filtered_inv:
                st.markdown("---")
                h1, h2, h3, h_price, h_minus, h_qty, h_plus = st.columns([1.5, 1.5, 2.5, 2, 1, 1, 1])
                h1.markdown("**📦 卡包**")
                h2.markdown("**✨ 前綴**")
                h3.markdown("**🏷️ 卡號**")
                h_price.markdown("**💸 單價 (小計)**")
                h_qty.markdown("**數量**")
                st.markdown("---")
                
                filtered_inv.sort()
                for c_id in filtered_inv:
                    qty = my_inventory[c_id]
                    unit_price = prices.get(c_id, 0)
                    subtotal = unit_price * qty
                    
                    c1, c2, c3, c_price, c_minus, c_qty, c_plus = st.columns([1.5, 1.5, 2.5, 2, 1, 1, 1])
                    c1.write(c_id.split('-')[0] if '-' in c_id else "其他")
                    c2.write(get_prefix(c_id))
                    c3.write(c_id)
                    c_price.markdown(f"<span style='color: #4CAF50;'>{unit_price} 円</span><br><small style='color: gray;'>(計: {subtotal})</small>", unsafe_allow_html=True)
                    
                    if c_minus.button("➖", key=f"inv_minus_{c_id}"):
                        my_inventory[c_id] -= 1
                        if my_inventory[c_id] < 0: my_inventory[c_id] = 0
                        save_inventory_to_sheets(current_sheet, my_inventory)
                        st.rerun()
                    c_qty.markdown(f"### {qty}")
                    if c_plus.button("➕", key=f"inv_plus_{c_id}"):
                        my_inventory[c_id] += 1
                        save_inventory_to_sheets(current_sheet, my_inventory)
                        st.rerun()
                st.markdown("---")
            else: st.warning("沒有符合過濾條件的卡片。")
        else:
            st.info("這個背包空空如也，快去上方登記吧！")
            
    except Exception as e:
        st.error(f"渲染背包資料時發生錯誤：{e}")

    # ==========================================
    # 備份與還原區塊
    st.write("")
    with st.expander(f"⚙️ 進階功能：匯出與匯入【{selected_backpack}】"):
        col_dl, col_ul = st.columns(2)
        with col_dl:
            st.write("#### ⬇️ 下載備份檔")
            if my_inventory:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["卡號", "擁有數量"])
                for c_id, q in my_inventory.items():
                    if q > 0: writer.writerow([c_id, q])
                st.download_button(label="📥 下載庫存 CSV 備份", data=output.getvalue(), file_name=f"{selected_backpack}_inventory.csv", mime="text/csv")
            else: st.warning("目前背包無資料。")
                
        with col_ul:
            st.write("#### ⬆️ 上傳還原檔至雲端")
            uploaded_file = st.file_uploader("選擇你的 CSV 備份檔", type=["csv"], key="inventory_csv_uploader")
            if uploaded_file is not None:
                import_mode = st.radio("請選擇匯入模式：", ("🔄 取代現有背包", "➕ 增加至現有背包"))
                if st.button("🚀 執行上傳並同步"):
                    try:
                        reader = csv.reader(io.StringIO(uploaded_file.getvalue().decode("utf-8-sig")))
                        next(reader, None)
                        if import_mode.startswith("🔄"): my_inventory.clear()
                        for row in reader:
                            if len(row) >= 2: my_inventory[row[0]] = my_inventory.get(row[0], 0) + int(row[1]) if not import_mode.startswith("🔄") else int(row[1])
                        save_inventory_to_sheets(current_sheet, my_inventory)
                        st.success("🎉 雲端背包資料同步成功！")
                        st.rerun()
                    except Exception as e: st.error(f"檔案格式錯誤：{e}")
