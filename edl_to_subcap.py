# This script was created by Seb Riezler

import streamlit as st
import re
import os
from datetime import datetime
from collections import Counter
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
                comment = match.group(2).strip()
                blocks.append((last_src_start, last_src_end, color, comment))
                last_src_start = last_src_end = None
    return blocks

def tc_to_srt(tc):
    hh, mm, ss, ff = map(int, tc.split(":"))
    ms = int((ff / 25) * 1000)
    return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"

def tc_to_vtt(tc):
    hh, mm, ss, ff = map(int, tc.split(":"))
    ms = int((ff / 25) * 1000)
    return f"{hh:02}:{mm:02}:{ss:02}.{ms:03}"

def create_subcap_txt(blocks):
    output = ["<begin subtitles>\n"]
    for start, end, _, text in blocks:
        output.append(f"{start} {end}\n{text}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

def create_marker_txt(blocks, colors_enabled=False):
    lines = []
    for i, (start, end, color, text) in enumerate(blocks, 1):
        line = f"{i:03}  {start}  {color if colors_enabled else ''}  {text}".strip()
        lines.append(line)
    return "\n".join(lines)

def create_scriptsync_txt(blocks):
    return "\n".join([text for _, _, _, text in blocks])

def create_srt(blocks):
    lines = []
    for i, (start, end, _, text) in enumerate(blocks, 1):
        lines.append(f"{i}")
        lines.append(f"{tc_to_srt(start)} --> {tc_to_srt(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)

def create_vtt(blocks):
    lines = ["WEBVTT\n"]
    for (start, end, _, text) in blocks:
        lines.append(f"{tc_to_vtt(start)} --> {tc_to_vtt(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)

def create_sbv(blocks):
    lines = []
    for (start, end, _, text) in blocks:
        lines.append(f"{tc_to_srt(start).replace(',', '.')} , {tc_to_srt(end).replace(',', '.')}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)

def create_marker_xml(blocks):
    root = ET.Element("Markers")
    for i, (start, end, color, text) in enumerate(blocks, 1):
        marker = ET.SubElement(root, "Marker")
        ET.SubElement(marker, "Number").text = str(i)
        ET.SubElement(marker, "In").text = start
        ET.SubElement(marker, "Out").text = end
        ET.SubElement(marker, "Color").text = color
        ET.SubElement(marker, "Text").text = text
    return ET.tostring(root, encoding="unicode")

# Streamlit UI
st.title("EDL → Multi-Format Subtitle Exporter (incl. XML)")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])

export_format = st.selectbox("Choose export format", [
    "Avid SubCap (.txt)",
    "Marker Text (.txt) [8 Colors]",
    "Marker Text (.txt) [16 Colors]",
    "Marker XML (.xml) [8 Colors]",
    "Marker XML (.xml) [16 Colors]",
    "ScriptSync (.txt)",
    "SRT (SubRip)",
    "VTT (Web Video Text)",
    "SBV (YouTube SubViewer)"
])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = uploaded_file.read().decode("latin1")

    all_blocks = extract_loc_blocks_with_colors(content)

    if all_blocks:
        base_name = os.path.splitext(uploaded_file.name)[0]
        today_str = datetime.now().strftime("%y%m%d")

        if "SubCap" in export_format:
            result_text = create_subcap_txt(all_blocks)
            suffix = "SubCap"
            ext = "txt"
        elif "Marker Text" in export_format:
            colors_enabled = "16" in export_format
            result_text = create_marker_txt(all_blocks, colors_enabled)
            suffix = "Marker16" if colors_enabled else "Marker8"
            ext = "txt"
        elif "Marker XML" in export_format:
            result_text = create_marker_xml(all_blocks)
            suffix = "XML16" if "16" in export_format else "XML8"
            ext = "xml"
        elif "ScriptSync" in export_format:
            result_text = create_scriptsync_txt(all_blocks)
            suffix = "ScriptSync"
            ext = "txt"
        elif "SRT" in export_format:
            result_text = create_srt(all_blocks)
            suffix = "SRT"
            ext = "srt"
        elif "VTT" in export_format:
            result_text = create_vtt(all_blocks)
            suffix = "VTT"
            ext = "vtt"
        elif "SBV" in export_format:
            result_text = create_sbv(all_blocks)
            suffix = "SBV"
            ext = "sbv"

        export_filename = f"{base_name}_{suffix}_{today_str}.{ext}"

        st.subheader("Preview")
        st.text_area("Export Content", result_text, height=400)

        st.download_button(
            label="📥 Download Export File",
            data=result_text,
            file_name=export_filename,
            mime="text/plain"
        )
    else:
        st.warning("No matching * LOC: entries found.")
