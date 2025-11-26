#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch-transform CalDraCor TEI files for TextGrid / TGR alignment.

Transforms:
1. <idno type="wikidata">Q...</idno>
   -> add corresp="https://www.wikidata.org/wiki/Q..."

2. <idno type="pnd">N</idno>
   -> type="gnd"
   -> corresp="https://d-nb.info/gnd/N"

3. Ensure <langUsage><language ident="spa">Spanish</language></langUsage>
   exists in <profileDesc> (if missing).

4. In <textClass>, add three <keywords> blocks if missing:
   - BK basic classification
   - GND genre (Theaterstück)
   - TextGrid genre (drama)

5. In <respStmt>, normalize Antonio Rojas Castro's persName:
   -> <persName xml:id="rojas" corresp="https://orcid.org/0000-0002-8916-4997">
        <forename>Antonio</forename>
        <surname>Rojas Castro</surname>
      </persName>

6. In <publicationStmt>, ensure:
   - <publisher>Tracing Regularities in Pedro Calderón de la Barca's Dramatic OEuvre
     with a Computational Approach (508056339)</publisher>
   - <idno type="caldracor">FILENAME_WITHOUT_EXTENSION</idno>

7. In <profileDesc>, create <creation><date> based on standOff/listEvent:
   - Prefer <event type="written"> (when/notBefore/notAfter),
   - Fallback to <event type="print"> if no written event exists.
