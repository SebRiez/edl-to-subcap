import streamlit as st
import streamlit.components.v1 as components
import re
import os
import json
import base64
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

DEFAULT_FPS = 25  # fallback; can be extended to auto-detect from EDL header
TIMECODE_RE = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
LOC_RE = re.compile(r"\* ?LOC:\s*\d{2}:\d{2}:\d{2}:\d{2}\s+(\S+)\s+(.*)", re.IGNORECASE)


# ─────────────────────────────────────────────
# Core parsing
# ─────────────────────────────────────────────

def extract_loc_blocks(
    edl_text: str,
    separator: str | None,
    split_enabled: bool,
    separate_marker: bool,
    fps: int = DEFAULT_FPS,
) -> list[tuple]:
    """
    Parse LOC markers from an EDL and return a list of tuples:
      (src_in, src_out, color, part1, part2, part3)

    - part1: ShotID / left token (or full comment when split disabled)
    - part2: right side of separator  (empty when split disabled)
    - part3: prefix tokens before part1 (only when separate_marker=True)
    """
    blocks = []
    last_src_in = last_src_out = None

    for line in edl_text.splitlines():
        # Track the most recent edit-line timecodes (4 fields: rec-in/out + src-in/out).
        # Do NOT skip with continue — a LOC marker never shares a line with 4 timecodes,
        # but we must fall through so the LOC check below still runs on every line.
        tcs = TIMECODE_RE.findall(line)
        if len(tcs) >= 4:
            last_src_in, last_src_out = tcs[-2], tcs[-1]

        upper = line.upper()
        if "*LOC:" not in upper and "* LOC:" not in upper:
            continue

        match = LOC_RE.search(line)
        if not (match and last_src_in and last_src_out):
            continue  # skip malformed or orphaned LOC lines

        color = match.group(1).strip().upper()
        comment = match.group(2).strip()

        if split_enabled and separator and separator in comment:
            left, part2 = (s.strip() for s in comment.split(separator, 1))
            if separate_marker:
                tokens = left.split()
                part1 = tokens[-1] if tokens else left
                part3 = " ".join(tokens[:-1])
            else:
                part1, part3 = left, ""
        else:
            part1, part2, part3 = comment, "", ""

        blocks.append((last_src_in, last_src_out, color, part1, part2, part3))
        last_src_in = last_src_out = None  # consume — prevent stale re-use

    return blocks


# ─────────────────────────────────────────────
# Timecode helpers
# ─────────────────────────────────────────────

def tc_to_srt(tc: str, fps: int = DEFAULT_FPS) -> str:
    """Convert a drop/non-drop SMPTE timecode to SRT timestamp (HH:MM:SS,mmm)."""
    hh, mm, ss, ff = map(int, tc.split(":"))
    ms = round(ff / fps * 1000)
    return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"


# ─────────────────────────────────────────────
# Formatters — one function per format
# ─────────────────────────────────────────────

def _active(blocks: list[tuple], idx: int) -> list[tuple]:
    """Filter blocks where the target part is non-empty."""
    return [b for b in blocks if b[idx]]


def fmt_subcap(blocks: list[tuple], idx: int, **_) -> tuple[str, str, str]:
    lines = ["<begin subtitles>\n"]
    for b in _active(blocks, idx):
        lines.append(f"{b[0]} {b[1]}\n{b[idx]}\n")
    lines.append("<end subtitles>\n")
    return "\n".join(lines), "text/plain", "txt"


def fmt_srt(blocks: list[tuple], idx: int, fps: int = DEFAULT_FPS, **_) -> tuple[str, str, str]:
    lines = []
    for i, b in enumerate(_active(blocks, idx), 1):
        lines.append(f"{i}\n{tc_to_srt(b[0], fps)} --> {tc_to_srt(b[1], fps)}\n{b[idx]}\n")
    return "\n".join(lines), "text/plain", "srt"


