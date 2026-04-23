import streamlit as st
import pandas as pd
import re

# 設定網頁標題與寬度
st.set_page_config(page_title="BOM 矩陣比對工具", layout="wide")

st.title("📑 BOM 多批次智能比對工具")

# --- 1. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 比對設定")
    # 大前提開關
    pcb_strict = st.checkbox("強制 PCB 版號一致 (圈 PCB)", value=True)
    
    # 階層勾選器
    st.subheader("選擇比對階層 (Level)")
    levels = []
    for i in range(1, 7):
        default = True if i in [3, 4] else False
        if st.checkbox(f"Level {i}", value=default):
            levels.append(i)

# --- 2. 檔案上傳 ---
uploaded_files = st.file_uploader("請上傳 BOM 文字檔 (支援多檔案拖拉)", accept_multiple_files=True)

def parse_bom_line(line):
    """解析單行 BOM 資料"""
    # 匹配開頭的階層數字
    match = re.match(r'^(\d)\s+', line)
    if not match:
        return None
    
    level = int(match.group(1))
    # 使用多個空格拆分欄位
    parts = re.split(r'\s{2,}', line.strip())
    
    if len(parts) < 2:
        return None
        
    pn = parts[1]
    qty = parts[2] if len(parts) > 2 else "0"
    desc = parts[3] if len(parts) > 3 else ""
    
    # 處理 Ref Des：拆分點號、移除括號內容
    ref_raw = parts[-1] if len(parts) > 4 else ""
    # 範例：JP2(2-3)1. 轉成 JP2
    refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
    
    return {"Level": level, "PN": pn, "Qty": qty, "Desc": desc, "Refs": refs}

if uploaded_files:
    all_data = {}
    pcb_to_files = {}

    for uploaded_file in uploaded_files:
        # --- 自動處理 Big5 編碼 ---
        try:
            content = uploaded_file.getvalue().decode("big5")
        except:
            content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        
        lines = content.splitlines()
        file_parts = []
        pcb_version = "未知版號"
        
        current_part = None
        for line in lines:
            parsed = parse_bom_line(line)
            if parsed:
                # 識別大前提：PCB 版號
                if "PCB" in parsed["Desc"].upper() and "ASSY" not in parsed["Desc"].upper():
                    pcb_version = parsed["PN"]
                file_parts.append(parsed)
                current_part = parsed
            elif current_part and line.startswith(" " * 10):
                # 處理跨行位置
                extra_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
                current_part["Refs"].extend(extra_refs)
        
        all_data[uploaded_file.name] = {"parts": file_parts, "pcb": pcb_version}
        
        if pcb_version not in pcb_to_files:
            pcb_to_files[pcb_version] = []
        pcb_to_files[pcb_version].append(uploaded_file.name)

    # --- 3. 顯示結果 ---
    st.success(f"成功讀取 {len(uploaded_files)} 個檔案")

    for pcb, filenames in pcb_to_files.items():
        with st.expander(f"📦 PCB 版號群組：{pcb} ({len(filenames)} 檔案)", expanded=True):
            # 取得所有唯一的料號清單
            target_pns = []
            for fname in filenames:
                for p in all_data[fname]["parts"]:
                    if p["Level"] in levels:
                        target_pns.append((p["PN"], p["Desc"]))
            
            unique_pns = pd.DataFrame(target_pns, columns=["PN", "Desc"]).drop_duplicates("PN").sort_values("PN")
            
            # 建立比對矩陣
            result_df = unique_pns.copy()
            for fname in filenames:
                file_dict = {p["PN"]: f"{p['Qty']} | {','.join(p['Refs'])}" for p in all_data[fname]["parts"]}
                result_df[fname] = result_df["PN"].map(file_dict).fillna("0 (無)")
            
            st.dataframe(result_df, use_container_width=True)

else:
    st.info("💡 請在左側設定階層，並將檔案拖入上方區域。")