"""

import os
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {"tei": TEI_NS}

# Paths relative to the directory where you run this script
INPUT_DIR = "tei"
OUTPUT_DIR = "tei-updated"

os.makedirs(OUTPUT_DIR, exist_ok=True)

PUBLISHER_TEXT = (
    "Tracing Regularities in Pedro Calderón de la Barca's Dramatic OEuvre "
    "with a Computational Approach (508056339)"
)

ORCID_ROJAS = "https://orcid.org/0000-0002-8916-4997"


def add_wikidata_corresp(root):
    """Add @corresp to <idno type='wikidata'> if missing."""
    xpath_expr = '//tei:idno[@type="wikidata"]'
    for idno in root.xpath(xpath_expr, namespaces=NSMAP):
        qid = (idno.text or "").strip()
        if qid and not idno.get("corresp"):
            idno.set("corresp", f"https://www.wikidata.org/wiki/{qid}")


def convert_pnd_to_gnd(root):
    """Convert <idno type='pnd'> to type='gnd' and add @corresp."""
    xpath_expr = '//tei:idno[@type="pnd"]'
    for idno in root.xpath(xpath_expr, namespaces=NSMAP):
        num = (idno.text or "").strip()
        idno.set("type", "gnd")
        if num and not idno.get("corresp"):
            idno.set("corresp", f"https://d-nb.info/gnd/{num}")


def ensure_langusage_spanish(root):
    """Ensure <langUsage><language ident='spa'>Spanish</language></langUsage> exists."""
    for profile_desc in root.xpath("//tei:profileDesc", namespaces=NSMAP):
        lang_usage = profile_desc.find("tei:langUsage", namespaces=NSMAP)
        if lang_usage is None:
            lang_usage = etree.SubElement(profile_desc, f"{{{TEI_NS}}}langUsage")
            lang = etree.SubElement(lang_usage, f"{{{TEI_NS}}}language")
            lang.set("ident", "spa")
            lang.text = "Spanish"


def ensure_textclass_keywords(root):
    """
    In each <textClass>, add three <keywords> blocks if missing:
    1) BK basic classification
    2) GND genre Theaterstück
    3) TextGrid genre drama
    """
    for text_class in root.xpath("//tei:textClass", namespaces=NSMAP):
        # 1) BK
        if not text_class.xpath(
            'tei:keywords[@scheme="http://uri.gbv.de/terminology/bk/"]',
            namespaces=NSMAP,
        ):
            kw_bk = etree.SubElement(text_class, f"{{{TEI_NS}}}keywords")
            kw_bk.set("scheme", "http://uri.gbv.de/terminology/bk/")
            term1 = etree.SubElement(kw_bk, f"{{{TEI_NS}}}term")
            term1.set("type", "basicClassification")
            term1.set("key", "17.97")
            term1.text = "Texts by a single author"
            term2 = etree.SubElement(kw_bk, f"{{{TEI_NS}}}term")
            term2.set("type", "basicClassification")
            term2.set("key", "18.30")
            term2.text = "Spanish language and literature"

        # 2) GND genre
        if not text_class.xpath(
            'tei:keywords[@scheme="https://d-nb.info/gnd/"]',
            namespaces=NSMAP,
        ):
            kw_gnd = etree.SubElement(text_class, f"{{{TEI_NS}}}keywords")
            kw_gnd.set("scheme", "https://d-nb.info/gnd/")
            term = etree.SubElement(kw_gnd, f"{{{TEI_NS}}}term")
            term.set("type", "testament")
            term.set("ref", "http://d-nb.info/gnd/4304080-9")
            term.text = "Theaterstück"

        # 3) TextGrid genre
        if not text_class.xpath(
            'tei:keywords[@scheme="http://textgrid.info/namespaces/metadata/core/2010#genre"]',
            namespaces=NSMAP,
        ):
            kw_tg = etree.SubElement(text_class, f"{{{TEI_NS}}}keywords")
            kw_tg.set("scheme", "http://textgrid.info/namespaces/metadata/core/2010#genre")
            term = etree.SubElement(kw_tg, f"{{{TEI_NS}}}term")
            term.set("type", "genre-tg")
            term.text = "drama"


def normalize_persname_rojas(root):
    """
    Normalize Antonio Rojas Castro's persName in respStmt:

    Before (examples):
      <persName xml:id="rojas">Rojas Castro, Antonio</persName>
      <persName>Antonio Rojas Castro</persName>

    After:
      <persName xml:id="rojas" corresp="ORCID_ROJAS">
        <forename>Antonio</forename>
        <surname>Rojas Castro</surname>
      </persName>
    """
    xpath_expr = "//tei:respStmt/tei:persName"
    for pers in root.xpath(xpath_expr, namespaces=NSMAP):
        full_text = " ".join(pers.itertext()).strip().replace("\xa0", " ")
        xml_id = pers.get(f"{{{XML_NS}}}id")

        # Heurística: si xml:id es 'rojas' o el texto contiene 'Rojas' y 'Antonio'
        if not (xml_id == "rojas" or ("Rojas" in full_text and "Antonio" in full_text)):
            continue

        # Limpiamos y reconstruimos siempre, para unificar
        pers.clear()
        pers.set(f"{{{XML_NS}}}id", "rojas")
        pers.set("corresp", ORCID_ROJAS)

        forename = etree.SubElement(pers, f"{{{TEI_NS}}}forename")
        forename.text = "Antonio"
        surname = etree.SubElement(pers, f"{{{TEI_NS}}}surname")
        surname.text = "Rojas Castro"


def ensure_publisher(root):
    """Ensure publisher has the project name."""
    pub_stmts = root.xpath("//tei:fileDesc/tei:publicationStmt", namespaces=NSMAP)
    if not pub_stmts:
        return
    pub_stmt = pub_stmts[0]

    publisher = pub_stmt.find("tei:publisher", namespaces=NSMAP)
    if publisher is None:
        publisher = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}publisher")

    publisher.text = PUBLISHER_TEXT


def ensure_caldracor_id(root, basename):
    """
    Add <idno type='caldracor'>BASENAME</idno> in <publicationStmt> if not present.
    BASENAME is the filename without extension.
    """
    pub_stmts = root.xpath("//tei:fileDesc/tei:publicationStmt", namespaces=NSMAP)
    if not pub_stmts:
        return
    pub_stmt = pub_stmts[0]

    existing = pub_stmt.xpath('tei:idno[@type="caldracor"]', namespaces=NSMAP)
    if existing:
        return

    idno = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}idno")
    idno.set("type", "caldracor")
    idno.text = basename


def ensure_creation_from_events(root):
    """
    Create <creation><date> in <profileDesc> based on standOff/listEvent:

    Priority:
    1) <event type='written'>
    2) if none, <event type='print'>

    Copy @when, @notBefore, @notAfter from the chosen event into <date>.
    If creation/date already exists, do nothing.
    """
    profile_desc = root.find(".//tei:profileDesc", namespaces=NSMAP)
    if profile_desc is None:
        return

    # If creation already exists, we don't touch it
    existing_creation = profile_desc.find("tei:creation", namespaces=NSMAP)
    if existing_creation is not None:
        return

    events_written = root.xpath(
        "//tei:standOff/tei:listEvent/tei:event[@type='written']",
        namespaces=NSMAP,
    )
    event_el = events_written[0] if events_written else None

    if event_el is None:
        events_print = root.xpath(
            "//tei:standOff/tei:listEvent/tei:event[@type='print']",
            namespaces=NSMAP,
        )
        event_el = events_print[0] if events_print else None

    if event_el is None:
        # No suitable event found; do nothing
        return

    creation = etree.SubElement(profile_desc, f"{{{TEI_NS}}}creation")
    date = etree.SubElement(creation, f"{{{TEI_NS}}}date")

    # Copy date-related attributes
    for attr in ("when", "notBefore", "notAfter"):
        val = event_el.get(attr)
        if val:
            date.set(attr, val)


def process_file(path_in, path_out):
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(path_in, parser)
    root = tree.getroot()

    basename = os.path.splitext(os.path.basename(path_in))[0]

    add_wikidata_corresp(root)
    convert_pnd_to_gnd(root)
    ensure_langusage_spanish(root)
    ensure_textclass_keywords(root)
    normalize_persname_rojas(root)
    ensure_publisher(root)
    ensure_caldracor_id(root, basename)
    ensure_creation_from_events(root)

    tree.write(
        path_out,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )


def main():
    for fname in os.listdir(INPUT_DIR):
        if not fname.lower().endswith(".xml"):
            continue
        in_path = os.path.join(INPUT_DIR, fname)
        out_path = os.path.join(OUTPUT_DIR, fname)
        print(f"Processing {in_path} -> {out_path}")
        process_file(in_path, out_path)


if __name__ == "__main__":
    main()
