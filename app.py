import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 深度比對工具", layout="wide")
st.title("🔍 BOM 變更差異深度比對")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 比對設定")
    
    # 修正點 1：階層選擇改為一列整齊排列
    st.subheader("選擇比對階層 (Level)")
    selected_levels = []
    for i in range(1, 7):
        # 預設勾選 3, 4 階
        if st.checkbox(f"Level {i}", value=True if i in [3, 4] else False):
            selected_levels.append(i)
    
    st.divider()
    st.info("💡 系統目前設定為：僅顯示有變更的項目")

# --- 核心處理函數 ---
def parse_bom(file_bytes):
    try:
        text = file_bytes.decode("big5")
    except:
        text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    data = []
    pcb_pn = "Unknown"
    current_item = None

    for line in lines:
        match = re.match(r'^(\d)\s+', line)
        if match:
            level = int(match.group(1))
            cols = re.split(r'\s{2,}', line.strip())
            if len(cols) >= 2:
                pn = cols[1]
                qty = cols[2] if len(cols) > 2 else "0"
                desc = cols[3] if len(cols) > 3 else ""
                ref_raw = cols[-1] if len(cols) > 4 else ""
                # 處理位置編號：移除括號、點號拆分
                refs = sorted([re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()])
                
                if "PCB" in desc.upper() and "ASSY" not in desc.upper(): pcb_pn = pn
                
                current_item = {"Level": level, "PN": pn, "Qty": qty, "Desc": desc, "Refs": set(refs)}
                data.append(current_item)
        elif current_item and line.startswith(" " * 10):
            extra_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            current_item["Refs"].update(extra_refs)

    df = pd.DataFrame(data)
    if not df.empty:
        df["Refs"] = df["Refs"].apply(lambda x: sorted(list(x)))
    return df, pcb_pn

# --- 檔案上傳 ---
uploaded_files = st.file_uploader("請上傳兩個 BOM 進行對照比對", accept_multiple_files=True)

if len(uploaded_files) >= 2:
    df_a, pcb_a = parse_bom(uploaded_files[0].getvalue())
    df_b, pcb_b = parse_bom(uploaded_files[1].getvalue())

    st.success(f"比對目標：[A] {uploaded_files[0].name} ↔ [B] {uploaded_files[1].name}")

    # 篩選階層
    df_a = df_a[df_a['Level'].isin(selected_levels)]
    df_b = df_b[df_b['Level'].isin(selected_levels)]

    # 合併兩者料號清單
    all_pns = pd.concat([df_a[['PN', 'Desc', 'Level']], df_b[['PN', 'Desc', 'Level']]]).drop_duplicates('PN')

    diff_data = []
    for _, row in all_pns.iterrows():
        pn = row['PN']
        item_a = df_a[df_a['PN'] == pn].to_dict('records')
        item_b = df_b[df_b['PN'] == pn].to_dict('records')
        
        item_a = item_a[0] if item_a else None
        item_b = item_b[0] if item_b else None
        
        qty_a = item_a['Qty'] if item_a else "0"
        qty_b = item_b['Qty'] if item_b else "0"
        refs_a = item_a['Refs'] if item_a else []
        refs_b = item_b['Refs'] if item_b else []
        
        # 判斷變更狀態
        status = ""
        if not item_a: status = "🆕 新增"
        elif not item_b: status = "❌ 刪除"
        elif qty_a != qty_b or refs_a != refs_b: status = "⚠️ 變更"
        else: continue # 修正點 2：無差異則跳過，不加入清單

        diff_data.append({
            "變更差異": status,
            "Level": row['Level'],
            "料號": pn,
            "規格描述": row['Desc'],
            "A數量": qty_a,
            "B數量": qty_b,
            "A位置": ",".join(refs_a),
            "B位置": ",".join(refs_b)
        })

    if diff_data:
        result_df = pd.DataFrame(diff_data)

        # 顏色渲染
        def color_status(val):
            color = 'black'
            if val == "🆕 新增": color = '#28a745' # 綠
            elif val == "❌ 刪除": color = '#dc3545' # 紅
            elif val == "⚠️ 變更": color = '#fd7e14' # 橘
            return f'color: {color}; font-weight: bold'

        st.subheader("📋 差異比對清單 (僅顯示變更項)")
        st.dataframe(result_df.style.map(color_status, subset=['變更差異']), use_container_width=True)
    else:
        st.balloons()
        st.success("✨ 比對完成：兩個 BOM 在選定階層內完全一致，無任何差異！")

elif uploaded_files:
    st.warning("請至少上傳 2 個檔案以執行比對。")
