import streamlit as st
import utils

prices = st.session_state.prices
card_names = st.session_state.card_names
all_cards = st.session_state.all_cards
packs = st.session_state.packs
selected_backpack = st.session_state.selected_backpack

st.title("💰 單卡價格與卡圖查詢")
st.subheader("🔍 選擇卡片或搜尋關鍵字")

col_p3, col_r3, col_c3 = st.columns(3)
with col_p3: search_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="search_pack")
cards_in_pack3 = all_cards if search_pack == "全部" else [c for c in all_cards if c.startswith(search_pack + "-")]
prefixes3 = sorted(list(set([utils.get_prefix(c) for c in cards_in_pack3])))

with col_r3: search_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes3, key="search_prefix")
cards_in_prefix3 = sorted(cards_in_pack3 if search_prefix == "全部" else [c for c in cards_in_pack3 if utils.get_prefix(c) == search_prefix])

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
    with col_img_d: st.image(utils.get_card_image_url(c_id_dropdown, st.session_state.card_images), width=180)
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
            with col_img3: st.image(utils.get_card_image_url(c_id, st.session_state.card_images), width=180)
            st.divider()
