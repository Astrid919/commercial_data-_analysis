from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


NAVY = "15324B"
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
LIGHT_BLUE = "E8EEF5"
LIGHT_GRAY = "F2F4F7"
CALLOUT = "F4F6F9"
PALE_GOLD = "F7EBCB"
PALE_RED = "F5DEDE"
GREEN = "4F8A5B"
RED = "9B1C1C"
GRAY = "687780"
WHITE = "FFFFFF"
TABLE_DXA = 9360
TABLE_INDENT_DXA = 120


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def set_run_font(run, name="Calibri", size=11, bold=None, color=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = rgb(color)


def shade_cell(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, bottom=80, start=120, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_dxa: int):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def set_table_borders(table, color="B8C2CC", size=4):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), str(size))
        node.set(qn("w:color"), color)


def set_repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def set_table_geometry(table, widths_dxa: list[int]):
    if sum(widths_dxa) != TABLE_DXA:
        raise ValueError(f"Table widths must total {TABLE_DXA}, got {sum(widths_dxa)}")
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(TABLE_DXA))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(TABLE_INDENT_DXA))
    tbl_ind.set(qn("w:type"), "dxa")
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        prevent_row_split(row)
        for i, cell in enumerate(row.cells):
            set_cell_width(cell, widths_dxa[i])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_table_borders(table)


def style_cell_text(cell, size=9, bold=False, color="1F2933", align=None):
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        if align is not None:
            paragraph.alignment = align
        for run in paragraph.runs:
            set_run_font(run, size=size, bold=bold, color=color)


def add_table(doc: Document, headers: list[str], rows: Iterable[Iterable], widths_dxa: list[int],
              font_size=8.5, numeric_cols: set[int] | None = None, header_fill=LIGHT_GRAY,
              first_col_bold=False):
    rows = list(rows)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, text in enumerate(headers):
        table.rows[0].cells[i].text = str(text)
        shade_cell(table.rows[0].cells[i], header_fill)
        style_cell_text(table.rows[0].cells[i], size=font_size, bold=True, color=NAVY,
                        align=WD_ALIGN_PARAGRAPH.CENTER)
    set_repeat_header(table.rows[0])
    for row_data in rows:
        row = table.add_row()
        for i, value in enumerate(row_data):
            row.cells[i].text = "" if value is None else str(value)
            align = WD_ALIGN_PARAGRAPH.RIGHT if numeric_cols and i in numeric_cols else WD_ALIGN_PARAGRAPH.LEFT
            style_cell_text(row.cells[i], size=font_size, bold=first_col_bold and i == 0, align=align)
    set_table_geometry(table, widths_dxa)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_source_note(doc: Document, text: str):
    p = doc.add_paragraph()
    p.style = doc.styles["Source Note"]
    p.add_run(text)
    return p


def add_caption(doc: Document, text: str):
    p = doc.add_paragraph()
    p.style = doc.styles["Caption"]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(text)
    return p


def set_picture_alt_text(inline_shape, descr: str):
    doc_pr = inline_shape._inline.docPr
    doc_pr.set("descr", descr)


def add_figure(doc: Document, image_path: Path, caption: str, alt_text: str, source: str | None = None, width=6.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    shape = p.add_run().add_picture(str(image_path), width=Inches(width))
    set_picture_alt_text(shape, alt_text)
    add_caption(doc, caption)
    if source:
        add_source_note(doc, source)


def add_callout(doc: Document, title: str, text: str, fill=CALLOUT, accent=BLUE):
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = title
    table.rows[0].cells[1].text = text
    shade_cell(table.rows[0].cells[0], accent)
    shade_cell(table.rows[0].cells[1], fill)
    style_cell_text(table.rows[0].cells[0], size=10, bold=True, color=WHITE, align=WD_ALIGN_PARAGRAPH.CENTER)
    style_cell_text(table.rows[0].cells[1], size=10, color=NAVY)
    set_repeat_header(table.rows[0])
    set_table_geometry(table, [1800, 7560])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)
    set_run_font(run, size=9, color=GRAY)


