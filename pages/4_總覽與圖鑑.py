import streamlit as st
import pandas as pd
import math
import utils

# --- 防呆檢查：確保已經載入基本資料 ---
if "my_inventory" not in st.session_state:
    st.warning("⚠️ 請先從側邊欄選擇並載入一個背包！")
    st.stop()

# --- 初始化基本變數 ---
selected_backpack = st.session_state.get("current_bp_name", "未選擇")
prices = st.session_state.get("prices", {})
card_names = st.session_state.get("card_names", {})
worksheets = st.session_state.get("worksheets_list", [selected_backpack])

# 圖鑑全卡表設定
all_cards = sorted(list(st.session_state.get("card_images", {}).keys()))
packs = sorted(list(set([utils.get_pack_name(c) for c in all_cards if "-" in c])))

st.title("📊 總覽與圖鑑")

# 🌟 頂部工具區：庫存匯出與匯入 (支援全背包整合)
with st.expander("⚙️ 進階功能：庫存匯出與匯入 (支援全背包整合)"):
    st.write("### 📥 下載庫存 (匯出)")
    # 讓使用者選擇要下載單一背包還是全部合併
    export_mode = st.radio("選擇匯出範圍：", [f"📦 當前背包 ({selected_backpack})", "🌍 所有背包 (合併總計)"], horizontal=True)
    
    if export_mode.startswith("📦"):
        # 匯出當前背包 (直接讀取記憶體，不消耗 API)
        current_inv = [{"卡號": k, "擁有數量": v} for k, v in st.session_state.my_inventory.items() if v > 0]
        if current_inv:
            df_export = pd.DataFrame(current_inv)
            csv = df_export.to_csv(index=False).encode('utf-8-sig')
            st.download_button(f"📥 下載 {selected_backpack} CSV", data=csv, file_name=f"{selected_backpack}_庫存.csv", mime="text/csv")
        else:
            st.info("當前背包沒有卡片可供匯出。")
            
    else:
        # 匯出所有背包 (利用總覽的快取資料，保護 API 不被鎖)
        if st.session_state.get("master_data_cache") is None:
            st.warning("⚠️ 請先在下方的總覽區點擊「🔄 讀取並整合所有背包數據」按鈕，才能下載全部背包的整合資料喔！")
        else:
            merged_inv = [{"卡號": k, "擁有數量": v} for k, v in st.session_state.master_data_cache.items() if v > 0]
            if merged_inv:
                df_export = pd.DataFrame(merged_inv)
                csv = df_export.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載所有背包合併 CSV", data=csv, file_name="全背包整合庫存.csv", mime="text/csv")
            else:
                st.info("所有背包都沒有卡片。")
                
    st.divider()
    
    st.write("### 📤 上傳庫存 (匯入至當前背包)")
    st.warning(f"這會將上傳的 CSV 資料加入到目前的【{selected_backpack}】，請確認卡號欄位正確。")
    uploaded_file = st.file_uploader("上傳 CSV 備份檔", type=["csv"])
    if uploaded_file is not None:
        try:
            df_import = pd.read_csv(uploaded_file)
            if "卡號" in df_import.columns and "擁有數量" in df_import.columns:
                for _, row in df_import.iterrows():
                    cid = str(row["卡號"]).strip()
                    qty = int(row["擁有數量"])
                    if qty > 0:
                        st.session_state.my_inventory[cid] = st.session_state.my_inventory.get(cid, 0) + qty
                st.session_state.unsaved_changes = True
                st.success("✅ 匯入成功！請記得點擊側邊欄的「儲存至雲端」按鈕來正式寫入。")
            else:
                st.error("CSV 格式錯誤：必須包含「卡號」與「擁有數量」兩個欄位。")
        except Exception as e:
            st.error(f"讀取檔案失敗：{e}")

# --- 宣告分頁 ---
tab_overview, tab_gallery = st.tabs(["📊 全景總覽區", "📖 圖鑑收集冊"])

