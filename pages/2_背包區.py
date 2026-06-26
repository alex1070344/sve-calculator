import streamlit as st
import csv
import io
import utils

prices = st.session_state.prices
card_names = st.session_state.card_names
all_cards = st.session_state.all_cards
packs = st.session_state.packs
selected_backpack = st.session_state.selected_backpack

st.title(f"🎒 我的庫存與資產 ({selected_backpack})")

if st.session_state.unsaved_changes:
    st.warning("⚠️ 你的背包目前有【尚未儲存】的變更！離開前請記得存檔。")
    if st.button("💾 將變更儲存至 Google 雲端", type="primary", use_container_width=True):
        if utils.save_inventory_to_sheets(st.session_state.current_sheet):
            st.success("🎉 雲端儲存成功！")
            st.rerun()
            
st.subheader("📝 登記新卡片")
col_p2, col_r2, col_c2, col_q2 = st.columns(4)
with col_p2: inv_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="inv_pack")
cards_in_pack2 = all_cards if inv_pack == "全部" else [c for c in all_cards if c.startswith(inv_pack + "-")]
prefixes2 = sorted(list(set([utils.get_prefix(c) for c in cards_in_pack2])))

with col_r2: inv_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes2, key="inv_prefix")
cards_in_prefix2 = sorted(cards_in_pack2 if inv_prefix == "全部" else [c for c in cards_in_pack2 if utils.get_prefix(c) == inv_prefix])

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
            
    with st.expander("📸 AI 智慧圖片掃描入庫 (上傳圖片)"):
        st.write("上傳卡圖照片，讓 AI 自動幫你找出卡號並登記入庫！")
        gemini_key_inv = st.text_input("輸入 Gemini API Key：", type="password", key="gemini_key_inv")
        
        active_img_inv = st.file_uploader("📂 上傳圖片 (支援單圖多卡)", type=["jpg", "jpeg", "png"], key="up_inv")
        
        if active_img_inv:
            if not gemini_key_inv:
                st.warning("⚠️ 請先輸入 Gemini API Key 才能執行 AI 辨識。")
            else:
                if st.button("🔍 執行 AI 辨識並加入背包", type="primary", key="btn_scan_inv"):
                    with st.spinner("AI 正在精準定位多張卡圖並登記入庫..."):
                        success, c_ids, raw_text = utils.scan_card_image(active_img_inv, gemini_key_inv)
                        if success:
                            valid_ids = []
                            for c_id in c_ids:
                                if c_id in prices:
                                    st.session_state.my_inventory[c_id] = st.session_state.my_inventory.get(c_id, 0) + 1
                                    valid_ids.append(c_id)
                            
                            if valid_ids:
                                st.session_state.last_scanned_inv = valid_ids
                                st.session_state.unsaved_changes = True
                                st.rerun()
                            else:
                                st.warning("辨識出的卡號皆不在我們的價格資料庫中。")
                        else:
                            st.error(f"辨識失敗，AI 看到的內容是：{raw_text}")
                            
    if st.session_state.last_scanned_inv:
        st.markdown("---")
        st.markdown("### 👁️ 上次掃描結果視覺確認 (請核對實體卡片)")
        st.caption("以下卡片已成功送入臨時背包。請確認卡圖與實體卡是否一致，沒問題請點選上方『儲存至雲端』。")
        if st.button("🧹 關閉/完成確認", key="clear_preview_inv"):
            st.session_state.last_scanned_inv = []
            st.rerun()
            
        cols_inv = st.columns(4)
        for idx, c_id in enumerate(st.session_state.last_scanned_inv):
            with cols_inv[idx % 4]:
                st.image(utils.get_card_image_url(c_id, st.session_state.card_images), width=120)
                st.caption(f"**{c_id}**\n{card_names.get(c_id, '未知')}")

with col_img2:
    if selected_option2 != "請選擇...":
        st.image(utils.get_card_image_url(selected_option2.split(" - ")[0], st.session_state.card_images), width=150)

st.divider()
total_backpack_value = sum([prices.get(c_id, 0) * q for c_id, q in st.session_state.my_inventory.items() if q > 0])
col_title, col_value = st.columns([2, 1])
with col_title: st.write("### 🎒 我的庫存清單")
with col_value: st.info(f"💰 **總資產估值： {total_backpack_value} 円**")

with st.expander(f"⚙️ 進階功能：匯出與匯入【{selected_backpack}】"):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["卡號", "擁有數量"])
    for c_id, q in st.session_state.my_inventory.items():
        if q > 0: writer.writerow([c_id, q])
    st.download_button(label="📥 下載庫存 CSV 備份", data=output.getvalue(), file_name=f"{selected_backpack}_inventory.csv", mime="text/csv")

if st.session_state.my_inventory and any(v > 0 for v in st.session_state.my_inventory.values()):
    col_f1, col_f2 = st.columns(2)
    owned_packs = sorted(list(set([k.split('-')[0] for k, v in st.session_state.my_inventory.items() if '-' in k and v > 0])))
    with col_f1: filter_pack = st.selectbox("過濾卡包", ["全部"] + owned_packs)
    filtered_inv = [k for k, v in st.session_state.my_inventory.items() if v > 0]
    if filter_pack != "全部": filtered_inv = [k for k in filtered_inv if k.startswith(filter_pack + "-")]
        
    owned_prefixes = sorted(list(set([utils.get_prefix(k) for k in filtered_inv])))
    with col_f2: filter_prefix = st.selectbox("過濾前綴", ["全部"] + owned_prefixes)
    if filter_prefix != "全部": filtered_inv = [k for k in filtered_inv if utils.get_prefix(k) == filter_prefix]

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


