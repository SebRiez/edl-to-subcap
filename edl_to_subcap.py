# This script was created by Seb Riezler
# Final Version: Multi-Format Support, Dual-Download & Optional Split Logic

import streamlit as st
import streamlit.components.v1 as components
import re
import os
from datetime import datetime
import base64
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

def extract_loc_blocks(edl_text, separator, split_enabled):
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
                
                if split_enabled and separator and separator in full_comment:
                    p1, p2 = full_comment.split(separator, 1)
                    blocks.append((last_src_start, last_src_end, color, p1.strip(), p2.strip()))
                else:
                    # Falls Split aus ist oder Separator nicht gefunden wurde: Alles in Part 1
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
        valid_blocks = [x for x in blocks if x[part_index]]
        for i, b in enumerate(valid_blocks, 1):
            lines.append(f"{i}\n{tc_to_srt(b[0])} --> {tc_to_srt(b[1])}\n{b[part_index]}\n")
        return "\n".join(lines), "text/plain", "srt"

    elif fmt == "VTT (.vtt)":
        lines = ["WEBVTT\n\n"]
        for b in blocks:
            if b[part_index]:
                start, end = tc_to_srt(b[0]).replace(",", "."), tc_to_srt(b[1]).replace(",", ".")
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
        root = ET.Element("Sequence", version="5")
        markers_node = ET.SubElement(root, "Markers")
        for b in blocks:
            if b[part_index]:
                marker = ET.SubElement(markers_node, "Marker")
                ET.SubElement(marker, "In").text = b[0]
                ET.SubElement(marker, "Out").text = b[1]
                ET.SubElement(marker, "Name").text = b[part_index]
                ET.SubElement(marker, "Color").text = b[2]
        xml_str = ET.tostring(root, encoding="utf-8")
        return minidom.parseString(xml_str).toprettyxml(indent="  "), "application/xml", "xml"
    
    return "", "text/plain", "txt"

# --- UI Layout ---
st.set_page_config(layout="wide", page_title="EDL Subtitle Exporter")
st.title("EDL → Subtitle & Marker Exporter")

uploaded_file = st.file_uploader("Upload EDL file", type=["edl", "txt"])
st.divider()

# --- Settings ---
st.subheader("Global Settings")
col_opt, col_fmt = st.columns([1, 2])
with col_opt:
    use_split = st.checkbox("Enable Split-Function (Separator)", value=True)
with col_fmt:
    export_format = st.selectbox("Export Format", ["Avid SubCap (.txt)", "SRT (.srt)", "VTT (.vtt)", "CSV (.csv)", "JSON (.json)", "Marker XML (.xml)"])

if use_split:
    st.markdown("---")
    st.subheader("Split & Naming")
    c1, c2, c3 = st.columns(3)
    with c1: user_separator = st.text_input("Separator", value="//")
    with c2: suffix_part1 = st.text_input("Suffix Part 1", value="ShotIDs")
    with c3: suffix_part2 = st.text_input("Suffix Part 2", value="Scopes")
else:
    user_separator = None
    suffix_part1 = "Export"

st.divider()

if uploaded_file:
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    all_blocks = extract_loc_blocks(content, user_separator, use_split)

    if all_blocks:
        base_name = os.path.splitext(uploaded_file.name)[0]
        today = datetime.now().strftime("%y%m%d")
        
        if use_split:
            res1, mime1, ext1 = format_content(all_blocks, 3, export_format)
            res2, mime2, ext2 = format_content(all_blocks, 4, export_format)
            fname1, fname2 = f"{base_name}_{suffix_part1}_{today}.{ext1}", f"{base_name}_{suffix_part2}_{today}.{ext1}"

            cp1, cp2 = st.columns(2)
            with cp1: st.text_area(fname1, res1, height=250)
            with cp2: st.text_area(fname2, res2, height=250)

            # JS Multi-Download
            b64_1, b64_2 = base64.b64encode(res1.encode()).decode(), base64.b64encode(res2.encode()).decode()
            dl_btn = f"""
                <script>
                function dl() {{
                    const files = [{{n:"{fname1}",d:"data:{mime1};base64,{b64_1}"}},{{n:"{fname2}",d:"data:{mime2};base64,{b64_2}"}}];
                    files.forEach((f,i)=>{{setTimeout(()=>{{const a=document.createElement("a");a.href=f.d;a.download=f.n;document.body.appendChild(a);a.click();document.body.removeChild(a);}},i*400);}});
                }}
                </script>
                <button onclick="dl()" style="background:#ff4b4b;color:white;padding:15px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;width:100%;">📥 Download Both Files</button>
            """
            components.html(dl_btn, height=80)
        else:
            res, mime, ext = format_content(all_blocks, 3, export_format)
            fname = f"{base_name}_{suffix_part1}_{today}.{ext}"
            st.text_area(fname, res, height=300)
            st.download_button(f"📥 Download {ext.upper()} File", res, fname, mime=mime, use_container_width=True)
    else:
        st.warning("No Locator blocks found.")
