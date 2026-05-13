# This script was created by Seb Riezler (Extended for Split-Function with specific Suffixes)

import streamlit as st
import re
import os
from datetime import datetime
import xml.etree.ElementTree as ET

def extract_loc_blocks_with_colors(edl_text):
    lines = edl_text.splitlines()
    blocks = []
    last_src_start = None
    last_src_end = None
    timecode_pattern = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
    loc_full_pattern = re.compile(r"\* ?LOC:\s*\d{2}:\d{2}:\d{2}:\d{2}\s+(\S+)\s+(.*)", re.IGNORECASE)

    for line in lines:
        timecodes = timecode_pattern.findall(line)
        if len(timecodes) >= 4:
            last_src_start = timecodes[-2]
            last_src_end = timecodes[-1]
        if "*LOC:" in line.upper() or "* LOC:" in line.upper():
            match = loc_full_pattern.search(line)
            if match and last_src_start and last_src_end:
                color = match.group(1).strip().upper()
                full_comment = match.group(2).strip()
                
                # Split-Logik für //
                if "//" in full_comment:
                    parts = full_comment.split("//", 1)
                    comment_part1 = parts[0].strip()
                    comment_part2 = parts[1].strip()
                else:
                    comment_part1 = full_comment
                    comment_part2 = ""
                
                blocks.append((last_src_start, last_src_end, color, comment_part1, comment_part2))
                last_src_start = last_src_end = None
    return blocks

def create_subcap_txt(blocks, part_index):
    """part_index 3 = ShotID (vor //), part_index 4 = ScopeOfWork (nach //)"""
    output = ["<begin subtitles>\n"]
    for b in blocks:
        start, end, text = b[0], b[1], b[part_index]
        if text:
            output.append(f"{start} {end}\n{text}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

# Streamlit UI
st.title("EDL → Subtitle Exporter (Split & Suffix Update)")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = uploaded_file.read().decode("latin1")

    all_blocks = extract_loc_blocks_with_colors(content)

    if all_blocks:
        base_name = os.path.splitext(uploaded_file.name)[0]
        today_str = datetime.now().strftime("%y%m%d")

        # Check if split is needed
        has_split = any(b[4] != "" for b in all_blocks)

        if has_split:
            # File 1: ShotID (Vor //)
            res1 = create_subcap_txt(all_blocks, 3)
            fname1 = f"{base_name}_ShotID_{today_str}.txt"
            st.subheader(f"Vorschau: {fname1}")
            st.text_area("Inhalt ShotID", res1, height=200)
            st.download_button(f"📥 Download {fname1}", res1, fname1)

            # File 2: ScopeOfWork (Nach //)
            res2 = create_subcap_txt(all_blocks, 4)
            fname2 = f"{base_name}_ScopeOfWork_{today_str}.txt"
            st.subheader(f"Vorschau: {fname2}")
            st.text_area("Inhalt ScopeOfWork", res2, height=200)
            st.download_button(f"📥 Download {fname2}", res2, fname2)
        else:
            # Standard Export falls kein // vorhanden
            res = create_subcap_txt(all_blocks, 3)
            fname = f"{base_name}_SubCap_{today_str}.txt"
            st.subheader("Preview")
            st.text_area("Export Content", res, height=400)
            st.download_button("📥 Download SubCap", res, fname)
    else:
        st.warning("Keine passenden * LOC: Einträge gefunden.")
