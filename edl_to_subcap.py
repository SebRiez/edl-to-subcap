# This script was created by Seb Riezler

import streamlit as st
import re
import os
from datetime import datetime
from collections import Counter

def extract_loc_blocks_with_colors(edl_text):
    """
    Extracts LOC lines with SRC IN/OUT timecodes and color filtering.
    Returns list of (start_tc, end_tc, color, comment)
    """
    lines = edl_text.splitlines()
    blocks = []

    last_src_start = None
    last_src_end = None

    timecode_pattern = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
    loc_full_pattern = re.compile(
        r"\* ?LOC:\s*\d{2}:\d{2}:\d{2}:\d{2}\s+(\S+)\s+(.*)", re.IGNORECASE
    )

    for line in lines:
        timecodes = timecode_pattern.findall(line)

        if len(timecodes) >= 4:
            last_src_start = timecodes[-2]
            last_src_end = timecodes[-1]

        if "*LOC:" in line.upper() or "* LOC:" in line.upper():
            match = loc_full_pattern.search(line)
            if match and last_src_start and last_src_end:
                color = match.group(1).strip().upper()
                comment = match.group(2).strip()
                blocks.append((last_src_start, last_src_end, color, comment))
                last_src_start = last_src_end = None

    return blocks

def create_subcap_text(blocks):
    """Creates SubCap-formatted subtitle text."""
    output = ["<begin subtitles>\n"]
    for start, end, _, text in blocks:
        output.append(f"{start} {end}\n{text}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

# Streamlit UI
st.title("EDL → SubCap Converter (with color filter and colors in filename)")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = uploaded_file.read().decode("latin1")

    all_blocks = extract_loc_blocks_with_colors(content)

    if all_blocks:
        # Count entries per color
        color_counts = Counter(color for _, _, color, _ in all_blocks)
        detected_colors = sorted(color_counts)

        st.subheader("Select locator colors to include:")
        selected_colors = []
        for color in detected_colors:
            count = color_counts[color]
            if st.checkbox(f"{color} ({count})", value=True):
                selected_colors.append(color)

        # Filter by selected colors
        filtered_blocks = [b for b in all_blocks if b[2] in selected_colors]

        if filtered_blocks:
            subcap_text = create_subcap_text(filtered_blocks)

            # Build filename with selected colors
            base_name = os.path.splitext(uploaded_file.name)[0]
            today_str = datetime.now().strftime("%y%m%d")
            color_suffix = "_".join(selected_colors) if selected_colors else "ALL"
            export_filename = f"{base_name}_{color_suffix}_SubCaps_{today_str}.txt"

            st.subheader("Preview (SubCap Format)")
            st.text_area("SubCap File", subcap_text, height=400)

            st.download_button(
                label="📥 Download SubCap File",
                data=subcap_text,
                file_name=export_filename,
                mime="text/plain"
            )
        else:
            st.warning("No LOC entries match selected colors.")
    else:
        st.error("⚠️ No matching * LOC: comments found.")
