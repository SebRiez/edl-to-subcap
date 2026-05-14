# This script was created by Seb Riezler
# Final Version: Multi-Format Support & Dual-Download Logic

import streamlit as st
import streamlit.components.v1 as components
import re
import os
from datetime import datetime
import base64
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

def extract_loc_blocks_with_colors(edl_text, separator):
    lines = edl_text.splitlines()
    blocks = []
    last_src_start = last_src_end = None
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

def tc_to_srt(tc):
    hh, mm, ss, ff = map(int, tc.split(":"))
    ms = int((ff / 25) * 1000)
    return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"

def format_content(blocks, part_index, fmt):
    if fmt == "Avid SubCap (.txt)":
        output = ["<begin subtitles>\n"]
        for b in blocks:
            if b[part_index]: output.append(f"{b[0]} {b[1]}\n{b[part_index]}\n")
        output.append("<end subtitles>\n")
        return "\n".join(output), "text/plain", "txt"
    
    elif fmt == "SRT (.srt)":
        lines = []
        for i, b in enumerate([x for x in blocks if x[part_index]], 1):
            lines.append(f"{i}\n{tc_to_srt(b[0])} --> {tc_to_srt(b[1])}\n{b[part_index]}\n")
        return "\n".join(lines), "text/plain", "srt"

    elif fmt == "VTT (.vtt)":
        lines = ["WEBVTT\n\n"]
        for b in blocks:
            if b[part_index]:
                start = tc_to_srt(b[0]).replace(",", ".")
                end = tc_to_srt(b[1]).replace(",", ".")
                lines.append(f"{start} --> {end}\n{b[part_index]}\n")
        return "\n".join(lines), "text/vtt", "vtt"
    
    elif fmt == "CSV (.csv)":
        lines = ["In,Out,Content"]
        for b in blocks:
            if b[part_index]: lines.append(f'{b[0]},{b[1]},"{b[part_index]}"')
        return "\n".join(lines), "text/csv", "csv"

    elif fmt == "JSON (.json)":
        data = [{"in": b[0], "out": b[1], "content": b[part_index]} for b in blocks if b[part_index]]
        return json.dumps(data, indent=4), "application/json", "json"

    elif fmt == "Marker XML (.xml)":
        # Erstellt eine XML-Struktur, die von NLEs (Premiere/Resolve) gelesen werden kann
        root = ET.Element("Sequence", version="5")
        markers_node = ET.SubElement(root, "Markers")
        for i, b in enumerate([x for x in blocks if x[part_index]], 1):
            marker = ET.SubElement(markers_node, "Marker")
            ET.SubElement(marker, "In").text = b[0]
            ET.SubElement(marker, "Out").text = b[1]
            ET.SubElement(marker, "Name").text = b[part_index]
            ET.SubElement(marker, "Comment").text = f"Part {part_index-2} Export"
            ET.SubElement(marker, "Color").text = b[2]
        
        # XML hübsch formatieren
        xml_str = ET.tostring(root, encoding="utf-8")
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
        return pretty_xml, "application/xml", "xml"
    
    return "", "text/plain", "txt"

# --- Streamlit UI Setup ---
st.set_page_config(layout="wide", page_title="EDL Subtitle Exporter")
st.title("EDL → Subtitle & Marker Exporter")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])
st.divider()

# --- Settings ---
st.subheader("Split & Naming Settings")
c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1: user_separator = st.text_input("Separator", value="//")
with c2: suffix_part1 = st.text_input("Suffix Part 1", value="ShotIDs")
with c3: suffix_part2 = st.text_input("Suffix Part 2", value="Scopes")
with c4: export_format = st.selectbox("Export Format", [
    "Avid SubCap (.txt)", 
    "SRT (.srt)", 
    "VTT (.vtt)", 
    "CSV (.csv)", 
    "JSON (.json)", 
    "Marker XML (.xml)"
])

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
        
        res1, mime1, ext1 = format_content(all_blocks, 3, export_format)
        res2, mime2, ext2 = format_content(all_blocks, 4, export_format)
        
        fname1 = f"{base_name}_{suffix_part1}_{today}.{ext1}"
        fname2 = f"{base_name}_{suffix_part2}_{today}.{ext2}"

        # Preview Section
        col_preview1, col_preview2 = st.columns(2)
        with col_preview1:
            st.markdown(f"**Preview: {fname1}**")
            st.text_area("Content 1", res1, height=250, key="prev1")
        with col_preview2:
            st.markdown(f"**Preview: {fname2}**")
            st.text_area("Content 2", res2, height=250, key="prev2")

        st.divider()

        # --- Multi-Download JavaScript ---
        b64_1 = base64.b64encode(res1.encode()).decode()
        b64_2 = base64.b64encode(res2.encode()).decode()

        dl_script = f"""
            <script>
            function downloadFiles() {{
                const files = [
                    {{ name: "{fname1}", data: "data:{mime1};base64,{b64_1}" }},
                    {{ name: "{fname2}", data: "data:{mime2};base64,{b64_2}" }}
                ];
                files.forEach((file, index) => {{
                    setTimeout(() => {{
                        const link = document.createElement("a");
                        link.href = file.data;
                        link.download = file.name;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }}, index * 400); // 400ms delay to ensure browser handles dual download
                }});
            }}
            </script>
            <div style="text-align: center;">
                <button onclick="downloadFiles()" style="
                    background-color: #ff4b4b; 
                    color: white; 
                    padding: 15px 32px; 
                    border: none; 
                    border-radius: 8px; 
                    cursor: pointer; 
                    font-size: 16px;
                    font-weight: bold;
                    width: 100%;
                ">
                    📥 Download Both {ext1.upper()} Files
                </button>
            </div>
        """
        components.html(dl_script, height=100)
        st.info("💡 Pro Tip: When the browser asks, select 'Allow multiple downloads' for this site.")
    else:
        st.warning("No valid Locator blocks found. Please check your EDL and Separator.")
