import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 工程差異分析工具", layout="wide")
st.title("🛠️ BOM 工程異動分析 (ECN 邏輯版)")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 比對設定")
    selected_levels = []
    st.subheader("選擇比對階層 (Level)")
    for i in range(1, 7):
        if st.checkbox(f"Level {i}", value=True if i in [3, 4, 5] else False):
            selected_levels.append(i)
    st.divider()
    st.caption("註：本工具優先以『位置(Ref Des)』為基準進行對齊比對。")

def parse_bom_to_ref_map(file_bytes):
    """將 BOM 解析為以 Ref Des 為 Key 的字典，方便位置對齊"""
    try:
        text = file_bytes.decode("big5")
    except:
        text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    ref_map = {} # { "C1": {"PN": "...", "Desc": "...", "Level": 3}, ... }
    
    current_item = None
    for line in lines:
        match = re.match(r'^(\d)\s+', line)
        if match:
            level = int(match.group(1))
            cols = re.split(r'\s{2,}', line.strip())
            if len(cols) >= 2:
                pn = cols[1]
                qty = float(cols[2]) if len(cols) > 2 and cols[2].replace('.','',1).isdigit() else 0
                desc = cols[3] if len(cols) > 3 else ""
                ref_raw = cols[-1] if len(cols) > 4 else ""
                
                # 僅處理數量大於 0 的有效料號，過濾雜訊
                if qty <= 0: continue
                
                # 拆解位置
                refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
                
                current_item = {"Level": level, "PN": pn, "Desc": desc}
                for r in refs:
                    ref_map[r] = current_item
        elif current_item and line.startswith(" " * 10):
            extra_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            for r in extra_refs:
                ref_map[r] = current_item
    return ref_map

# --- 檔案上傳 ---
uploaded_files = st.file_uploader("請上傳兩個 BOM 檔案", accept_multiple_files=True)

if len(uploaded_files) >= 2:
    map_a = parse_bom_to_ref_map(uploaded_files[0].getvalue())
    map_b = parse_bom_to_ref_map(uploaded_files[1].getvalue())

    st.success(f"比對目標：[A] {uploaded_files[0].name} ↔ [B] {uploaded_files[1].name}")

    # 取得所有出現過的位置 (聯集)
    all_refs = sorted(list(set(map_a.keys()) | set(map_b.keys())), key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    diff_data = []
    # 這裡實施「舊工具」的成對比對邏輯
    for ref in all_refs:
        item_a = map_a.get(ref)
        item_b = map_b.get(ref)
        
        # 篩選階層：只要其中一邊符合階層就列入考慮
        lvl_a = item_a['Level'] if item_a else None
        lvl_b = item_b['Level'] if item_b else None
        if (lvl_a not in selected_levels) and (lvl_b not in selected_levels):
            continue

        status = ""
        if not item_a: status = "🆕 位置新增"
        elif not item_b: status = "❌ 位置刪除"
        elif item_a['PN'] != item_b['PN']: status = "🔄 料號變更"
        else: continue # 無差異

        diff_data.append({
            "變更項目": status,
            "位置": ref,
            "A料號 (舊)": item_a['PN'] if item_a else "---",
            "B料號 (新)": item_b['PN'] if item_b else "---",
            "A規格": item_a['Desc'] if item_a else "",
            "B規格": item_b['Desc'] if item_b else "",
            "階層": lvl_b if lvl_b else lvl_a
        })

    if diff_data:
        df_result = pd.DataFrame(diff_data)
        
        # 為了讓結果像舊工具一樣「成對且精簡」，我們將相同變更內容的位置合併
        # 相同 (狀態, A料號, B料號) 的合併在一起
        summary = df_result.groupby(["變更項目", "A料號 (舊)", "B料號 (新)", "A規格", "B規格", "階層"])["位置"].apply(lambda x: ".".join(x)).reset_index()
        
        # 重新排列欄位順序，模仿舊工具
        summary = summary[["變更項目", "位置", "A料號 (舊)", "B料號 (新)", "A規格", "B規格", "階層"]]

        def color_status(val):
            if val == "🔄 料號變更": return 'color: #fd7e14; font-weight: bold'
            if val == "🆕 位置新增": return 'color: #28a745; font-weight: bold'
            if val == "❌ 位置刪除": return 'color: #dc3545; font-weight: bold'
            return ''

        st.subheader("📋 異動分析報告 (按位置對齊)")
        st.dataframe(summary.style.map(color_status, subset=['變更項目']), use_container_width=True)
    else:
        st.success("✅ 兩份 BOM 在選定階層內之『位置與料號對應』完全一致。")