# -----------------------------------------------------------
# 📊 ----- 總覽分頁 -----
with tab_overview:
    st.subheader("🌍 全背包庫存總覽")
    
    if st.session_state.get("master_data_cache") is None:
        if st.button("🔄 讀取並整合所有背包數據", type="primary"):
            with st.spinner("正在向雲端請求所有背包資料，請稍候..."):
                try:
                    client = utils.init_gspread_client()
                    doc = client.open_by_key(st.session_state.sheet_id)
                    master_data = {}
                    for ws_title in worksheets:
                        ws = doc.worksheet(ws_title)
                        records = ws.get_all_records()
                        for row in records:
                            if '卡號' in row:
                                cid = str(row['卡號'])
                                qty = int(row['擁有數量'])
                                if qty > 0:
                                    if cid not in master_data:
                                        master_data[cid] = {w: 0 for w in worksheets}
                                    master_data[cid][ws_title] = qty
                    st.session_state.master_data_cache = master_data
                    st.rerun()
                except Exception as e:
                    st.error(f"讀取失敗：{e}")
        st.info("點擊上方按鈕載入全背包數據 (消耗較多 API，建議一天更新一次即可)")
    else:
        st.success("✅ 已成功載入總覽快取資料！")
        master_data = st.session_state.master_data_cache
        
        all_scanned_ids = sorted(list(master_data.keys()))
        scanned_packs = sorted(list(set([utils.get_pack_name(cid) for cid in all_scanned_ids if "-" in cid])))
        
        col_f1_t4, col_f2_t4 = st.columns(2)
        with col_f1_t4:
            filter_pack_t4 = st.selectbox("1. 過濾卡包 (全景總覽)", ["全部"] + scanned_packs, key="filter_pack_t4")
            
        if filter_pack_t4 == "全部": 
            cards_filtered_by_pack = all_scanned_ids
        else: 
            cards_filtered_by_pack = [cid for cid in all_scanned_ids if cid.startswith(filter_pack_t4 + "-")]
            
        scanned_prefixes = sorted(list(set([utils.get_prefix(cid) for cid in cards_filtered_by_pack])))
        with col_f2_t4:
            filter_prefix_t4 = st.selectbox("2. 過濾編號前綴 (全景總覽)", ["全部"] + scanned_prefixes, key="filter_prefix_t4")
            
        if filter_prefix_t4 == "全部": 
            final_filtered_ids = cards_filtered_by_pack
        else: 
            final_filtered_ids = [cid for cid in cards_filtered_by_pack if utils.get_prefix(cid) == filter_prefix_t4]
            
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
                for ws_title in worksheets: 
                    row_dict[f"🎒 {ws_title}"] = bp_qtys[ws_title]
                row_dict["📊 合計張數"] = total_qty
                row_dict["💰 總價值 (円)"] = subtotal_value
                table_rows.append(row_dict)
                
        st.write("")
        c_val1, c_val2 = st.columns(2)
        with c_val1: 
            st.success(f"👑 全庫存終極總資產： **{grand_total_value} 円**")
        with c_val2:
            if filter_pack_t4 != "全部" or filter_prefix_t4 != "全部": 
                st.info(f"🔍 當前篩選範圍資產估值： **{filtered_total_value} 円**")
            else: 
                st.caption("💡 提示：使用上方選單進行篩選，可動態查看特定包或前綴的價值統計。")
                
        if table_rows:
            df = pd.DataFrame(table_rows)
            st.dataframe(df, use_container_width=True, height=500)
        else: 
            st.warning("⚠️ 沒有符合當前篩選條件的卡片！")

# -----------------------------------------------------------
# 📖 ----- 圖鑑分頁 -----
with tab_gallery:
    st.subheader(f"📖 【{selected_backpack}】全圖鑑收集冊")
    if st.session_state.get("unsaved_changes", False):
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
    
    # 確保頁碼安全
    if "gallery_page" not in st.session_state:
        st.session_state.gallery_page = 1
    if st.session_state.gallery_page > total_pages: 
        st.session_state.gallery_page = total_pages

    if total_items > 0:
        col_pag_prev, col_pag_info, col_pag_next = st.columns([1, 4, 1])
        with col_pag_prev:
            if st.button("⬅️ 上一頁", use_container_width=True, disabled=st.session_state.gallery_page <= 1):
                st.session_state.gallery_page -= 1
                st.rerun()
        with col_pag_info:
            st.markdown(f"<h4 style='text-align: center;'>第 {st.session_state.gallery_page} 頁 / 共 {total_pages} 頁 (共 {total_items} 張)</h4>", unsafe_allow_html=True)
        with col_pag_next:
            if st.button("下一頁 ➡️", use_container_width=True, disabled=st.session_state.gallery_page >= total_pages):
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
                    img_url = utils.get_card_image_url(c_id, st.session_state.get("card_images", {}))
                    
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
            if st.button("⬅️ 上一頁 ", use_container_width=True, key="prev_b", disabled=st.session_state.gallery_page <= 1):
                st.session_state.gallery_page -= 1
                st.rerun()
        with col_pag_info_b:
            st.markdown(f"<div style='text-align: center; padding-top: 8px;'>回到頁首</div>", unsafe_allow_html=True)
        with col_pag_next_b:
            if st.button("下一頁 ➡️ ", use_container_width=True, key="next_b", disabled=st.session_state.gallery_page >= total_pages):
                st.session_state.gallery_page += 1
                st.rerun()
    else:
        st.info("📦 根據目前的篩選條件，沒有找到任何卡片！")
