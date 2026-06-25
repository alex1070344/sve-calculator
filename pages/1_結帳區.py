import streamlit as st
import csv
import io
import utils

# 從 session_state 取出共用變數
prices = st.session_state.prices
card_names = st.session_state.card_names
name_to_ids = st.session_state.name_to_ids
all_cards = st.session_state.all_cards
packs = st.session_state.packs

st.title("🧾 牌組結帳 (計算缺卡)")
st.subheader("🔍 選擇卡片加入結帳牌組")

col_p1, col_r1, col_c1, col_q1 = st.columns(4)
with col_p1: deck_pack = st.selectbox("1. 選擇卡包：", ["全部"] + packs, key="deck_pack")
cards_in_pack1 = all_cards if deck_pack == "全部" else [c for c in all_cards if c.startswith(deck_pack + "-")]
prefixes1 = sorted(list(set([utils.get_prefix(c) for c in cards_in_pack1])))

with col_r1: deck_prefix = st.selectbox("2. 選擇編號前綴：", ["全部"] + prefixes1, key="deck_prefix")
cards_in_prefix1 = sorted(cards_in_pack1 if deck_prefix == "全部" else [c for c in cards_in_pack1 if utils.get_prefix(c) == deck_prefix])

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
            
    with st.expander("📝 進階：批次匯入與 📸 AI 圖片上傳辨識"):
        auto_cheapest = st.checkbox("💸 抄牌或掃描時自動將卡片替換為「同名最低價」版本", value=True, key="chk_cheap_deck")
        st.divider()
        
        st.write("#### 📸 AI 圖片上傳辨識")
        gemini_key_deck = st.text_input("輸入 Gemini API Key 來啟用 AI 掃描：", type="password", key="gemini_key_deck")
        st.caption("免費的 Gemini API Key 可於 [Google AI Studio](https://aistudio.google.com/) 取得。")
        
        active_img_deck = st.file_uploader("📂 上傳卡片圖片 (支援單圖多卡)", type=["jpg", "jpeg", "png"], key="up_deck")
        
        if active_img_deck:
            if not gemini_key_deck:
                st.warning("⚠️ 請先在上方輸入 Gemini API Key 才能執行 AI 辨識。")
            else:
                if st.button("🔍 執行 AI 辨識並加入牌組", type="primary", key="btn_scan_deck"):
                    with st.spinner("AI 正在火力全開解析多張卡圖中..."):
                        success, c_ids, raw_text = utils.scan_card_image(active_img_deck, gemini_key_deck)
                        if success:
                            valid_ids = []
                            for c_id in c_ids:
                                if auto_cheapest: 
                                    c_id = utils.get_cheapest_version(c_id, card_names, name_to_ids, prices)
                                if c_id in prices:
                                    st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + 1
                                    valid_ids.append(c_id)
                            
                            if valid_ids:
                                st.session_state.last_scanned_deck = valid_ids
                                st.rerun()
                            else:
                                st.warning("雖然掃描到了卡號，但比對後發現都不在我們的資料庫中。")
                        else:
                            st.error(f"辨識失敗，AI 未能找到任何卡號。")
                            
        if st.session_state.last_scanned_deck:
            st.markdown("---")
            st.markdown("### 👁️ 上次掃描結果視覺確認 (請核對實體卡片)")
            st.caption("以下為 AI 剛剛自動幫您加入結帳明細的卡片。如果發現有錯或漏掉，可直接在下方明細調整張數。")
            if st.button("🧹 關閉/完成確認", key="clear_preview_deck"):
                st.session_state.last_scanned_deck = []
                st.rerun()
                
            cols_deck = st.columns(4)
            for idx, c_id in enumerate(st.session_state.last_scanned_deck):
                with cols_deck[idx % 4]:
                    st.image(utils.get_card_image_url(c_id, st.session_state.card_images), width=120)
                    st.caption(f"**{c_id}**\n{card_names.get(c_id, '未知')}")
                            
        st.divider()
        
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
                            if auto_cheapest: c_id = utils.get_cheapest_version(c_id, card_names, name_to_ids, prices)
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
                            if auto_cheapest: c_id = utils.get_cheapest_version(c_id, card_names, name_to_ids, prices)
                            st.session_state.deck_list[c_id] = st.session_state.deck_list.get(c_id, 0) + int(first_row[1].strip())
                    for row in reader:
                        if len(row) >= 2:
                            c_id = row[0].strip()
                            try: q = int(row[1].strip())
                            except: q = 1
                            if c_id in prices: 
                                if auto_cheapest: c_id = utils.get_cheapest_version(c_id, card_names, name_to_ids, prices)
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
                        success, msg = utils.fetch_decklog(decklog_code, auto_cheapest, card_names, name_to_ids, prices)
                        if success: st.success(msg); st.rerun()
                        else: st.error(msg)

with col_img1:
    if selected_option1 != "請選擇...":
        st.image(utils.get_card_image_url(selected_option1.split(" - ")[0], st.session_state.card_images), width=150)

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
