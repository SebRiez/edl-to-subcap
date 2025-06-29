# This script was created by Seb Riezler
# c 2025

import streamlit as st
import re
import os
from datetime import datetime

def extract_loc_blocks(edl_text):
    """
    Extracts LOC lines with SRC IN/OUT timecodes.
    Uses only the comment after the color name.
    """
    lines = edl_text.splitlines()
    blocks = []

    last_src_start = None
    last_src_end = None

    timecode_pattern = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
    loc_comment_pattern = re.compile(
        r"\* ?LOC:\s*\d{2}:\d{2}:\d{2}:\d{2}\s+\S+\s+(.*)", re.IGNORECASE
    )

    for line in lines:
        timecodes = timecode_pattern.findall(line)

        if len(timecodes) >= 4:
            last_src_start = timecodes[-2]
            last_src_end = timecodes[-1]

        if "*LOC:" in line.upper() or "* LOC:" in line.upper():
            match = loc_comment_pattern.search(line)
            if match and last_src_start and last_src_end:
                comment = match.group(1).strip()
                blocks.append((last_src_start, last_src_end, comment))
                last_src_start = last_src_end = None

    return blocks

def create_subcap_text(blocks):
    """Creates SubCap-formatted subtitle text."""
    output = ["<begin subtitles>\n"]
    for start, end, text in blocks:
        output.append(f"{start} {end}\n{text}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

# Streamlit UI
st.title("EDL → SubCap Converter")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])

if uploaded_file is not None:
    # Dynamically create filename
    base_name = os.path.splitext(uploaded_file.name)[0]
    today_str = datetime.now().strftime("%y%m%d")
    export_filename = f"{base_name}_SubCaps_{today_str}.txt"

    try:
        content = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = uploaded_file.read().decode("latin1")

    blocks = extract_loc_blocks(content)

    if blocks:
        subcap_text = create_subcap_text(blocks)

        st.subheader("Preview (SubCap Format)")
        st.text_area("SubCap File", subcap_text, height=400)

        st.download_button(
            label="📥 Download SubCap File",
            data=subcap_text,
            file_name=export_filename,
            mime="text/plain"
        )
    else:
        st.error("⚠️ No matching * LOC: comments found.")