def fmt_vtt(blocks: list[tuple], idx: int, fps: int = DEFAULT_FPS, **_) -> tuple[str, str, str]:
    lines = ["WEBVTT\n\n"]
    for b in _active(blocks, idx):
        start = tc_to_srt(b[0], fps).replace(",", ".")
        end = tc_to_srt(b[1], fps).replace(",", ".")
        lines.append(f"{start} --> {end}\n{b[idx]}\n")
    return "\n".join(lines), "text/vtt", "vtt"


def fmt_csv(blocks: list[tuple], idx: int, **_) -> tuple[str, str, str]:
    rows = ["In,Out,Content"] + [f'{b[0]},{b[1]},"{b[idx]}"' for b in _active(blocks, idx)]
    return "\n".join(rows), "text/csv", "csv"


def fmt_json(blocks: list[tuple], idx: int, **_) -> tuple[str, str, str]:
    data = [{"in": b[0], "out": b[1], "content": b[idx]} for b in _active(blocks, idx)]
    return json.dumps(data, indent=4), "application/json", "json"


def fmt_xml(blocks: list[tuple], idx: int, **_) -> tuple[str, str, str]:
    root = ET.Element("Sequence", version="5")
    markers_node = ET.SubElement(root, "Markers")
    for b in _active(blocks, idx):
        marker = ET.SubElement(markers_node, "Marker")
        ET.SubElement(marker, "In").text = b[0]
        ET.SubElement(marker, "Out").text = b[1]
        ET.SubElement(marker, "Name").text = b[idx]
        ET.SubElement(marker, "Color").text = b[2]
    raw = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(raw).toprettyxml(indent="  "), "application/xml", "xml"


FORMAT_REGISTRY: dict[str, callable] = {
    "Avid SubCap (.txt)": fmt_subcap,
    "SRT (.srt)": fmt_srt,
    "VTT (.vtt)": fmt_vtt,
    "CSV (.csv)": fmt_csv,
    "JSON (.json)": fmt_json,
    "Marker XML (.xml)": fmt_xml,
}


def format_content(blocks: list[tuple], part_index: int, fmt: str, fps: int = DEFAULT_FPS):
    fn = FORMAT_REGISTRY.get(fmt, fmt_subcap)
    return fn(blocks, part_index, fps=fps)


# ─────────────────────────────────────────────
# Download helper
# ─────────────────────────────────────────────

