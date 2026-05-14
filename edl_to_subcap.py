# This script was created by Seb Riezler

import streamlit as st
import streamlit.components.v1 as components
import re
import os
from datetime import datetime
import base64

def extract_loc_blocks_with_colors(edl_text, separator):
    lines = edl_text.splitlines()
    blocks = []
    last_src_start = None
    last_src_end = None
    timecode_pattern = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
    loc_full_pattern = re.compile(r"\* ?LOC:\s*\d{2}:\d{2}:\d{2}:\d{2}\s+(\S+)\s+(.*)", re.IGNORECASE)

    for line in lines:
        timecodes = timecode_pattern.findall(line)
        if len(timecodes) >= 4:
            last_src_start, last_src_end = timecodes[-2], timecodes[-1]
        if "*LOC:" in line.upper() or "* LOC:" in line.upper():
            match = loc_full_pattern.search(line)
            if match and last_src_start and last_src_end:
                color = match.group(1).strip().upper()
                full_comment = match.group(2).strip()
                if separator and separator in full_comment:
                    p1, p2 = full_comment.split(separator, 1)
                    blocks.append((last_src_start, last_src_end, color, p1.strip(), p2.strip()))
                else:
                    blocks.append((last_src_start, last_src_end, color, full_comment, ""))
                last_src_start = last_src_end = None
    return blocks

def create_subcap_txt(blocks, part_index):
    output = ["<begin subtitles>\n"]
    for b in blocks:
        if b[part_index]:
            output.append(f"{b[0]} {b[1]}\n{b[part_index]}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

st.title("EDL → Subtitle Exporter")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])
st.divider()

st.subheader("Split & Naming Settings")
c1, c2, c3 = st.columns(3)
with c1: user_separator = st.text_input("Separator", value="//")
with c2: suffix_part1 = st.text_input("Suffix Part 1", value="ShotID")
with c3: suffix_part2 = st.text_input("Suffix Part 2", value="ScopeOfWork")
st.divider()

if uploaded_file:
    try:
        content = uploaded_file.read().decode("utf-8")
    except:
        content = uploaded_file.read().decode("latin1")

    all_blocks = extract_loc_blocks_with_colors(content, user_separator)

    if all_blocks:
        base_name = os.path.splitext(uploaded_file.name)[0]
        today = datetime.now().strftime("%y%m%d")
        
        res1 = create_subcap_txt(all_blocks, 3)
        res2 = create_subcap_txt(all_blocks, 4)
        fname1 = f"{base_name}_{suffix_part1}_{today}.txt"
        fname2 = f"{base_name}_{suffix_part2}_{today}.txt"

        col_p1, col_p2 = st.columns(2)
        with col_p1: st.text_area(fname1, res1, height=200)
        with col_p2: st.text_area(fname2, res2, height=200)

        st.divider()

        # JS Multi-Download logic
        b64_1 = base64.b64encode(res1.encode()).decode()
        b64_2 = base64.b64encode(res2.encode()).decode()

        dl_script = f"""
            <script>
            function downloadFiles() {{
                const files = [
                    {{ name: "{fname1}", data: "data:text/plain;base64,{b64_1}" }},
                    {{ name: "{fname2}", data: "data:text/plain;base64,{b64_2}" }}
                ];
                files.forEach((file, index) => {{
                    setTimeout(() => {{
                        const link = document.createElement("a");
                        link.href = file.data;
                        link.download = file.name;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }}, index * 250); // Small delay to help browsers handle multiple triggers
                }});
            }}
            </script>
            <div style="display: flex; justify-content: center;">
                <button onclick="downloadFiles()" style="
                    background-color: #ff4b4b; 
                    color: white; 
                    padding: 12px 24px; 
                    border: none; 
                    border-radius: 8px; 
                    cursor: pointer; 
                    font-family: sans-serif;
                    font-weight: bold;
                    width: 100%;
                ">
                    📥 Download Both Files (Separate TXTs)
                </button>
            </div>
        """
        components.html(dl_script, height=80)
        st.caption("Note: If prompted, please allow 'Multiple Downloads' in your browser.")
    else:
        st.warning("No matching entries found.")
