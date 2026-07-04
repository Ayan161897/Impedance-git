#!/usr/bin/env python3
"""Generate EIS PCB Bill of Materials PDF with Reichelt purchase links."""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import date

# ── Colours ────────────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#0F1F3D")
BLUE      = colors.HexColor("#1565C0")
TEAL      = colors.HexColor("#00897B")
LIGHT_BG  = colors.HexColor("#EBF0F8")
ROW_ALT   = colors.HexColor("#F4F7FB")
HDR_CAT   = colors.HexColor("#1E3A5F")
WHITE     = colors.white
MUTED     = colors.HexColor("#64748B")
WARN      = colors.HexColor("#B45309")

# ── Styles ─────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "Title", parent=styles["Normal"],
    fontSize=20, fontName="Helvetica-Bold",
    textColor=NAVY, spaceAfter=2*mm, leading=24
)
subtitle_style = ParagraphStyle(
    "Subtitle", parent=styles["Normal"],
    fontSize=10, fontName="Helvetica",
    textColor=MUTED, spaceAfter=1*mm
)
col_hdr_style = ParagraphStyle(
    "ColHdr", parent=styles["Normal"],
    fontSize=9, fontName="Helvetica-Bold",
    textColor=WHITE, alignment=TA_CENTER
)
cat_style = ParagraphStyle(
    "Cat", parent=styles["Normal"],
    fontSize=9, fontName="Helvetica-Bold",
    textColor=WHITE
)
cell_style = ParagraphStyle(
    "Cell", parent=styles["Normal"],
    fontSize=8.5, fontName="Helvetica",
    textColor=colors.HexColor("#1E293B"),
    leading=12
)
cell_bold_style = ParagraphStyle(
    "CellBold", parent=styles["Normal"],
    fontSize=8.5, fontName="Helvetica-Bold",
    textColor=colors.HexColor("#1E293B"),
    leading=12
)
link_style = ParagraphStyle(
    "Link", parent=styles["Normal"],
    fontSize=8, fontName="Helvetica",
    textColor=BLUE, leading=11
)
note_style = ParagraphStyle(
    "Note", parent=styles["Normal"],
    fontSize=8, fontName="Helvetica",
    textColor=MUTED, leading=11
)
warn_style = ParagraphStyle(
    "Warn", parent=styles["Normal"],
    fontSize=8, fontName="Helvetica-Oblique",
    textColor=WARN, leading=11
)
footer_style = ParagraphStyle(
    "Footer", parent=styles["Normal"],
    fontSize=7.5, fontName="Helvetica",
    textColor=MUTED
)


def cell(text):
    return Paragraph(text, cell_style)

def bold_cell(text):
    return Paragraph(text, cell_bold_style)

def link_cell(url, label=None):
    display = label or url
    # Truncate for display but keep full URL as href
    if len(display) > 60:
        display = display[:57] + "..."
    return Paragraph(f'<link href="{url}" color="#1565C0">{display}</link>', link_style)

def cat_row(label):
    """Full-width category separator row."""
    return [Paragraph(label, cat_style), "", ""]

def warn_cell(text):
    return Paragraph(text, warn_style)


