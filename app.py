import streamlit as st
import utils

# ==========================================
# 🌟 初始化：網頁基本設定
st.set_page_config(page_title="SVE 缺卡計算機", page_icon="🃏", layout="wide")

# 🌟 定義 CSS 來處理未擁有卡片的暗化效果 (放在主檔案確保全域套用)
st.markdown("""
<style>
.card-unowned {
    filter: grayscale(80%) brightness(0.6);
    transition: all 0.3s ease;
}
.card-unowned:hover {
    filter: grayscale(40%) brightness(0.8);
}
.card-owned {
    box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
    border-radius: 8px;
    transition: all 0.3s ease;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌟 初始化：網頁記憶體 (Session State)
if "deck_list" not in st.session_state: st.session_state.deck_list = {}
if "my_inventory" not in st.session_state: st.session_state.my_inventory = {}
if "current_bp_name" not in st.session_state: st.session_state.current_bp_name = ""
if "unsaved_changes" not in st.session_state: st.session_state.unsaved_changes = False
if "last_scanned_deck" not in st.session_state: st.session_state.last_scanned_deck = []
if "last_scanned_inv" not in st.session_state: st.session_state.last_scanned_inv = []
if "master_data_cache" not in st.session_state: st.session_state.master_data_cache = None
if "gallery_page" not in st.session_state: st.session_state.gallery_page = 1

# ==========================================
# 🌟 全域資料載入 (從 utils 呼叫)
client = utils.init_gspread_client()
if not client: st.stop()

try:
    # ⚠️⚠️⚠️ 記得換成你的試算表 ID ⚠️⚠️⚠️
    sheet_id = "13iEttGIfSgEwXp69Lq1zRkG0y0S9s_4l7tV678A7lVw" 
    st.session_state.doc = client.open_by_key(sheet_id)
except Exception as e:
    st.error(f"無法開啟試算表：{e}")
    st.stop()

prices, card_images, card_names, name_to_ids, all_cards, packs = utils.load_card_data()

# 將這些常用變數存入 session_state，讓其他頁面可以取用
st.session_state.prices = prices
st.session_state.card_images = card_images
st.session_state.card_names = card_names
st.session_state.name_to_ids = name_to_ids
st.session_state.all_cards = all_cards
st.session_state.packs = packs

# ==========================================
# 🌟 側邊欄：背包管理 (共用元件)
worksheets = [ws.title for ws in st.session_state.doc.worksheets()]
with st.sidebar:
    st.title("🎒 背包管理")
    selected_backpack = st.selectbox("切換背包：", worksheets)
    
    st.divider()
    with st.expander("➕ 建立全新背包"):
        new_bp_name = st.text_input("輸入新背包名稱：")
        if st.button("🚀 建立背包"):
            if new_bp_name and new_bp_name not in worksheets:
                new_sheet = st.session_state.doc.add_worksheet(title=new_bp_name, rows="1000", cols="2")
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
                st.session_state.doc.del_worksheet(st.session_state.doc.worksheet(selected_backpack))
                st.success("已成功刪除！")
                st.rerun()

st.session_state.current_sheet = st.session_state.doc.worksheet(selected_backpack)
st.session_state.selected_backpack = selected_backpack

# 切換背包時的邏輯處理
if st.session_state.current_bp_name != selected_backpack:
    try:
        records = st.session_state.current_sheet.get_all_records()
        st.session_state.my_inventory = {str(row['卡號']): int(row['擁有數量']) for row in records if '卡號' in row}
        st.session_state.current_bp_name = selected_backpack
        st.session_state.unsaved_changes = False
        st.session_state.gallery_page = 1 # 切換背包時重置圖鑑頁碼
    except Exception as e:
        st.error(f"讀取雲端資料失敗：{e}")

# ==========================================
# 🌟 使用 st.navigation 設定多頁面導航
# 這裡定義的頁面名稱會顯示在側邊欄上方

pg = st.navigation({
    "核心功能": [
        st.Page("pages/1_結帳區.py", title="🧾 牌組結帳", icon="🧾"),
        st.Page("pages/2_背包區.py", title="🎒 我的庫存", icon="🎒"),
        st.Page("pages/3_單卡查詢.py", title="💰 價格與查詢", icon="💰"),
    ],
    "進階管理": [
        st.Page("pages/4_總覽與圖鑑.py", title="📊 總覽與 📖 全圖鑑", icon="📖"),
    ]
})

# 執行導航 (載入使用者選擇的頁面)
pg.run()
