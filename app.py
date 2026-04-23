import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 工程差異分析工具", layout="wide")

# --- 側邊欄 CSS 縮減版面 ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 160px; max-width: 180px; }
    .stCheckbox { margin-bottom: -12px; }
    div[data-testid="stExpander"] div[role="button"] p { font-size: 14px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛠️ BOM 工程異動分析 (精準對齊版)")

# --- 1. 側邊欄：一列整齊排列 ---
with st.sidebar:
    st.subheader("階層篩選")
    selected_levels = []
    for i in range(1, 7):
        if st.checkbox(f"L{i}", value=True if i in [3, 4, 5] else False, key=f"L{i}"):
            selected_levels.append(i)
    st.divider()
    st.caption("Status: Logic V4.0")

# --- 2. 核心解析邏輯 (精準過濾零件位置) ---
def parse_bom_expert(file_bytes):
    try:
        text = file_bytes.decode("big5")
    except:
        text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    ref_map = {}
    current_item = None

    for line in lines:
        # 正則表達式：階層(1) 至少兩個空格 料號(2) 至少兩個空格 數量(3)
        match = re.match(r'^(\d)\s+(\S+)\s+([\d.]+)', line)
        if match:
            level = int(match.group(1))
            pn = match.group(2)
            qty = float(match.group(3))
            
            # 使用固定寬度或大空格切分，確保規格完整
            parts = re.split(r'\s{2,}', line.strip())
            desc = parts[3] if len(parts) > 3 else ""
            ref_raw = parts[-1] if len(parts) > 4 else ""
            
            if qty <= 0: continue
            
            # 【關鍵修正】：零件位置守門員
            # 只有符合「英文字母開頭+數字」的字串才視為 Ref Des (如 C1, R1, U1)
            # 這樣就能過濾掉 "ECS-9700..." 這種描述性文字
            raw_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
            valid_refs = [r for r in raw_refs if re.match(r'^[A-Z]+\d+', r)]
            
            current_item = {"Level": level, "PN": pn, "Desc": desc}
            for r in valid_refs:
                ref_map[r] = current_item
                
        elif current_item and line.startswith(" " * 10):
            # 處理跨行位置，同樣套用守門員過濾
            extra_raw = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            valid_extra = [r for r in extra_raw if re.match(r'^[A-Z]+\d+', r)]
            for r in valid_extra:
                ref_map[r] = current_item
    return ref_map

# --- 3. 比對與呈現 ---
uploaded_files = st.file_uploader("上傳兩個 BOM (.txt) 進行對齊比對", accept_multiple_files=True)

if len(uploaded_files) >= 2:
    map_a = parse_bom_expert(uploaded_files[0].getvalue())
    map_b = parse_bom_expert(uploaded_files[1].getvalue())

    st.info(f"對比：[A] {uploaded_files[0].name} ↔ [B] {uploaded_files[1].name}")

    # 位置排序邏輯
    all_refs = sorted(list(set(map_a.keys()) | set(map_b.keys())), 
                      key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    diff_list = []
    for ref in all_refs:
        a = map_a.get(ref)
        b = map_b.get(ref)
        
        lvl_a = a['Level'] if a else None
        lvl_b = b['Level'] if b else None
        
        # 篩選勾選的階層
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
        # 合併同類型異動的位置
        final_view = df.groupby(["變更差異", "階層", "A料號 (舊)", "B料號 (新)", "規格描述"])["位置"].apply(lambda x: ".".join(x)).reset_index()
        
        # 【修正欄位順序】：變更差異 | 階層 | 位置 | 料號 | 規格
        final_view = final_view[["變更差異", "階層", "位置", "A料號 (舊)", "B料號 (新)", "規格描述"]]

        def style_diff(val):
            if val == "🔄 變更": return 'color: #fd7e14; font-weight: bold'
            if val == "🆕 新增": return 'color: #28a745; font-weight: bold'
            if val == "❌ 刪除": return 'color: #dc3545; font-weight: bold'
            return ''

        st.dataframe(final_view.style.map(style_diff, subset=['變更差異']), use_container_width=True)
    else:
        st.success("✨ 恭喜！選定階層內所有零件位置與料號對應完全吻合。")