# ── Bill of Materials data ─────────────────────────────────────────────────
# (component_name, description, quantity, reichelt_url, note)
SECTIONS = [
    # ── Microcontrollers & Digital ICs ────────────────────────────────────
    ("Microcontrollers & Digital ICs", [
        (
            "STM32F303CCT6",
            "ARM Cortex-M4F, 72 MHz, 256 KB Flash, LQFP-48\n"
            "Central MCU — ADC, SPI, USART, DMA",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=STM32F303CCT6",
            ""
        ),
        (
            "CP2102-GMR",
            "Silicon Labs USB-to-UART Bridge, QFN-28\n"
            "Converts USB (PC) to USART1 (STM32 PA9/PA10)",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=CP2102",
            "Also available at Mouser / DigiKey if not in stock"
        ),
        (
            "W25Q32JVSSIQ",
            "Winbond 32 Mbit SPI Flash, SOIC-8\n"
            "Stores sweep measurement records; shares SPI1 (CS=PB12)",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=W25Q32",
            ""
        ),
    ]),

    # ── DDS Signal Generator ──────────────────────────────────────────────
    ("DDS Signal Generator", [
        (
            "AD9833BRMZ",
            "Analog Devices Programmable Waveform Generator, MSOP-10\n"
            "Generates swept sine; SPI-controlled (FSYNC=PA4); 25 MHz MCLK",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=AD9833",
            "Specialty ADI part — also at Mouser / DigiKey"
        ),
    ]),

    # ── Analog ICs ────────────────────────────────────────────────────────
    ("Analog ICs", [
        (
            "OPA2140AID",
            "Texas Instruments Dual Precision FET-Input Op-Amp, SOIC-8\n"
            "Amp1A: excitation unity-gain buffer; Amp2A: TIA (I-to-V)",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=OPA2140",
            "Precision FET op-amp — also at Mouser / DigiKey"
        ),
        (
            "ADR4533BRZ",
            "Analog Devices 3.3 V Precision Voltage Reference, SOIC-8\n"
            "Feeds STM32 VDDA and VREF+ for accurate ADC full-scale",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=ADR4533",
            "Low-drift (<25 uV/degC) reference — also at Mouser / DigiKey"
        ),
        (
            "MCP1700T-3302E/TT",
            "Microchip 3.3 V Ultra-Low IQ LDO Regulator, SOT-23\n"
            "USB-C VBUS (5 V) to 3.3 V system supply; 250 mA output",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=MCP1700",
            ""
        ),
    ]),

    # ── Oscillators & Crystals ────────────────────────────────────────────
    ("Oscillators & Crystals", [
        (
            "ASE-25.000MHZ-LC-T",
            "Abracon 25 MHz SMD Crystal Oscillator (full-can, 4-pad)\n"
            "AD9833 MCLK — determines DDS freq word accuracy",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=Oszillator+25+MHz+SMD",
            "5x3.2 mm or 7x5 mm footprint — verify package on datasheet"
        ),
        (
            "ABM3B-8.000MHZ-B2-T",
            "Abracon 8 MHz SMD Crystal, 3.2x2.5 mm\n"
            "STM32 HSE (PF0/OSC_IN, PF1/OSC_OUT) -> PLL x9 = 72 MHz",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=Quarz+8+MHz+SMD",
            ""
        ),
    ]),

    # ── Capacitors ────────────────────────────────────────────────────────
    ("Capacitors", [
        (
            "100 nF / 50 V / X7R / 0402",
            "MLCC Decoupling Capacitor\n"
            "One per IC power pin: STM32 x5, AD9833 x2, OPA2140 x2,\n"
            "ADR4533 x1, W25Q32 x1, CP2102 x2  (order extras)",
            "15",
            "https://www.reichelt.de/search.html?SEARCH=100nF+0402+X7R",
            ""
        ),
        (
            "1 uF / 16 V / X5R / 0402",
            "MLCC Bulk Bypass Capacitor\n"
            "ADR4533 output x1, MCP1700 input x1, MCP1700 output x1,\n"
            "STM32 VDDA x1, extra x1",
            "5",
            "https://www.reichelt.de/search.html?SEARCH=1uF+0402+X5R",
            ""
        ),
        (
            "10 uF / 16 V / X5R / 0805",
            "MLCC Bulk Input Capacitor\n"
            "USB-C VBUS input bulk — absorbs cable inductance transients",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=10uF+0805+X5R",
            ""
        ),
        (
            "22 pF / 50 V / C0G / 0402",
            "MLCC Crystal Load Capacitor\n"
            "Two load caps for 8 MHz STM32 crystal (C_L = 10 pF typ.)",
            "2",
            "https://www.reichelt.de/search.html?SEARCH=22pF+0402+C0G",
            "Verify exact C_L value from ABM3B-8.000 datasheet"
        ),
    ]),

    # ── Resistors ─────────────────────────────────────────────────────────
    ("Resistors (all 0402, 1%)", [
        (
            "330 Ohm / 0402",
            "LED Current-Limiting Resistor\n"
            "Series resistor for status LED on PB13 (3.3 V - V_f) / I_f",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=330+Ohm+0402",
            ""
        ),
        (
            "5.1 kOhm / 0402",
            "USB-C CC Pull-Down Resistors\n"
            "CC1 and CC2 pins — configures board as 5 V sink (UFP)",
            "2",
            "https://www.reichelt.de/search.html?SEARCH=5%2C1+kOhm+0402",
            ""
        ),
        (
            "10 kOhm / 0402",
            "General Pull-Up / Pull-Down Resistors\n"
            "W25Q32 /CS pull-up (PB12), BOOT0 pull-down, TIA Rf (default)",
            "3",
            "https://www.reichelt.de/search.html?SEARCH=10+kOhm+0402",
            "Rf is user-selectable — add 1k / 100k variants as needed"
        ),
    ]),

    # ── LED ───────────────────────────────────────────────────────────────
    ("LED", [
        (
            "Green LED / 0402 SMD",
            "Status / Activity LED\n"
            "Connected to PB13 (active high); toggled once per sweep step",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=LED+gruen+0402+SMD",
            ""
        ),
    ]),

    # ── Connectors ────────────────────────────────────────────────────────
    ("Connectors", [
        (
            "USB-C Receptacle (SMD)",
            "USB Type-C Female Connector — Power + Data\n"
            "VBUS (5 V in), D+/D- to CP2102, CC1/CC2 pull-downs",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=USB-C+Buchse+SMD",
            "Verify footprint matches your PCB layout"
        ),
        (
            "Electrode Connector (2x BNC PCB)",
            "Coaxial BNC PCB-Mount Connector\n"
            "Electrode+ (excitation) and Electrode- (return / TIA input)",
            "2",
            "https://www.reichelt.de/search.html?SEARCH=BNC+Buchse+Leiterplatte",
            "Alternatively use 2-pin screw terminal or SMA connector"
        ),
        (
            "SWD Debug Header — 2x5 / 1.27 mm",
            "ARM Cortex Debug Connector (Cortex-M 10-pin)\n"
            "SWDIO (PA13), SWDCLK (PA14), SWO, RESET, VDD, GND",
            "1",
            "https://www.reichelt.de/search.html?SEARCH=Stiftleiste+2x5+1%2C27",
            ""
        ),
    ]),

    # ── PCB ───────────────────────────────────────────────────────────────
    ("PCB", [
        (
            "Custom PCB (2-layer or 4-layer)",
            "Bare PCB manufactured from your KiCad / Altium design files\n"
            "Min. 4/4 mil clearance recommended; controlled impedance for SPI",
            "1",
            "https://jlcpcb.com",
            "Order from JLCPCB, PCBWay, or Eurocircuits (EU lead time ~5d)"
        ),
    ]),
]


