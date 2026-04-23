import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 矩陣比對工具", layout="wide")
st.title("📊 BOM 多批次智能比對工具")

# --- 側邊欄：設定比對邏輯 ---
with st.sidebar:
    st.header("⚙️ 設定面板")
    st.info("大前提：系統會自動尋找 Description 包含 'PCB' 的料號作為分組依據")
    
    st.subheader("階層篩選 (Level)")
    l3 = st.checkbox("Level 3", value=True)
    l4 = st.checkbox("Level 4", value=True)
    l5 = st.checkbox("Level 5", value=False)
    
    target_levels = []
    if l3: target_levels.append(1 if l3 else 0) # 修正邏輯
    target_levels = [lvl for lvl, checked in {3:l3, 4:l4, 5:l5}.items() if checked]

# --- 檔案上傳區 ---
uploaded_files = st.file_uploader("請上傳多個 BOM 文字檔 (.txt)", accept_multiple_files=True)

def parse_bom(file_bytes, file_name):
    # 解決亂碼：先嘗試 Big5，不行再換 UTF-8
    try:
        text = file_bytes.decode("big5")
    except:
        text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    data = []
    pcb_pn = "Unknown_PCB"
    
    for line in lines:
        # 匹配開頭階層數字 (例如 3, 4, 5)
        match = re.match(r'^(\d)\s+', line)
        if match:
            level = int(match.group(1))
            cols = re.split(r'\s{2,}', line.strip())
            if len(cols) >= 2:
                pn = cols[1]
                qty = cols[2] if len(cols) > 2 else "0"
                desc = cols[3] if len(cols) > 3 else ""
                
                # 自動識別 PCB 版號 (大前提)
                if "PCB" in desc.upper() and "ASSY" not in desc.upper():
                    pcb_pn = pn
                
                # 處理 Ref Des (位置編號)：拆分點號並過濾括號
                ref_raw = cols[-1] if len(cols) > 4 else ""
                refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
                
                data.append({"Level": level, "PN": pn, "Qty": qty, "Desc": desc, "Refs": refs})
    return pd.DataFrame(data), pcb_pn

if uploaded_files:
    all_boms = {}
    pcb_groups = {}

    for f in uploaded_files:
        df, pcb = parse_bom(f.getvalue(), f.name)
        all_boms[f.name] = {"df": df, "pcb": pcb}
        if pcb not in pcb_groups: pcb_groups[pcb] = []
        pcb_groups[pcb].append(f.name)

    st.success(f"已讀取 {len(uploaded_files)} 個檔案，識別出 {len(pcb_groups)} 種 PCB 版本")

    # --- 顯示矩陣表格 ---
    for pcb, fnames in pcb_groups.items():
        with st.expander(f"📦 PCB 分組：{pcb} (共 {len(fnames)} 個檔案)", expanded=True):
            # 彙整所有料號
            combined_dfs = [all_boms[fn]["df"] for fn in fnames]
            master_list = pd.concat(combined_dfs).drop_duplicates("PN")
            # 篩選階層
            master_list = master_list[master_list["Level"].isin(target_levels)]
            
            # 建立矩陣
            result = master_list[["Level", "PN", "Desc"]].copy()
            for fn in fnames:
                temp_df = all_boms[fn]["df"][["PN", "Qty", "Refs"]]
                # 格式化顯示：數量 + 位置
                temp_df[fn] = temp_df.apply(lambda x: f"{x['Qty']} | {','.join(x['Refs'][:5])}...", axis=1)
                result = pd.merge(result, temp_df[["PN", fn]], on="PN", how="left").fillna("0 (缺件)")
            
            st.dataframe(result, use_container_width=True)
