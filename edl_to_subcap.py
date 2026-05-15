import streamlit as st
import streamlit.components.v1 as components
import re
import os
from datetime import datetime
import base64
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

# --- Logic ---
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

# --- UI Setup ---
st.set_page_config(page_title="EDL → Subcap", layout="centered")

st.markdown("""
<style>
    /* Dark Theme Base */
    [data-testid="stAppViewContainer"] {
        background-color: #090b10;
        color: #e2e8f0;
    }
    [data-testid="stHeader"] {
        background-color: transparent;
    }
    
    /* Typography */
    .title-text {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #ffffff;
    }
    .subtitle-text {
        text-align: center;
        font-size: 1rem;
        color: #94a3b8;
        margin-bottom: 2rem;
    }
    
    /* Containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #11141d;
        border: 1px solid #1e2433;
        border-radius: 12px;
        padding: 1rem;
    }
    
    /* File Uploader styling */
    [data-testid="stFileUploadDropzone"] {
        background-color: transparent;
        border: 1px dashed #334155;
        border-radius: 12px;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #007A5A;
        background-color: #111822;
    }
    
    /* Inputs */
    .stTextInput input, .stSelectbox > div > div > div {
        background-color: #1e2433 !important;
        color: white !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    
    /* Primary Button override (native) */
    .stDownloadButton > button {
        background-color: #007A5A !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        width: 100% !important;
        font-weight: bold !important;
        padding: 0.75rem !important;
    }
    .stDownloadButton > button:hover {
        background-color: #006046 !important;
    }
    
    /* Footer */
    .footer-text {
        text-align: center;
        font-size: 0.85rem;
        color: #64748b;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">EDL → Subcap</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Convert EDL files into subtitles and markers</div>', unsafe_allow_html=True)

with st.container(border=True):
    uploaded_file = st.file_uploader("Upload EDL File", type=["edl", "txt"], help="Max 200MB")

st.write("") # Spacing

with st.container(border=True):
    st.markdown("### ⚙️ Settings")
    st.write("")
    
    export_format = st.selectbox(
        "Export Formats", 
        ["Avid SubCap (.txt)", "SRT (.srt)", "VTT (.vtt)", "CSV (.csv)", "JSON (.json)", "Marker XML (.xml)"]
    )
    
    st.markdown("---")
    
    use_split = st.toggle("Enable Split Function", value=True)
    
    if use_split:
        c1, c2, c3 = st.columns(3)
        with c1: user_separator = st.text_input("Separator", value="//")
        with c2: suffix_part1 = st.text_input("Name SubCapFile 01", value="ShotIDs")
        with c3: suffix_part2 = st.text_input("Name  SubCapFile 02", value="SoW")
    else:
        user_separator = None
        suffix_part1 = "Export"

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

            b64_1, b64_2 = base64.b64encode(res1.encode()).decode(), base64.b64encode(res2.encode()).decode()
            dl_btn = f"""
                <script>
                function dl() {{
                    const files = [{{n:"{fname1}",d:"data:{mime1};base64,{b64_1}"}},{{n:"{fname2}",d:"data:{mime2};base64,{b64_2}"}}];
                    files.forEach((f,i)=>{{setTimeout(()=>{{const a=document.createElement("a");a.href=f.d;a.download=f.n;document.body.appendChild(a);a.click();document.body.removeChild(a);}},i*400);}});
                }}
                </script>
                <button onclick="dl()" style="background:#007A5A;color:white;padding:12px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;width:100%;font-family:inherit;">
                    <svg style="width:16px;height:16px;vertical-align:middle;margin-right:8px" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Convert & Download
                </button>
            """
            components.html(dl_btn, height=60)
        else:
            res, mime, ext = format_content(all_blocks, 3, export_format)
            fname = f"{base_name}_{suffix_part1}_{today}.{ext}"
            st.download_button("📥 Convert & Download", res, fname, mime=mime, use_container_width=True)

st.markdown('<div class="footer-text">Processing happens locally in your browser</div>', unsafe_allow_html=True)
