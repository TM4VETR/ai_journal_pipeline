import re
import xml.etree.ElementTree as ET
from pathlib import Path

_CUSTOM_BLOCK_RE = re.compile(r'(\b{key}\b)\s*\{{([^}}]*)\}}')


def _detect_page_ns(root: ET.Element) -> dict:
    """
    Detect PAGE namespace from root tag like:
      "{http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15}PcGts"
    Returns dict usable in ElementTree find/findall: {"pc": "<uri>"}.
    """
    if root.tag.startswith("{") and "}" in root.tag:
        uri = root.tag.split("}", 1)[0][1:]
        return {"pc": uri}
    # Fallback: no namespace (rare)
    return {"pc": ""}


def iter_pagexml_files(project_dir: Path):
    """Yields all PAGE-XML files in the given project directory."""
    yield from project_dir.rglob("*.xml")


def get_word_text(word_el: ET.Element, ns: dict) -> str:
    """
    Extract text of a Word element in PAGE-XML.
    Prefer Word/TextEquiv/Unicode; fall back to concatenated Glyph unicodes if needed.
    """
    # 1) Word-level TextEquiv (most common)
    unicode_el = word_el.find("./pc:TextEquiv/pc:Unicode", ns)
    if unicode_el is not None and (unicode_el.text or "").strip():
        return unicode_el.text.strip()

    # 2) Some files only provide glyph-level text
    glyph_unicodes = []
    for g_u in word_el.findall(".//pc:Glyph/pc:TextEquiv/pc:Unicode", ns):
        t = (g_u.text or "").strip()
        if t:
            glyph_unicodes.append(t)

    return "".join(glyph_unicodes).strip()


def load_words_from_pagexml(xml_path: Path):
    """Loads words from a PAGE-XML file."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = _detect_page_ns(root)

    word_elements = root.findall(".//pc:Word", ns)

    words = []
    aligned_word_elements = []
    for w_el in word_elements:
        txt = get_word_text(w_el, ns)
        if txt:
            words.append(txt)
            aligned_word_elements.append(w_el)

    return tree, aligned_word_elements, words, ns


def upsert_custom_field(custom: str, key: str, value: str) -> str:
    """
    PAGE 'custom' is a free-form string often like:
      "structure {type:header;} readingOrder {index:1;}"
    We'll store:
      "job_title {value:LABEL;}"
    """
    custom = (custom or "").strip()
    block = f"{key}: {value}"

    if not custom:
        return block

    m = re.search(rf'(\b{re.escape(key)}\b)\s*\{{([^}}]*)\}}', custom.replace("\n", " "))
    if not m:
        return (custom + " " + block).strip()

    # Replace existing key-block
    start, end = m.span()
    return (custom[:start] + block + custom[end:]).strip()


def write_labels_to_pagexml(word_elements, labels):
    """ Writes labels into the 'custom' attribute of Word elements in PAGE-XML. """
    if len(word_elements) != len(labels):
        raise ValueError(f"Mismatch: {len(word_elements)} words vs {len(labels)} labels")

    for w_el, label in zip(word_elements, labels):
        old_custom = w_el.get("custom", "")
        if label.strip().upper() != "O":
            w_el.set("custom", upsert_custom_field(old_custom, "ENTITY", label))


if __name__ == "__main__":
    # Example usage
    xml_path = Path("example.xml")
    tree, word_elements, words, ns = load_words_from_pagexml(xml_path)

    print(f"Detected PAGE namespace: {ns.get('pc')}")
    print(f"Found {len(words)} words:")

    tree, word_elements, words, ns = load_words_from_pagexml(xml_path)

    print("First 10 words:")
    for i, w in enumerate(words[:10], start=1):
        print(f"{i:02d}: {w}")