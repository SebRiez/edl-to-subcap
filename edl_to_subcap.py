import streamlit as st
import re

def extract_loc_blocks(edl_text):
    """
    Extrahiert LOC-Zeilen mit SRC IN/OUT Timecodes und filtert den MUM-Code.
    Gibt Liste von (start_tc, end_tc, mum_code) zurück.
    """
    lines = edl_text.splitlines()
    blocks = []

    last_src_start = None
    last_src_end = None

    timecode_pattern = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
    mum_pattern = re.compile(r"\bMUM_\d{3}_\d{4}\b")

    for line in lines:
        timecodes = timecode_pattern.findall(line)

        # Merke SRC IN/OUT Timecodes (die letzten beiden Timecodes in der Zeile)
        if len(timecodes) >= 4:
            last_src_start = timecodes[-2]
            last_src_end = timecodes[-1]

        # LOC-Zeile → MUM extrahieren
        if "*LOC:" in line.upper() and last_src_start and last_src_end:
            match = mum_pattern.search(line)
            if match:
                mum_code = match.group(0)
                blocks.append((last_src_start, last_src_end, mum_code))
            last_src_start = last_src_end = None  # zurücksetzen

    return blocks

def create_subcap_text(blocks):
    """Erstellt SubCap-formatierte Textdatei aus LOC-Blöcken."""
    output = ["<begin subtitles>\n"]
    for start, end, text in blocks:
        output.append(f"{start} {end}\n{text}\n")
    output.append("<end subtitles>\n")
    return "\n".join(output)

# Streamlit UI
st.title("EDL → SubCap Konverter – nur MUM_###_#### aus LOC:")

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
        st.error("⚠️ Keine passenden * LOC: Einträge mit MUM_###_#### gefunden.")
