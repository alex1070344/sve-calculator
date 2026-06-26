import streamlit as st
import pandas as pd
import math
import utils

prices = st.session_state.prices
card_names = st.session_state.card_names
all_cards = st.session_state.all_cards
packs = st.session_state.packs
selected_backpack = st.session_state.selected_backpack
doc = st.session_state.doc

st.title("📊 總覽與 📖 全圖鑑")
tab_overview, tab_gallery = st.tabs(["📊 所有背包總覽", "📖 全圖鑑收集冊"])

# -----------------------------------------------------------
# 📊 ----- 總覽分頁 -----
with tab_overview:
    st.subheader("📊 全背包庫存交叉大總覽")
    st.caption("點擊下方按鈕將會即時連線掃描 Google Sheet 內的所有分頁背包，並進行數據自動整合與資產清算。")
    
    worksheets = [ws.title for ws in doc.worksheets()]
    
    if st.button("🔄 讀取並整合所有背包數據", type="primary", use_container_width=True):
        with st.spinner("正在穿越雲端，掃描所有背包分頁中...請稍候..."):
            try:
                master_data = {}
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
                                
                st.session_state.master_data_cache = master_data
                st.success("✅ 全背包雲端數據同步成功！已為您開啟下方篩選查找面板。")
            except Exception as e:
                st.error(f"跨背包整合失敗：{e}")

    if st.session_state.master_data_cache:
        master_data = st.session_state.master_data_cache
        all_scanned_ids = list(master_data.keys())
        scanned_packs = sorted(list(set([cid.split('-')[0] for cid in all_scanned_ids if '-' in cid])))
        
        st.write("---")
        st.markdown("### 🛠️ 庫存分類篩選面板")
        
        col_f1_t4, col_f2_t4 = st.columns(2)
        with col_f1_t4:
            filter_pack_t4 = st.selectbox("1. 過濾卡包 (全景總覽)", ["全部"] + scanned_packs, key="filter_pack_t4")
            
        if filter_pack_t4 == "全部": cards_filtered_by_pack = all_scanned_ids
        else: cards_filtered_by_pack = [cid for cid in all_scanned_ids if cid.startswith(filter_pack_t4 + "-")]
            
        scanned_prefixes = sorted(list(set([utils.get_prefix(cid) for cid in cards_filtered_by_pack])))
        with col_f2_t4:
            filter_prefix_t4 = st.selectbox("2. 過濾編號前綴 (全景總覽)", ["全部"] + scanned_prefixes, key="filter_prefix_t4")
            
        if filter_prefix_t4 == "全部": final_filtered_ids = cards_filtered_by_pack
        else: final_filtered_ids = [cid for cid in cards_filtered_by_pack if utils.get_prefix(cid) == filter_prefix_t4]
            
        table_rows = []
        grand_total_value = 0      
        filtered_total_value = 0   
        
        for c_id, bp_qtys in sorted(master_data.items()):
            total_qty = sum(bp_qtys.values())
            unit_price = prices.get(c_id, 0)
            subtotal_value = unit_price * total_qty
            grand_total_value += subtotal_value
            
            if c_id in final_filtered_ids:
                filtered_total_value += subtotal_value
                row_dict = {
                    "卡號": c_id,
                    "卡牌名稱": card_names.get(c_id, "未知"),
                    "單價 (円)": unit_price
                }
                for ws_title in worksheets: row_dict[f"🎒 {ws_title}"] = bp_qtys[ws_title]
                row_dict["📊 合計張數"] = total_qty
                row_dict["💰 總價值 (円)"] = subtotal_value
                table_rows.append(row_dict)
                
        st.write("")
        c_val1, c_val2 = st.columns(2)
        with c_val1: st.success(f"👑 全庫存終極總資產： **{grand_total_value} 円**")
        with c_val2:
            if filter_pack_t4 != "全部" or filter_prefix_t4 != "全部": st.info(f"🔍 當前篩選範圍資產估值： **{filtered_total_value} 円**")
            else: st.caption("💡 提示：使用上方選單進行篩選，可動態查看特定包或前綴的價值統計。")
                
        if table_rows:
            df = pd.DataFrame(table_rows)
            st.dataframe(df, use_container_width=True, height=500)
        else: st.warning("⚠️ 沒有符合當前篩選條件的卡片！")