# ── Build PDF ─────────────────────────────────────────────────────────────
def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=20*mm,
        title="EIS PCB — Bill of Materials",
        author="EIS Measurement Project"
    )

    W_TOTAL = A4[0] - 30*mm  # usable width
    COL_WIDTHS = [W_TOTAL * 0.29, W_TOTAL * 0.06, W_TOTAL * 0.65]

    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("EIS Measurement PCB", title_style))
    story.append(Paragraph("Bill of Materials — Component Order List", subtitle_style))
    story.append(Paragraph(
        f"Generated: {date.today().strftime('%d %B %Y')}  |  "
        f"MCU: STM32F303CCT6  |  Supplier: Reichelt Elektronik (DE)",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=4*mm))

    # ── Column header row ─────────────────────────────────────────────────
    header_row = [
        Paragraph("Component / Part Number", col_hdr_style),
        Paragraph("Qty", col_hdr_style),
        Paragraph("Reichelt Order Link  (click to open search)", col_hdr_style),
    ]

    all_rows = [header_row]
    row_styles = []  # additional per-row TableStyle commands

    current_data_row = 1  # row index in table (0 = header)

    for section_name, components in SECTIONS:
        # Category header spanning all 3 columns
        cat_label = f"  {section_name}"
        all_rows.append([Paragraph(cat_label, cat_style), "", ""])
        row_styles.append(("SPAN", (0, current_data_row), (2, current_data_row)))
        row_styles.append(("BACKGROUND", (0, current_data_row), (2, current_data_row), HDR_CAT))
        row_styles.append(("TOPPADDING", (0, current_data_row), (2, current_data_row), 4))
        row_styles.append(("BOTTOMPADDING", (0, current_data_row), (2, current_data_row), 4))
        current_data_row += 1

        for idx, (part, desc, qty, url, note) in enumerate(components):
            bg = ROW_ALT if idx % 2 == 0 else WHITE

            # Build component cell: bold part number + description
            comp_para = Paragraph(
                f'<b>{part}</b><br/>'
                + desc.replace("\n", "<br/>"),
                cell_style
            )

            # Build link cell
            link_para = link_cell(url)
            if note:
                note_para = Paragraph(f"&#8505; {note}", warn_style)
                from reportlab.platypus import KeepTogether as KT
                link_content = [link_para, Spacer(1, 1.5*mm), note_para]
            else:
                link_content = [link_para]

            # Wrap link cell content in a sub-table to stack paragraphs
            def build_link_cell(items):
                parts = []
                for item in items:
                    parts.append(item)
                return parts

            # Use a nested list — reportlab Table cells can contain Paragraphs
            # We'll just concatenate into a single Paragraph with line breaks
            link_text = f'<link href="{url}" color="#1565C0">{url}</link>'
            if note:
                link_text += f'<br/><font color="#B45309" size="7.5"><i>&#8505; {note}</i></font>'
            link_para_full = Paragraph(link_text, link_style)

            qty_para = Paragraph(qty, ParagraphStyle(
                "Qty", parent=styles["Normal"],
                fontSize=9, fontName="Helvetica-Bold",
                textColor=NAVY, alignment=TA_CENTER
            ))

            all_rows.append([comp_para, qty_para, link_para_full])
            row_styles.append(("BACKGROUND", (0, current_data_row), (2, current_data_row), bg))
            current_data_row += 1

    # ── Build table ───────────────────────────────────────────────────────
    table = Table(all_rows, colWidths=COL_WIDTHS, repeatRows=1)

    base_style = [
        # Header row
        ("BACKGROUND",    (0, 0), (2, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (2, 0),  WHITE),
        ("FONTNAME",      (0, 0), (2, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (2, 0),  9),
        ("ALIGN",         (0, 0), (2, 0),  "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#C5CFD8")),
        ("LINEBELOW",     (0, 0), (2, 0),   1.0, TEAL),
    ]

    table.setStyle(TableStyle(base_style + row_styles))

    story.append(table)
    story.append(Spacer(1, 6*mm))

    # ── Notes ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.8, color=MUTED, spaceAfter=3*mm))
    story.append(Paragraph("<b>Notes</b>", ParagraphStyle(
        "NoteHdr", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=2*mm
    )))
    notes = [
        "1.  All Reichelt links open a search results page — verify part number and package before adding to cart.",
        "2.  Specialty precision ICs (AD9833, OPA2140, ADR4533) may not be stocked by Reichelt. "
             "Order from <link href='https://www.mouser.de' color='#1565C0'>Mouser Deutschland</link> or "
             "<link href='https://www.digikey.de' color='#1565C0'>DigiKey Germany</link> if unavailable.",
        "3.  Resistor Rf (TIA feedback) default is 10 kOhm. For higher-impedance cells order 100 kOhm (0402) as well.",
        "4.  Crystal load capacitors (22 pF): verify the exact C_L value from the ABM3B-8.000MHZ datasheet "
             "(specified C_L is 10 pF; board caps = 2*(C_stray + C_board) to match C_L).",
        "5.  PCB: JLCPCB (https://jlcpcb.com) ships to Germany in 7-10 days at low cost. "
             "Eurocircuits (https://www.eurocircuits.com) offers EU-manufactured boards in ~5 days.",
        "6.  All SMD passives are 0402 footprint. A solder paste stencil is strongly recommended.",
        "7.  The electrode connector type (BNC, SMA, or screw terminal) depends on your measurement setup.",
    ]
    for n in notes:
        story.append(Paragraph(n, note_style))
        story.append(Spacer(1, 1.5*mm))

    # ── Build ──────────────────────────────────────────────────────────────
    doc.build(story)
    print(f"PDF saved: {output_path}")


if __name__ == "__main__":
    build_pdf("EIS_PCB_BOM.pdf")