def configure_styles(doc: Document):
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.font.size = Pt(11)
    pf = normal.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.10
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for name, size, color, before, after in (
        ("Heading 1", 16, BLUE, 16, 8),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DARK_BLUE, 8, 4),
    ):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        st._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = rgb(color)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True
    caption = doc.styles["Caption"]
    caption.font.name = "Calibri"
    caption.font.size = Pt(9)
    caption.font.italic = True
    caption.font.color.rgb = rgb(GRAY)
    caption.paragraph_format.space_before = Pt(2)
    caption.paragraph_format.space_after = Pt(2)
    source = doc.styles.add_style("Source Note", 1)
    source.font.name = "Calibri"
    source.font.size = Pt(8.5)
    source.font.color.rgb = rgb(GRAY)
    source.paragraph_format.space_before = Pt(4)
    source.paragraph_format.space_after = Pt(4)
    source.paragraph_format.keep_with_next = True
    source.paragraph_format.keep_together = True


def configure_section(section):
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)


def configure_header_footer(doc: Document):
    section = doc.sections[0]
    section.different_first_page_header_footer = True
    header = section.header
    p = header.paragraphs[0]
    p.text = "IQVIA COMMERCIAL DATA SCIENTIST INTERVIEW CASE  |  PORTFOLIO ANALYTICS"
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(2)
    for r in p.runs:
        set_run_font(r, size=8.5, bold=True, color=GRAY)
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "D9E1E5")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.add_run("CONFIDENTIAL INTERVIEW CASE  |  ")
    for r in fp.runs:
        set_run_font(r, size=8.5, color=GRAY)
    add_page_number(fp)


def keep_with_next(paragraph):
    paragraph.paragraph_format.keep_with_next = True


def f_pct(x, digits=1):
    if x is None or not math.isfinite(float(x)):
        return "n/a"
    return f"{float(x)*100:.{digits}f}%"


def f_pp(x, digits=1):
    if x is None or not math.isfinite(float(x)):
        return "n/a"
    return f"{float(x)*100:.{digits}f} pp"


def f_num(x):
    return f"{float(x):,.0f}"


def f_m(x):
    return f"{float(x)/1e6:.1f}M"


def add_body(doc, text: str, bold_prefix: str | None = None):
    p = doc.add_paragraph()
    if bold_prefix and text.startswith(bold_prefix):
        r = p.add_run(bold_prefix)
        set_run_font(r, bold=True, color=NAVY)
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)
    return p


def add_page_break(doc):
    doc.add_page_break()


