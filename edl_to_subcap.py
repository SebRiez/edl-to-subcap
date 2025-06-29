# Dieses Script wurde erstellt von Seb Riezler
# 2025

import streamlit as st
import re

def extract_loc_blocks(edl_text):
    """
    Extrahiert LOC-Zeilen mit SRC IN/OUT Timecodes.
    Verwendet nur den Kommentartext nach dem Farbnamen.
    """
    lines = edl_text.splitlines()
    blocks = []

    last_src_start = None
    last_src_end = None

    timecode_pattern = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")

    # Erkennung von *LOC: oder * LOC:, extrahiere Kommentar nach Farbe
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
    """Erstellt SubCap-formatierte Textdatei aus LOC-Blöcken."""
    output = ["<begin subtitles>\n"]
    for start, end, text in blocks:
        output.append(f"{start} {end}\n{text}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

# Streamlit UI
st.title("EDL → SubCap Converter")

uploaded_file = st.file_uploader("EDL-Datei hochladen", type=["edl", "txt"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = uploaded_file.read().decode("latin1")

    blocks = extract_loc_blocks(content)

    if blocks:
        subcap_text = create_subcap_text(blocks)

        st.subheader("Vorschau (SubCap Format)")
        st.text_area("SubCap-Datei", subcap_text, height=400)

        st.download_button(
            label="📥 SubCap-Datei herunterladen",
            data=subcap_text,
            file_name="subcap_export.txt",
            mime="text/plain"
        )
    else:
        st.error("⚠️ Keine passenden * LOC: Kommentare gefunden.")