# -----------------------------------------------------------
# 📖 ----- 圖鑑分頁 -----
with tab_gallery:
    st.subheader(f"📖 【{selected_backpack}】全圖鑑收集冊")
    if st.session_state.unsaved_changes:
        st.warning("⚠️ 你有尚未儲存的庫存變更！點擊加號或減號後，請記得去側邊欄或背包區進行『雲端儲存』。")
        
    col_gal_p, col_gal_r, col_gal_s = st.columns([2, 2, 2])
    with col_gal_p:
        gal_pack = st.selectbox("圖鑑過濾卡包：", ["全部"] + packs, key="gal_pack")
        if "prev_gal_pack" not in st.session_state: st.session_state.prev_gal_pack = gal_pack
        if st.session_state.prev_gal_pack != gal_pack:
            st.session_state.gallery_page = 1
            st.session_state.prev_gal_pack = gal_pack
            
    gal_cards_pack = all_cards if gal_pack == "全部" else [c for c in all_cards if c.startswith(gal_pack + "-")]
    gal_prefixes = sorted(list(set([utils.get_prefix(c) for c in gal_cards_pack])))
    
    with col_gal_r:
        gal_prefix = st.selectbox("圖鑑過濾前綴：", ["全部"] + gal_prefixes, key="gal_prefix")
        if "prev_gal_prefix" not in st.session_state: st.session_state.prev_gal_prefix = gal_prefix
        if st.session_state.prev_gal_prefix != gal_prefix:
            st.session_state.gallery_page = 1
            st.session_state.prev_gal_prefix = gal_prefix
            
    gal_cards_filtered = sorted(gal_cards_pack if gal_prefix == "全部" else [c for c in gal_cards_pack if utils.get_prefix(c) == gal_prefix])
    
    with col_gal_s:
        show_mode = st.selectbox("顯示模式：", ["顯示全部", "只看未擁有", "只看已擁有"], key="gal_mode")
        if "prev_gal_mode" not in st.session_state: st.session_state.prev_gal_mode = show_mode
        if st.session_state.prev_gal_mode != show_mode:
            st.session_state.gallery_page = 1
            st.session_state.prev_gal_mode = show_mode
            
    if show_mode == "只看未擁有":
        gal_cards_filtered = [c for c in gal_cards_filtered if st.session_state.my_inventory.get(c, 0) == 0]
    elif show_mode == "只看已擁有":
        gal_cards_filtered = [c for c in gal_cards_filtered if st.session_state.my_inventory.get(c, 0) > 0]

    st.divider()

    ITEMS_PER_PAGE = 50
    total_items = len(gal_cards_filtered)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
    
    if st.session_state.gallery_page > total_pages: 
        st.session_state.gallery_page = total_pages

    if total_items > 0:
        col_pag_prev, col_pag_info, col_pag_next = st.columns([1, 4, 1])
        with col_pag_prev:
            if st.button("⬅️ 上一頁", use_container_width=True, disabled=st.session_state.gallery_page == 1):
                st.session_state.gallery_page -= 1
                st.rerun()
        with col_pag_info:
            st.markdown(f"<h4 style='text-align: center;'>第 {st.session_state.gallery_page} 頁 / 共 {total_pages} 頁 (共 {total_items} 張)</h4>", unsafe_allow_html=True)
        with col_pag_next:
            if st.button("下一頁 ➡️", use_container_width=True, disabled=st.session_state.gallery_page == total_pages):
                st.session_state.gallery_page += 1
                st.rerun()

        start_idx = (st.session_state.gallery_page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        current_page_cards = gal_cards_filtered[start_idx:end_idx]

        st.write("")
        cols_per_row = 5
        for i in range(0, len(current_page_cards), cols_per_row):
            row_cards = current_page_cards[i:i + cols_per_row]
            cols = st.columns(cols_per_row)
            
            for j, c_id in enumerate(row_cards):
                with cols[j]:
                    owned_qty = st.session_state.my_inventory.get(c_id, 0)
                    img_url = utils.get_card_image_url(c_id, st.session_state.card_images)
                    
                    css_class = "card-owned" if owned_qty > 0 else "card-unowned"
                    st.markdown(f'<img src="{img_url}" class="{css_class}" style="width:100%; object-fit:contain; border-radius: 8px;">', unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align: center; margin-top: 8px;'><small><b>{c_id}</b></small><br><small>{card_names.get(c_id, '未知')}</small></div>", unsafe_allow_html=True)
                    
                    c_m, c_q, c_p = st.columns([1, 1, 1])
                    with c_m:
                        if st.button("➖", key=f"gal_m_{c_id}", use_container_width=True, disabled=owned_qty == 0):
                            st.session_state.my_inventory[c_id] -= 1
                            st.session_state.unsaved_changes = True
                            st.rerun()
                    with c_q:
                        st.markdown(f"<div style='text-align: center; padding-top: 5px;'><b>{owned_qty}</b></div>", unsafe_allow_html=True)
                    with c_p:
                        if st.button("➕", key=f"gal_p_{c_id}", use_container_width=True):
                            st.session_state.my_inventory[c_id] = owned_qty + 1
                            st.session_state.unsaved_changes = True
                            st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("---")
        col_pag_prev_b, col_pag_info_b, col_pag_next_b = st.columns([1, 4, 1])
        with col_pag_prev_b:
            if st.button("⬅️ 上一頁 ", use_container_width=True, key="prev_b", disabled=st.session_state.gallery_page == 1):
                st.session_state.gallery_page -= 1
                st.rerun()
        with col_pag_info_b:
            st.markdown(f"<div style='text-align: center; padding-top: 8px;'>回到頁首</div>", unsafe_allow_html=True)
        with col_pag_next_b:
            if st.button("下一頁 ➡️ ", use_container_width=True, key="next_b", disabled=st.session_state.gallery_page == total_pages):
                st.session_state.gallery_page += 1
                st.rerun()
    else:
        st.info("📦 根據目前的篩選條件，沒有找到任何卡片！")