def build_report(results_path: Path, figures_dir: Path, data_path: Path, output_path: Path):
    results = json.loads(results_path.read_text(encoding="utf-8"))
    kpi = pd.DataFrame(results["inn_kpi"])
    peer = pd.DataFrame(results["peer_analysis"])
    cls = pd.DataFrame(results["classification_results"])
    fc = pd.DataFrame(results["forecast_results"])
    clusters = pd.DataFrame(results["cluster_summary"])
    audit = {r["metric"]: r for r in results["audit"]}
    selected_cls = results["metadata"]["selected_classification_model"]
    selected_fc = results["metadata"]["selected_forecast_model"]
    selected_cls_row = cls[cls.model == selected_cls].iloc[0]
    selected_fc_row = fc[fc.model == selected_fc].iloc[0]
    total_2023 = kpi.sales_2023.sum()
    total_2024 = kpi.forecast_2024.sum()
    portfolio_growth_2024 = total_2024 / total_2023 - 1
    sha256 = hashlib.sha256(data_path.read_bytes()).hexdigest()

    doc = Document()
    configure_styles(doc)
    for section in doc.sections:
        configure_section(section)
    configure_header_footer(doc)
    doc.core_properties.title = "AI-Driven Pharmaceutical Portfolio Analytics"
    doc.core_properties.subject = "IQVIA Commercial Data Scientist final interview case"
    doc.core_properties.author = "Candidate"
    doc.core_properties.keywords = "pharmaceutical, commercial analytics, forecasting, market share, portfolio"

    # Cover.
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(44)
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run("AI-Driven Pharmaceutical\nPortfolio Analytics")
    set_run_font(r, size=26, bold=True, color=NAVY)
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(28)
    r = p2.add_run("Market Performance, Competitive Dynamics and Demand Forecasting Using Machine Learning")
    set_run_font(r, size=15, bold=False, color=BLUE)
    cover_table = doc.add_table(rows=1, cols=4)
    cover_table.style = "Table Grid"
    cover_vals = [
        ("1,730", "SKUs"), ("20", "INNs"), ("60", "months"), (f_m(total_2023), "2023 units")
    ]
    for i, (value, label) in enumerate(cover_vals):
        cell = cover_table.rows[0].cells[i]
        cell.text = ""
        shade_cell(cell, LIGHT_BLUE)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rv = p.add_run(value + "\n")
        set_run_font(rv, size=18, bold=True, color=NAVY)
        rl = p.add_run(label)
        set_run_font(rl, size=9.5, bold=True, color=GRAY)
    set_repeat_header(cover_table.rows[0])
    set_table_geometry(cover_table, [2340, 2340, 2340, 2340])
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(32)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("Prepared for")
    set_run_font(r, size=10, bold=True, color=GRAY)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("IQVIA Commercial Data Scientist Final Interview")
    set_run_font(r, size=14, bold=True, color=NAVY)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("Analysis date: 19 September 2026")
    set_run_font(r, size=10, color=GRAY)
    p = doc.add_paragraph()
    r = p.add_run("Public development dataset; results are for interview demonstration and not an IQVIA deliverable.")
    set_run_font(r, size=9, italic=True, color=GRAY)
    add_page_break(doc)

    # Executive summary.
    doc.add_heading("Executive Summary", level=1)
    add_callout(doc, "Decision", f"The portfolio remains below its 2021 peak and the validation-selected {selected_fc} base case projects {f_m(total_2024)} units in 2024 ({f_pct(portfolio_growth_2024)} versus 2023). Commercial attention should be concentrated on molecules with both positive share momentum and forward demand, while high-volume share losers require defensive review.", fill=PALE_GOLD, accent=NAVY)
    add_body(doc, "The 20-INN development sample generated 122.2 million pack-equivalent units in 2023, down 1.3% from 2022 and 22.3% below the 2021 peak. The decline is broad enough that portfolio planning should not assume a simple return to the prior growth path.")
    add_body(doc, f"The early-warning classifier selected on 2022 validation achieved {f_pct(selected_cls_row.test_precision_top20)} Precision@Top20% and {selected_cls_row.test_lift_top20:.2f}x lift on the 2023 holdout. Six-month share momentum was the most important out-of-time signal, which supports a monthly leading-indicator process rather than annual retrospective review.")
    top_growth = kpi.nlargest(3, "forecast_growth_2024")
    add_body(doc, f"The strongest 2024 percentage-growth outlooks are {', '.join(top_growth.INN.tolist())}. IBUPROFENUM combines positive share momentum, scale and forecast growth and is the clearest growth leader. PREGABALINUM and ACETYLCYSTEINUM are lower-share opportunities that merit targeted commercial diagnosis before investment.")
    action_rows = [
        ("Invest", "IBUPROFENUM; validate PREGABALINUM and ACETYLCYSTEINUM uptake drivers.", "Positive momentum plus positive 2024 outlook."),
        ("Defend", "ACIDUM ACETYLSALICYLICUM, PARACETAMOLUM and DICLOFENACUM.", "Large current volume with recent portfolio-share loss."),
        ("Plan supply", f"Use {selected_fc} as the governed base case; monitor its {f_pct(selected_fc_row.test_Bias)} test bias.", "Reduce under-forecast and shortage risk."),
        ("Monitor", "Refresh share momentum, forecast error, stock-out flags and segments monthly.", "Create a commercial early-warning loop."),
    ]
    add_table(doc, ["Action", "Priority", "Why now"], action_rows, [1500, 4300, 3560], font_size=9, first_col_bold=True)
    add_source_note(doc, "All values in this report are calculated from the Teva 20-INN public development sample. Units are pack-equivalent sales, not revenue.")
    add_page_break(doc)

    # Data and analytical design.
    doc.add_heading("1. Business Question and Analytical Design", level=1)
    add_body(doc, "The case addresses four commercial questions: where demand is growing or declining; which sampled competitors are gaining or losing share; which molecules are most likely to improve over the next six to twelve months; and how forecasting plus portfolio segmentation can guide limited commercial attention.")
    add_body(doc, "The analysis follows the decision path from raw SKU sales through feature extraction, market definition, competitive analytics, portfolio segmentation, early-warning classification, demand forecasting and transparent action rules. All validation is time ordered. No result uses a random train/test split.")
    add_callout(doc, "Scope", "The dataset supports unit-demand and sampled portfolio analytics. It does not support revenue forecasting, pricing elasticity, promotion ROI, patient or HCP targeting, market access analysis, profitability decisions or discontinuation recommendations.", fill=PALE_RED, accent=RED)
    doc.add_heading("1.1 Dataset and data engineering", level=2)
    rows = [
        ("Grain", "One row per pharmaceutical SKU (Morion ID)."),
        ("Coverage", "1,730 SKUs; 20 INNs; 2019-01 to 2023-12."),
        ("Sales", "60 monthly columns measuring pack-equivalent unit demand."),
        ("Hierarchy", "ATC1-ATC5, INN, anonymized brand and SKU."),
        ("Text features", "Strength, unit, pack size and simplified dosage-form category parsed from Description/NFC."),
    ]
    add_table(doc, ["Element", "Implementation"], rows, [2100, 7260], font_size=9.5, first_col_bold=True)
    doc.add_heading("1.2 Data quality findings", level=2)
    dq_rows = [
        ("Completeness", f"{audit['Missing sales values']['value']} missing and {audit['Negative sales values']['value']} negative sales values."),
        ("Zero sales", f"{f_pct(audit['Zero sales ratio']['value'])} of SKU-months; retained as possible availability/intermittency signals."),
        ("Text extraction", f"Strength {f_pct(audit['Strength extraction rate']['value'])}; pack size {f_pct(audit['Pack-size extraction rate']['value'])}."),
        ("Potential stock-outs", f"{int(audit['Potential stock-out gaps']['value']):,} zero gaps between two positive months; flagged, not deleted."),
        ("Potential spikes", f"{int(audit['Potential spikes']['value']):,} local spikes; retained for aggregate demand and sensitivity review."),
    ]
    add_table(doc, ["Check", "Result"], dq_rows, [2400, 6960], font_size=9.5, first_col_bold=True)
    doc.add_heading("1.3 Market definition", level=2)
    add_body(doc, "The preferred competitive market is ATC4. When an ATC4 group contains fewer than two sampled INNs, the analysis falls back to ATC3. If the fallback still has no sampled peer, competitive share is not reported. Twelve of the 20 INNs have at least one usable ATC4 or ATC3 peer context; the rest are evaluated with explicitly labeled portfolio-share metrics.")
    add_callout(doc, "Caveat", "The file is a purposive 20-INN development sample, not a complete market census. Reported shares are sample shares and must not be interpreted as external market shares.", fill=PALE_GOLD, accent=BLUE)
    add_page_break(doc)

    # Market performance.
    doc.add_heading("2. Market Performance and Competitive Dynamics", level=1)
    add_figure(doc, figures_dir / "01_annual_portfolio_sales.png", "Figure 1. Annual portfolio unit sales, 2019-2023.", "Bar chart showing annual portfolio sales increasing through 2021 and falling in 2022 and 2023.", "Source: author analysis of the Teva 20-INN development sample.")
    add_body(doc, "Portfolio demand increased 8.2% in 2020 and 1.4% in 2021, then contracted 21.3% in 2022 and 1.3% in 2023. The apparent stabilization in 2023 masks material molecule-level divergence.")
    doc.add_heading("2.1 Molecule performance", level=2)
    top_volume = kpi.nlargest(6, "sales_2023")
    vol_rows = [(r.INN, f_m(r.sales_2023), f_pct(r.yoy_growth_2023), f_pct(r.portfolio_share_2023), f_pp(r.portfolio_share_change_2023)) for _, r in top_volume.iterrows()]
    add_table(doc, ["INN", "2023 units", "YoY", "Portfolio share", "Share change"], vol_rows, [3000, 1500, 1300, 1700, 1860], font_size=8.8, numeric_cols={1,2,3,4})
    add_body(doc, "ACIDUM ACETYLSALICYLICUM was the largest molecule at 22.4M units, but its sample share declined 0.5 percentage points. IBUPROFENUM grew 8.4% and gained 1.0 point of portfolio share, making it the strongest high-volume momentum story. PARACETAMOLUM remained the third-largest molecule but fell 12.6% and lost 1.3 points.")
    add_page_break(doc)

    doc.add_heading("2.2 Sampled peer-market dynamics", level=2)
    key_peer = peer[(peer["market_name"].str.contains("HMG|M01A |N02B ", regex=True))].copy()
    key_peer = key_peer.sort_values(["market_name", "share_change_pp"], ascending=[True, False])
    peer_rows = [(r.INN, (r.market_name[:34] + "…") if len(r.market_name) > 35 else r.market_name, f_pct(r.market_growth_2023), f_pp(r.share_change_pp), f_num(r.share_effect)) for _, r in key_peer.iterrows()]
    add_table(doc, ["INN", "Sampled market", "Market growth", "Share change", "Share effect"], peer_rows, [2350, 3300, 1300, 1200, 1210], font_size=8.2, numeric_cols={2,3,4})
    add_body(doc, "Within sampled statins, ROSUVASTATINUM gained 3.0 points of share while ATORVASTATINUM lost the same amount. The statin market grew 19.0%, so both market expansion and competitive mix mattered.")
    add_body(doc, "Within systemic NSAIDs, IBUPROFENUM gained 2.0 points and generated a +519k share effect; DICLOFENACUM lost 3.1 points and a -795k share effect. Within other analgesics/antipyretics, PREGABALINUM gained 3.7 points despite a 4.6% market decline, producing a +997k share effect, while PARACETAMOLUM lost 4.1 points and a -1.10M share effect.")
    add_callout(doc, "Commercial implication", "Growth decomposition separates category tailwind from competitive execution. Molecules growing because the sampled market expands should not receive the same diagnosis as molecules gaining share in a declining market.", fill=CALLOUT, accent=BLUE)
    add_page_break(doc)

    # Segmentation.
    doc.add_heading("3. Portfolio Segmentation", level=1)
    add_body(doc, "INN-level commercial, demand and product-complexity features were standardized and compared across K=3, K=4 and K=5 solutions. K=4 produced the highest silhouette score (0.232 versus 0.208 and 0.211), so it was selected for descriptive archetypes.")
    add_figure(doc, figures_dir / "06_portfolio_clusters.png", "Figure 2. PCA projection of the four commercial archetypes.", "Scatterplot of the first two principal components with points colored by cluster; selected high-volume INNs are labeled.", "Source: standardized INN features; PCA is used for visualization only.")
    cluster_rows = [(r.cluster_label, int(r.INN_count), f_m(r.sales_2023), f_pct(r.avg_yoy_growth), f_pp(r.avg_share_change), f_pct(r.avg_forecast_growth)) for _, r in clusters.iterrows()]
    add_table(doc, ["Archetype", "INNs", "2023 units", "Avg YoY", "Avg share change", "Avg 2024 growth"], cluster_rows, [2400, 800, 1400, 1200, 1700, 1860], font_size=8.5, numeric_cols={1,2,3,4,5})
    add_body(doc, "The Growth/Emerging cluster contains PREGABALINUM and ROSUVASTATINUM, both with strong recent momentum. Mature Leaders contain the largest established molecules. The At-Risk/Declining group has the highest average volatility and negative historical growth. Clusters remain descriptive; action recommendations use forward-looking rules rather than cluster membership alone.")
    add_page_break(doc)

    # Classification.
    doc.add_heading("4. Commercial Opportunity Model", level=1)
    add_body(doc, "The target is a Future Share Winner: an INN whose six-month-ahead change in portfolio share ranks in the top quartile at a given anchor month. This portfolio-level fallback is necessary because most sampled ATC markets do not contain enough peers for stable market-specific labels.")
    split_rows = [
        ("Training", "2020-01 to 2021-12 anchors", "Feature learning"),
        ("Validation", "2022-01 to 2022-06 anchors", "Hyperparameter and model selection"),
        ("Test", "2022-07 to 2023-06 anchors", "One-time out-of-time evaluation"),
    ]
    add_table(doc, ["Period", "Anchor months", "Purpose"], split_rows, [1500, 3000, 4860], font_size=9.5, first_col_bold=True)
    class_rows = [(r.model, f_pct(r.validation_pr_auc), f_pct(r.test_pr_auc), f_pct(r.test_precision_top20), f"{r.test_lift_top20:.2f}x") for _, r in cls.iterrows()]
    add_table(doc, ["Model", "Val PR-AUC", "Test PR-AUC", "Test P@20", "Test Lift@20"], class_rows, [2600, 1600, 1600, 1600, 1960], font_size=9, numeric_cols={1,2,3,4})
    add_body(doc, f"{selected_cls} was selected on the validation period and achieved {f_pct(selected_cls_row.test_roc_auc)} ROC-AUC, {f_pct(selected_cls_row.test_pr_auc)} PR-AUC, {f_pct(selected_cls_row.test_precision_top20)} Precision@20% and {selected_cls_row.test_lift_top20:.2f}x Lift@20% on the holdout. In operational terms, the model more than doubled the concentration of future winners in the top-fifth review list relative to the 25% base rate.")
    add_figure(doc, figures_dir / "03_classifier_lift.png", "Figure 3. Test-period Lift@20% by opportunity model.", "Horizontal bar chart comparing lift at the top twenty percent across four classifiers.", "Model selection was based on 2022 validation, not 2023 test performance.")
    add_body(doc, "Logistic regression produced the highest test lift, but it was not retrospectively promoted because that would use the test set for selection. This is an important model-governance point: the honest conclusion is that ranking is useful, while model choice should be revisited only after another prospective period.")
    doc.add_heading("4.1 Explainability", level=2)
    top_imp = results["classification_importance"][:5]
    imp_rows = [(r["feature"], f"{r['pr_auc_drop']:.3f}") for r in top_imp]
    add_table(doc, ["Feature", "Test PR-AUC drop when permuted"], imp_rows, [4500, 4860], font_size=9.5, numeric_cols={1})
    add_body(doc, "Six-month share change was by far the strongest out-of-time signal. Strength breadth, six-month growth and three-month share change also contributed. These importances are predictive, not causal; they identify monitoring signals, not levers guaranteed to create growth.")
    add_page_break(doc)

    # Forecasting.
    doc.add_heading("5. Demand Forecasting", level=1)
    add_body(doc, "Forecasts were produced at INN-by-month level. Seasonal Naive, damped ETS, a global ridge autoregression with calendar and lag features, shallow global boosted trees and a validation-weighted ensemble were compared. All 2023 forecasts were generated without using 2023 outcomes.")
    forecast_rows = [(r.model, f_pct(r.validation_WAPE), f_pct(r.test_WAPE), f"{r.test_MASE:.2f}", f_pct(r.test_Bias)) for _, r in fc.iterrows()]
    add_table(doc, ["Model", "Val WAPE", "Test WAPE", "Test MASE", "Test bias"], forecast_rows, [2900, 1500, 1500, 1500, 1960], font_size=9, numeric_cols={1,2,3,4})
    add_body(doc, f"{selected_fc} won the 2022 validation comparison with {f_pct(selected_fc_row.validation_WAPE)} WAPE and was therefore selected before opening the 2023 holdout. On 2023 it delivered {f_pct(selected_fc_row.test_WAPE)} WAPE, {selected_fc_row.test_MASE:.2f} MASE and {f_pct(selected_fc_row.test_Bias)} bias. The negative bias indicates under-forecast risk and should be monitored in supply planning.")
    ensemble = fc[fc.model == "Validation-weighted Ensemble"].iloc[0]
    add_callout(doc, "Model risk", f"The validation-weighted ensemble achieved a lower 2023 WAPE ({f_pct(ensemble.test_WAPE)}) than the governed {selected_fc} model, but it did not win the earlier validation period. Treat this as a hypothesis for the next prospective backtest—not permission to re-select on the holdout.", fill=PALE_GOLD, accent=BLUE)
    add_figure(doc, figures_dir / "04_forecast_2023_actual_vs_predicted.png", "Figure 4. 2023 portfolio demand: actual versus governed forecast and seasonal baseline.", "Line chart comparing monthly actual portfolio demand with damped ETS and seasonal naive predictions.", "Source: out-of-time forecasts aggregated from INN-level predictions.")
    add_page_break(doc)

    doc.add_heading("5.1 2024 base case", level=2)
    add_body(doc, f"After refitting the validation-selected model on all 2019-2023 data, the bottom-up reconciled 2024 portfolio forecast is {f_m(total_2024)} units, {f_pct(portfolio_growth_2024)} below 2023. The empirical 80% ranges are calibrated from 2022 log residuals and reflect historical forecast error, not external event scenarios.")
    priority = kpi.sort_values("forecast_growth_2024", ascending=False).head(8)
    priority_rows = [(r.INN, f_m(r.sales_2023), f_m(r.forecast_2024), f_pct(r.forecast_growth_2024), r.action_segment) for _, r in priority.iterrows()]
    add_table(doc, ["INN", "2023 units", "2024 forecast", "Growth", "Action"], priority_rows, [2900, 1400, 1600, 1200, 2260], font_size=8.8, numeric_cols={1,2,3})
    add_figure(doc, figures_dir / "05_opportunity_matrix.png", "Figure 5. 2024 forecast growth versus 2023 portfolio-share momentum.", "Bubble chart with forecast growth on the horizontal axis, portfolio share change on the vertical axis and bubble size equal to 2023 sales.", "Axes use portfolio-level share because most ATC markets are singletons in the development sample.")
    add_body(doc, "IBUPROFENUM is the clearest scaled growth leader. PREGABALINUM and ACETYLCYSTEINUM are emerging opportunities. PARACETAMOLUM and ACIDUM ACETYLSALICYLICUM have positive demand outlooks but negative share momentum, so growth should be paired with a competitive-defense diagnosis. LEVOFLOXACINUM has both negative share momentum and the weakest forecast growth and is the clearest at-risk signal.")
    add_page_break(doc)

    # Recommendations.
    doc.add_heading("6. Commercial Recommendations", level=1)
    rec_rows = [
        ("1. Prioritize growth leaders", "IBUPROFENUM", "Maintain commercial support and ensure supply can capture continued demand; investigate which strengths/forms drive the gain."),
        ("2. Develop emerging opportunities", "PREGABALINUM; ACETYLCYSTEINUM", "Validate uptake drivers, distribution and formulation mix before incremental spend."),
        ("3. Defend high-volume franchises", "Aspirin; PARACETAMOLUM; DICLOFENACUM", "Diagnose sampled share loss, competitor substitution and formulation-level displacement."),
        ("4. Manage forecast risk", "Portfolio", f"Run {selected_fc} as the governed baseline, monitor bias monthly and prospectively challenger-test the ensemble."),
        ("5. Build an early-warning loop", "All INNs", "Refresh growth, sampled share, share change, forecast error and action segment every month."),
    ]
    add_table(doc, ["Recommendation", "Scope", "Commercial action"], rec_rows, [2600, 2100, 4660], font_size=9, first_col_bold=True)
    doc.add_heading("6.1 Monthly decision cadence", level=2)
    cadence_rows = [
        ("Data refresh", "Load the latest month; rerun quality flags and feature extraction."),
        ("Performance review", "Update unit growth, sampled peer share, share change and decomposition."),
        ("Model monitoring", "Score future-winner probability; compare forecast error and bias by INN."),
        ("Action review", "Escalate only molecules that cross transparent growth/share/forecast rules."),
        ("Learning loop", "Record commercial hypotheses and outcomes so future models can include causal context."),
    ]
    add_table(doc, ["Step", "Output"], cadence_rows, [2300, 7060], font_size=9.5, first_col_bold=True)
    add_callout(doc, "Operating principle", "Do not give every molecule the same forecasting or commercial treatment. Stable mature demand, volatile demand and intermittent demand require different monitoring thresholds and planning methods.", fill=CALLOUT, accent=NAVY)

    # Limitations and appendix.
    doc.add_heading("7. Limitations and Next Steps", level=1)
    limitations = [
        ("Sample completeness", "The 20-INN development file does not represent complete markets; sample shares are not external shares."),
        ("Commercial drivers", "No price, promotion, access, payer, patient, HCP, supply-policy or competitor-entry features are available."),
        ("Outcome interpretation", "Predictive importance does not establish causality or specify the intervention that will create growth."),
        ("Forecast horizon", "Only 60 monthly observations are available. Structural breaks can dominate annual backtests."),
        ("Intervals", "Empirical ranges reflect historical residuals and omit explicit launch, shortage and policy scenarios."),
        ("Profitability", "Unit demand cannot support profit, revenue or discontinuation decisions."),
    ]
    add_table(doc, ["Limitation", "Decision consequence"], limitations, [2400, 6960], font_size=9.3, first_col_bold=True)
    add_body(doc, "The next analytical step should use a fuller market extract with complete competitor coverage, then re-run ATC4 share modeling, add scenario drivers and extend rolling-origin validation. If profitability or field-force decisions are in scope, price, net sales, cost, promotional exposure, payer access and patient/HCP data must be added before optimization.")
    add_page_break(doc)

    doc.add_heading("Appendix A. Technical Definitions", level=1)
    defs = [
        ("YoY growth", "(Sales_t - Sales_t-12) / Sales_t-12; undefined when the denominator is zero."),
        ("CAGR", "(Sales_2023 / Sales_2019)^(1/4) - 1."),
        ("Sample market share", "INN sales / sampled market sales within a qualifying ATC4 or fallback ATC3 group."),
        ("Share effect", "Actual sales_t - Market sales_t × Share_t-1."),
        ("Seasonality strength", "1 - Var(residual) / Var(seasonal + residual), bounded to [0,1]."),
        ("Future Share Winner", "Top quartile of six-month-ahead portfolio-share change at each anchor month."),
        ("Precision@20%", "Winner rate among the top 20% of scored observations."),
        ("Lift@20%", "Precision@20% / overall winner rate."),
        ("WAPE", "Σ|actual - forecast| / Σactual."),
        ("Bias", "Σ(forecast - actual) / Σactual."),
    ]
    add_table(doc, ["Metric", "Definition"], defs, [2500, 6860], font_size=9.2, first_col_bold=True)
    doc.add_heading("Appendix B. Reproducibility", level=1)
    repro = [
        ("Source file", data_path.name),
        ("SHA-256", sha256),
        ("Analysis seed", str(results["metadata"]["seed"])),
        ("Time split", "Train through 2021; validate in 2022; final holdout in 2023."),
        ("Forecast reconciliation", "Bottom-up sum of INN forecasts to portfolio."),
        ("Deliverable scope", "Analysis workbook, written report and reproducible analysis code."),
    ]
    add_table(doc, ["Item", "Value"], repro, [2200, 7160], font_size=8.8, first_col_bold=True)
    doc.add_heading("Sources", level=2)
    source_rows = [(s["name"], s["url"]) for s in results["sources"]]
    add_table(doc, ["Source", "URL"], source_rows, [3100, 6260], font_size=8.5, first_col_bold=True)

    # Apply page setup to all sections and save.
    for section in doc.sections:
        configure_section(section)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    print(json.dumps({"output": str(output_path), "pages_expected": "11-14", "sha256": sha256}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--figures", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    build_report(args.results, args.figures, args.data, args.output)