def build_download_button_html(files: list[tuple[str, str, str]]) -> str:
    """
    Build an HTML+JS multi-file download button.
    files: list of (filename, mime, content_str)
    """
    js_array_items = []
    for fname, mime, content in files:
        b64 = base64.b64encode(content.encode()).decode()
        js_array_items.append(f'{{n:{json.dumps(fname)},d:"data:{mime};base64,{b64}"}}')

    return f"""
        <script>
        function dlAll() {{
            const files = [{",".join(js_array_items)}];
            files.forEach((f, i) => {{
                setTimeout(() => {{
                    const a = document.createElement("a");
                    a.href = f.d;
                    a.download = f.n;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }}, i * 400);
            }});
        }}
        </script>
        <div style="display:flex;justify-content:center;width:100%;">
            <button onclick="dlAll()" style="
                background:#007A5A;color:white;padding:12px;border:none;
                border-radius:8px;cursor:pointer;font-weight:bold;
                width:50%;min-width:300px;
                font-family:'Source Sans Pro',sans-serif;">
                Convert &amp; Download Files
            </button>
        </div>
    """


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.set_page_config(page_title="EDL → Subcap", layout="wide")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #090b10; color: #e2e8f0; }
    [data-testid="stHeader"]           { background-color: transparent; }
    [data-testid="block-container"]    { max-width: 50%; padding: 2rem; }

    /* Prevent column wrapping */
    [data-testid="stHorizontalBlock"]                        { flex-wrap: nowrap; }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] { min-width: 0; flex: 1 1 0%; }

    .title-text    { text-align:center; font-size:2.5rem; font-weight:700; color:#ffffff; }
    .subtitle-text { text-align:center; font-size:1rem;   color:#94a3b8; margin-bottom:2rem; }
    .footer-text   { text-align:center; font-size:0.85rem; color:#64748b; margin-top:1rem; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color:#11141d; border:1px solid #1e2433;
        border-radius:12px; padding:1rem;
    }
    [data-testid="stFileUploadDropzone"] {
        background-color:transparent; border:1px dashed #334155; border-radius:12px;
    }
    .stTextInput input,
    .stSelectbox > div > div > div,
    .stTextArea textarea {
        background-color:#1e2433; color:white;
        border:1px solid #334155; border-radius:8px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">EDL → Subcap</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Convert EDL files into subtitles and markers</div>', unsafe_allow_html=True)

# ── Upload ──────────────────────────────────
with st.container(border=True):
    uploaded_file = st.file_uploader("Upload EDL File", type=["edl", "txt"])

st.write("")

# ── Settings ────────────────────────────────
with st.container(border=True):
    st.markdown("### Settings")

    export_format = st.selectbox("Export Format", list(FORMAT_REGISTRY))

    st.markdown("---")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        use_split = st.toggle("Enable split comment function", value=True)
    with col_t2:
        # Only render the toggle when split is enabled; default False otherwise
        separate_marker = st.toggle("Separate marker name", value=True) if use_split else False

    st.write("")

    if use_split:
        n_cols = 4 if separate_marker else 3
        cols = st.columns(n_cols)
        with cols[0]: user_separator  = st.text_input("Separator",       value="//")
        with cols[1]: suffix_part1    = st.text_input("Suffix SubCap 01", value="ShotIDs")
        with cols[2]: suffix_part2    = st.text_input("Suffix SubCap 02", value="SoW")
        suffix_part3 = ""
        if separate_marker:
            with cols[3]: suffix_part3 = st.text_input("Suffix SubCap 03", value="MarkerName")
    else:
        user_separator = None
        suffix_part1, suffix_part2, suffix_part3 = "Export", "", ""

# ── Processing & Preview ─────────────────────
if uploaded_file:
    try:
        raw = uploaded_file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    all_blocks = extract_loc_blocks(raw, user_separator, use_split, separate_marker)

    if not all_blocks:
        st.warning("No LOC markers found in the uploaded EDL.")
        st.stop()

    base_name = os.path.splitext(uploaded_file.name)[0]
    today = datetime.now().strftime("%y%m%d")

    st.write("")
    st.markdown("### Preview")

    if use_split:
        res1, mime1, ext1 = format_content(all_blocks, 3, export_format)
        res2, mime2, ext2 = format_content(all_blocks, 4, export_format)
        fname1 = f"{base_name}_{suffix_part1}_{today}.{ext1}"
        fname2 = f"{base_name}_{suffix_part2}_{today}.{ext2}"

        n_preview = 3 if separate_marker else 2
        preview_cols = st.columns(n_preview)

        with preview_cols[0]: st.text_area(f"Name: {fname1}", res1, height=250)
        with preview_cols[1]: st.text_area(f"Name: {fname2}", res2, height=250)

        dl_files = [(fname1, mime1, res1), (fname2, mime2, res2)]

        if separate_marker:
            res3, mime3, ext3 = format_content(all_blocks, 5, export_format)
            fname3 = f"{base_name}_{suffix_part3}_{today}.{ext3}"
            with preview_cols[2]: st.text_area(f"Name: {fname3}", res3, height=250)
            dl_files.append((fname3, mime3, res3))

        st.write("")
        components.html(build_download_button_html(dl_files), height=80)

    else:
        res, mime, ext = format_content(all_blocks, 3, export_format)
        fname = f"{base_name}_{suffix_part1}_{today}.{ext}"
        st.text_area(f"Name: {fname}", res, height=300)
        st.write("")
        _, btn_col, _ = st.columns([1.5, 1, 1.5])
        with btn_col:
            st.download_button("Convert & Download", res, fname, mime=mime, use_container_width=True)

st.markdown('<div class="footer-text">Processing happens locally in your browser</div>', unsafe_allow_html=True)
