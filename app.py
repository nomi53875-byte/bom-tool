import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 工程差異分析工具", layout="wide")

# --- 介面樣式微調 (CSS) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 150px; max-width: 200px; }
    .stCheckbox { margin-bottom: -15px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛠️ BOM 工程異動分析 (舊工具對齊版)")

# --- 1. 側邊欄：縮小版面 ---
with st.sidebar:
    st.subheader("階層篩選")
    selected_levels = []
    # 緊湊型排列
    for i in range(1, 7):
        if st.checkbox(f"Level {i}", value=True if i in [3, 4, 5] else False, key=f"L{i}"):
            selected_levels.append(i)
    st.divider()
    st.caption("版本：2024.04.24")

# --- 2. 強化版解析邏輯 (確保規格完整) ---
def parse_bom_expert(file_bytes):
    try:
        text = file_bytes.decode("big5")
    except:
        text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    ref_map = {}
    current_item = None

    for line in lines:
        # 修正：精準匹配階層數字開頭
        match = re.match(r'^(\d)\s+(\S+)\s+([\d.]+)', line)
        if match:
            level = int(match.group(1))
            pn = match.group(2)
            qty = float(match.group(3))
            
            # 完整擷取規格：利用剩餘字串排除末尾位置
            # 尋找位置編號起始點 (通常是連續大寫字母+數字)
            parts = re.split(r'\s{2,}', line.strip())
            desc = parts[3] if len(parts) > 3 else ""
            ref_raw = parts[-1] if len(parts) > 4 else ""
            
            if qty <= 0: continue
            
            refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
            
            current_item = {"Level": level, "PN": pn, "Desc": desc}
            for r in refs:
                ref_map[r] = current_item
        elif current_item and line.startswith(" " * 10):
            # 處理跨行位置
            extra_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            for r in extra_refs:
                ref_map[r] = current_item
    return ref_map

# --- 3. 比對與呈現 ---
uploaded_files = st.file_uploader("上傳兩個 BOM (.txt)", accept_multiple_files=True)

if len(uploaded_files) >= 2:
    map_a = parse_bom_expert(uploaded_files[0].getvalue())
    map_b = parse_bom_expert(uploaded_files[1].getvalue())

    st.info(f"對比：[A] {uploaded_files[0].name} ↔ [B] {uploaded_files[1].name}")

    all_refs = sorted(list(set(map_a.keys()) | set(map_b.keys())), 
                      key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    diff_list = []
    for ref in all_refs:
        a = map_a.get(ref)
        b = map_b.get(ref)
        
        lvl_a = a['Level'] if a else None
        lvl_b = b['Level'] if b else None
        
        if (lvl_a not in selected_levels) and (lvl_b not in selected_levels):
            continue

        status = ""
        if not a: status = "🆕 新增"
        elif not b: status = "❌ 刪除"
        elif a['PN'] != b['PN']: status = "🔄 變更"
        else: continue

        diff_list.append({
            "變更差異": status,
            "階層": lvl_b if lvl_b else lvl_a,
            "位置": ref,
            "A料號 (舊)": a['PN'] if a else "---",
            "B料號 (新)": b['PN'] if b else "---",
            "規格描述": b['Desc'] if b else a['Desc']
        })

    if diff_list:
        df = pd.DataFrame(diff_list)
        # 依照舊工具邏輯：將相同異動的位置合併成一列，避免表格過碎
        final_view = df.groupby(["變更差異", "階層", "A料號 (舊)", "B料號 (新)", "規格描述"])["位置"].apply(lambda x: ".".join(x)).reset_index()
        
        # 調整欄位順序：變更差異 | 階層 | 位置 | 料號 | 規格
        final_view = final_view[["變更差異", "階層", "位置", "A料號 (舊)", "B料號 (新)", "規格描述"]]

        def style_diff(val):
            if val == "🔄 變更": return 'color: #fd7e14; font-weight: bold'
            if val == "🆕 新增": return 'color: #28a745; font-weight: bold'
            if val == "❌ 刪除": return 'color: #dc3545; font-weight: bold'
            return ''

        st.dataframe(final_view.style.map(style_diff, subset=['變更差異']), use_container_width=True)
    else:
        st.success("選定階層內無差異。")
