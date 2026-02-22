# generate_detailed_report.py
# Defense-Grade Technical Report for Quantum-Safe Tactical Communication System
# Revised for iDEX Defence Hackathon Submission

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image, Flowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import io

# --- Custom Colors (Professional Defense Palette) ---
PRIMARY_DARK = HexColor("#1a237e")      # Deep Indigo
PRIMARY_LIGHT = HexColor("#3949ab")     # Indigo
ACCENT_GOLD = HexColor("#ffc107")       # Amber
ACCENT_TEAL = HexColor("#00897b")       # Teal
TEXT_DARK = HexColor("#212121")         # Near Black
TEXT_LIGHT = HexColor("#757575")        # Grey
BG_LIGHT = HexColor("#f5f5f5")          # Light Grey
SUCCESS_GREEN = HexColor("#43a047")     # Green
DANGER_RED = HexColor("#e53935")        # Red

# --- Custom Styles ---
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name='MainTitle',
    fontName='Helvetica-Bold',
    fontSize=26,
    textColor=PRIMARY_DARK,
    alignment=TA_CENTER,
    spaceAfter=16,
    leading=32
))

styles.add(ParagraphStyle(
    name='Subtitle',
    fontName='Helvetica',
    fontSize=13,
    textColor=TEXT_LIGHT,
    alignment=TA_CENTER,
    spaceAfter=30
))

styles.add(ParagraphStyle(
    name='SectionHeading',
    fontName='Helvetica-Bold',
    fontSize=16,
    textColor=PRIMARY_DARK,
    spaceBefore=20,
    spaceAfter=10,
    leading=20
))

styles.add(ParagraphStyle(
    name='SubHeading',
    fontName='Helvetica-Bold',
    fontSize=12,
    textColor=PRIMARY_LIGHT,
    spaceBefore=12,
    spaceAfter=6,
    leading=16
))

styles.add(ParagraphStyle(
    name='CustomBody',
    fontName='Helvetica',
    fontSize=10,
    textColor=TEXT_DARK,
    alignment=TA_JUSTIFY,
    spaceAfter=8,
    leading=14
))

styles.add(ParagraphStyle(
    name='Callout',
    fontName='Helvetica-Oblique',
    fontSize=10,
    textColor=ACCENT_TEAL,
    alignment=TA_LEFT,
    leftIndent=15,
    spaceAfter=8,
    leading=13
))

styles.add(ParagraphStyle(
    name='TOCEntry',
    fontName='Helvetica',
    fontSize=11,
    textColor=PRIMARY_LIGHT,
    spaceAfter=6,
    leftIndent=12,
    leading=14
))

styles.add(ParagraphStyle(
    name='Footer',
    fontName='Helvetica',
    fontSize=9,
    textColor=TEXT_LIGHT,
    alignment=TA_CENTER
))

styles.add(ParagraphStyle(
    name='Caption',
    fontName='Helvetica-Oblique',
    fontSize=9,
    textColor=TEXT_LIGHT,
    alignment=TA_CENTER,
    spaceBefore=4,
    spaceAfter=10
))

# --- Custom Flowables ---
class HorizontalLine(Flowable):
    def __init__(self, width, color=PRIMARY_LIGHT, thickness=1):
        Flowable.__init__(self)
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = thickness + 4

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)

class BoxedText(Flowable):
    def __init__(self, text, width, bg_color=BG_LIGHT, text_color=TEXT_DARK, padding=10, height=70):
        Flowable.__init__(self)
        self.text = text
        self.box_width = width
        self.bg_color = bg_color
        self.text_color = text_color
        self.padding = padding
        self.height = height

    def draw(self):
        self.canv.setFillColor(self.bg_color)
        self.canv.roundRect(0, 0, self.box_width, self.height, 5, fill=1, stroke=0)
        self.canv.setFillColor(self.text_color)
        self.canv.setFont("Helvetica", 9)
        text_obj = self.canv.beginText(self.padding, self.height - 15)
        for line in self.text.split('\n'):
            text_obj.textLine(line)
        self.canv.drawText(text_obj)

# --- Diagram Generators ---
def create_architecture_diagram():
    """Creates system architecture diagram with security boundaries."""
    d = Drawing(450, 200)
    
    # Background
    d.add(Rect(0, 0, 450, 200, fillColor=HexColor("#fafafa"), strokeColor=None))
    
    # Title
    d.add(String(225, 185, "QSTCS High-Level Architecture", fontSize=11, fontName='Helvetica-Bold', textAnchor='middle', fillColor=PRIMARY_DARK))
    
    # Security Boundary Box
    d.add(Rect(130, 10, 210, 160, fillColor=None, strokeColor=PRIMARY_DARK, strokeWidth=1.5, strokeDashArray=[4,2], rx=8))
    d.add(String(235, 155, "Trusted Security Perimeter", fontSize=7, fontName='Helvetica-Oblique', textAnchor='middle', fillColor=PRIMARY_DARK))
    
    # Soldier Devices (Left - Outside boundary)
    d.add(Rect(15, 100, 75, 45, fillColor=ACCENT_TEAL, strokeColor=PRIMARY_DARK, strokeWidth=1, rx=4))
    d.add(String(52, 127, "Field Device A", fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(52, 113, "(Authenticated)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    d.add(Rect(15, 35, 75, 45, fillColor=ACCENT_TEAL, strokeColor=PRIMARY_DARK, strokeWidth=1, rx=4))
    d.add(String(52, 62, "Field Device B", fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(52, 48, "(Authenticated)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Gateway (Inside boundary)
    d.add(Rect(145, 70, 60, 40, fillColor=ACCENT_GOLD, strokeColor=PRIMARY_DARK, strokeWidth=1, rx=4))
    d.add(String(175, 95, "Gateway", fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=TEXT_DARK))
    d.add(String(175, 82, "(TLS 1.3)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=TEXT_DARK))
    
    # KMS (Center - Core)
    d.add(Rect(220, 70, 65, 40, fillColor=PRIMARY_LIGHT, strokeColor=PRIMARY_DARK, strokeWidth=2, rx=4))
    d.add(String(252, 95, "KMS", fontSize=9, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(252, 82, "(Key Authority)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Qiskit Simulator (Right - Inside boundary)
    d.add(Rect(300, 70, 70, 40, fillColor=PRIMARY_DARK, strokeColor=ACCENT_GOLD, strokeWidth=2, rx=4))
    d.add(String(335, 95, "BB84 Engine", fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(335, 82, "(QKD Sim)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Dashboard (Outside boundary - Right)
    d.add(Rect(360, 130, 70, 35, fillColor=SUCCESS_GREEN, strokeColor=PRIMARY_DARK, strokeWidth=1, rx=4))
    d.add(String(395, 152, "SOC Dashboard", fontSize=7, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(395, 140, "(Read-Only)", fontSize=6, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Arrows with labels
    d.add(Line(90, 122, 145, 95, strokeColor=grey, strokeWidth=1.2))
    d.add(Line(90, 57, 145, 85, strokeColor=grey, strokeWidth=1.2))
    d.add(Line(205, 90, 220, 90, strokeColor=grey, strokeWidth=1.2))
    d.add(Line(285, 90, 300, 90, strokeColor=grey, strokeWidth=1.2))
    d.add(Line(285, 105, 360, 140, strokeColor=grey, strokeWidth=1.2))
    
    return d

def create_bb84_protocol_diagram():
    """Creates detailed BB84 protocol flow with quantum mechanics annotations."""
    d = Drawing(450, 160)
    d.add(Rect(0, 0, 450, 160, fillColor=HexColor("#fafafa"), strokeColor=None))
    d.add(String(225, 148, "BB84 Quantum Key Distribution Protocol", fontSize=10, fontName='Helvetica-Bold', textAnchor='middle', fillColor=PRIMARY_DARK))
    
    # Phase boxes
    phases = [
        (20, "Phase 1", "Preparation", PRIMARY_LIGHT),
        (120, "Phase 2", "Transmission", ACCENT_GOLD),
        (220, "Phase 3", "Sifting", ACCENT_TEAL),
        (320, "Phase 4", "Verification", SUCCESS_GREEN),
    ]
    
    for x, title, subtitle, color in phases:
        d.add(Rect(x, 70, 80, 55, fillColor=color, strokeColor=None, rx=4))
        d.add(String(x+40, 110, title, fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
        d.add(String(x+40, 95, subtitle, fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Arrows between phases
    for x in [100, 200, 300]:
        d.add(Line(x, 97, x+20, 97, strokeColor=grey, strokeWidth=1.5))
    
    # Channel labels
    d.add(Rect(100, 35, 130, 22, fillColor=HexColor("#fff3e0"), strokeColor=ACCENT_GOLD, strokeWidth=1, rx=3))
    d.add(String(165, 48, "Quantum Channel (Qubits)", fontSize=7, fontName='Helvetica-Bold', textAnchor='middle', fillColor=TEXT_DARK))
    
    d.add(Rect(220, 35, 130, 22, fillColor=BG_LIGHT, strokeColor=grey, strokeWidth=1, rx=3))
    d.add(String(285, 48, "Classical Channel (Bases)", fontSize=7, fontName='Helvetica-Bold', textAnchor='middle', fillColor=TEXT_DARK))
    
    # Output
    d.add(Rect(410, 75, 35, 45, fillColor=PRIMARY_DARK, strokeColor=None, rx=3))
    d.add(String(427, 105, "256b", fontSize=7, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(427, 92, "Key", fontSize=7, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    
    d.add(Line(400, 97, 410, 97, strokeColor=grey, strokeWidth=1.5))
    
    return d

def create_threat_model_diagram():
    """Creates threat model visualization."""
    d = Drawing(450, 120)
    d.add(Rect(0, 0, 450, 120, fillColor=HexColor("#fafafa"), strokeColor=None))
    d.add(String(225, 108, "Threat Model: Quantum Channel Eavesdropping", fontSize=10, fontName='Helvetica-Bold', textAnchor='middle', fillColor=PRIMARY_DARK))
    
    # Alice
    d.add(Rect(20, 40, 60, 40, fillColor=PRIMARY_LIGHT, strokeColor=None, rx=4))
    d.add(String(50, 65, "Alice", fontSize=9, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(50, 52, "(HQ)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Eve (Attacker)
    d.add(Rect(180, 40, 60, 40, fillColor=DANGER_RED, strokeColor=None, rx=4))
    d.add(String(210, 65, "Eve", fontSize=9, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(210, 52, "(Adversary)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Bob
    d.add(Rect(340, 40, 60, 40, fillColor=ACCENT_TEAL, strokeColor=None, rx=4))
    d.add(String(370, 65, "Bob", fontSize=9, fontName='Helvetica-Bold', textAnchor='middle', fillColor=white))
    d.add(String(370, 52, "(Field)", fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=white))
    
    # Channel
    d.add(Line(80, 60, 180, 60, strokeColor=ACCENT_GOLD, strokeWidth=2))
    d.add(Line(240, 60, 340, 60, strokeColor=ACCENT_GOLD, strokeWidth=2))
    
    # Intercept arrows
    d.add(Line(210, 40, 210, 25, strokeColor=DANGER_RED, strokeWidth=1.5))
    d.add(String(210, 15, "Measure & Resend", fontSize=7, fontName='Helvetica-Bold', textAnchor='middle', fillColor=DANGER_RED))
    
    # Result
    d.add(String(420, 60, "QBER", fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=DANGER_RED))
    d.add(String(420, 48, ">25%", fontSize=8, fontName='Helvetica-Bold', textAnchor='middle', fillColor=DANGER_RED))
    
    return d

def create_qber_chart():
    """Creates QBER comparison chart with security threshold."""
    d = Drawing(280, 130)
    d.add(Rect(0, 0, 280, 130, fillColor=HexColor("#fafafa"), strokeColor=None))
    
    bc = VerticalBarChart()
    bc.x = 45
    bc.y = 25
    bc.height = 75
    bc.width = 180
    bc.data = [[2, 25]]  # Normal QBER ~2%, Attack QBER ~25%
    bc.strokeColor = None
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 30
    bc.valueAxis.valueStep = 10
    bc.valueAxis.labels.fontName = 'Helvetica'
    bc.valueAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fontName = 'Helvetica'
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.categoryNames = ['Secure Link', 'Eve Intercept']
    bc.bars[0].fillColor = SUCCESS_GREEN
    bc.bars[0].strokeColor = None
    bc.bars[(0, 1)].fillColor = DANGER_RED
    
    d.add(bc)
    d.add(String(135, 115, "QBER Analysis (%)", fontSize=9, fontName='Helvetica-Bold', textAnchor='middle', fillColor=PRIMARY_DARK))
    
    # 11% threshold line
    threshold_y = 25 + (11/30) * 75  # Calculate position
    d.add(Line(45, threshold_y, 225, threshold_y, strokeColor=DANGER_RED, strokeWidth=1, strokeDashArray=[3,2]))
    d.add(String(235, threshold_y-3, "11%", fontSize=7, fontName='Helvetica-Bold', fillColor=DANGER_RED))
    d.add(String(265, threshold_y-3, "Abort", fontSize=6, fontName='Helvetica', fillColor=DANGER_RED))
    
    return d

# --- Page Number and Header Function ---
def add_page_elements(canvas, doc):
    page_num = canvas.getPageNumber()
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(TEXT_LIGHT)
    canvas.drawCentredString(A4[0]/2, 0.4*inch, f"QSTCS Technical Report | Page {page_num}")
    canvas.drawRightString(A4[0] - 0.75*inch, A4[1] - 0.5*inch, "UNCLASSIFIED")
    canvas.restoreState()

# --- Main Report Builder ---
def build_report():
    filename = "Quantum_Safe_System_Report.pdf"
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=0.7*inch,
        leftMargin=0.7*inch,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch
    )
    
    story = []
    page_width = A4[0] - 1.4*inch
    
    # ============================================================
    # PAGE 1: COVER PAGE
    # ============================================================
    story.append(Spacer(1, 1.2*inch))
    story.append(Paragraph("QUANTUM-SAFE TACTICAL", styles['MainTitle']))
    story.append(Paragraph("COMMUNICATION SYSTEM", styles['MainTitle']))
    story.append(Spacer(1, 0.2*inch))
    story.append(HorizontalLine(page_width, color=ACCENT_GOLD, thickness=2))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Technical Architecture and Security Analysis", styles['Subtitle']))
    story.append(Paragraph("Submitted for iDEX Defence Innovation Challenge", styles['Subtitle']))
    story.append(Spacer(1, 0.6*inch))
    
    story.append(create_architecture_diagram())
    story.append(Paragraph("Figure 1: High-level system architecture showing trusted security perimeter and component relationships.", styles['Caption']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("A software-defined quantum key distribution prototype enabling provably secure tactical communications resistant to both classical and quantum cryptanalytic attacks.", styles['Callout']))
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph("Document Version 2.0 | Classification: UNCLASSIFIED | January 2026", styles['Footer']))
    story.append(PageBreak())
    
    # ============================================================
    # PAGE 2: TABLE OF CONTENTS + EXECUTIVE SUMMARY
    # ============================================================
    story.append(Paragraph("Contents", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    story.append(Spacer(1, 0.15*inch))
    
    toc_items = [
        ("1. Executive Summary", "2"),
        ("2. Threat Landscape and Motivation", "2"),
        ("3. System Architecture", "3"),
        ("4. BB84 Protocol Implementation", "4"),
        ("5. Security Analysis", "4"),
        ("6. Operational Workflow", "5"),
        ("7. Technical Specifications", "5"),
        ("8. Conclusion and Roadmap", "6"),
    ]
    for item, page in toc_items:
        story.append(Paragraph(f"{item} {'.' * (50 - len(item))} {page}", styles['TOCEntry']))
    
    story.append(Spacer(1, 0.25*inch))
    
    # EXECUTIVE SUMMARY
    story.append(Paragraph("1. Executive Summary", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    story.append(Paragraph(
        """The Quantum-Safe Tactical Communication System (QSTCS) is a prototype secure messaging 
        platform designed for military field operations. Unlike conventional encryption schemes 
        whose security relies on computational hardness assumptions vulnerable to quantum algorithms, 
        QSTCS implements the BB84 Quantum Key Distribution (QKD) protocol, which derives its 
        security guarantees from the fundamental laws of quantum mechanics.""",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        """The system provides three critical capabilities: (1) generation of cryptographic keys 
        with information-theoretic security, (2) real-time detection of eavesdropping attempts 
        through Quantum Bit Error Rate (QBER) monitoring, and (3) authenticated encryption of 
        tactical messages using AES-256-GCM with quantum-derived keys. This design addresses the 
        "harvest now, decrypt later" threat posed by adversaries stockpiling encrypted traffic 
        for future quantum decryption.""",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        "Key Innovation: Software-defined QKD simulation enabling rapid prototyping and seamless migration to hardware QKD infrastructure when deployed.",
        styles['Callout']
    ))
    story.append(Spacer(1, 0.15*inch))
    
    # THREAT LANDSCAPE
    story.append(Paragraph("2. Threat Landscape and Motivation", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    
    story.append(Paragraph("2.1 The Quantum Computing Threat", styles['SubHeading']))
    story.append(Paragraph(
        """Current asymmetric cryptographic systems (RSA, ECDH, DSA) rely on the computational 
        intractability of integer factorization and discrete logarithm problems. Shor's algorithm, 
        executable on a sufficiently powerful quantum computer, solves these problems in polynomial 
        time, rendering RSA-2048 and ECDH-256 effectively broken. While fault-tolerant quantum 
        computers capable of running Shor's algorithm at scale do not yet exist, intelligence 
        agencies assess their emergence within 10-15 years.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("2.2 Harvest Now, Decrypt Later (HNDL)", styles['SubHeading']))
    story.append(Paragraph(
        """Adversaries are actively intercepting and storing encrypted communications with the 
        intent to decrypt them once quantum capabilities mature. For classified military 
        communications with long-term sensitivity (strategic plans, intelligence sources, treaty 
        negotiations), this represents an immediate operational risk. Data encrypted today using 
        RSA or ECDH should be considered compromised against a patient adversary.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("2.3 Why Quantum Key Distribution?", styles['SubHeading']))
    story.append(Paragraph(
        """QKD protocols like BB84 provide information-theoretic security: their security does not 
        depend on computational assumptions but on physical laws. Specifically, the no-cloning 
        theorem guarantees that an eavesdropper cannot copy quantum states without detection, 
        and measurement disturbance ensures any interception attempt introduces detectable errors. 
        This makes QKD-derived keys provably secure against all computational attacks, including 
        those from future quantum computers.""",
        styles['CustomBody']
    ))
    
    # Comparison Table
    threat_data = [
        ['Security Property', 'RSA/ECDH', 'PQC (Kyber)', 'QKD (BB84)'],
        ['Security Basis', 'Math Hardness', 'Lattice Problems', 'Physics Laws'],
        ['Quantum Resistant', 'No', 'Believed Yes', 'Proven Yes'],
        ['Eavesdrop Detection', 'None', 'None', 'Built-in (QBER)'],
        ['Key Compromise', 'Silent', 'Silent', 'Detected'],
        ['Maturity', 'Deployed', 'Standardizing', 'Prototype'],
    ]
    threat_table = Table(threat_data, colWidths=[1.5*inch, 1.3*inch, 1.3*inch, 1.3*inch])
    threat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (-1,-1), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(Spacer(1, 0.1*inch))
    story.append(threat_table)
    story.append(Paragraph("Table 1: Comparative security properties of key establishment mechanisms.", styles['Caption']))
    story.append(PageBreak())
    
    # ============================================================
    # PAGE 3: SYSTEM ARCHITECTURE
    # ============================================================
    story.append(Paragraph("3. System Architecture", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    story.append(Paragraph(
        """QSTCS employs a modular architecture separating cryptographic key generation, key 
        management, and message encryption into distinct components. This design enables 
        independent security auditing and facilitates future hardware integration.""",
        styles['CustomBody']
    ))
    story.append(create_architecture_diagram())
    story.append(Paragraph("Figure 2: Component architecture with security boundary delineation.", styles['Caption']))
    
    story.append(Paragraph("3.1 BB84 Quantum Engine", styles['SubHeading']))
    story.append(Paragraph(
        """The core cryptographic module implementing the BB84 QKD protocol. In the current 
        prototype, quantum operations are simulated using classical randomness with 
        physics-accurate error modeling. The engine executes the complete BB84 workflow: random 
        bit and basis generation, qubit state preparation, basis-dependent measurement simulation, 
        sifting, and QBER calculation. The simulation accurately models eavesdropper-induced 
        disturbance, producing ~25% QBER under intercept-resend attacks as predicted by quantum 
        information theory.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("3.2 Key Management Service (KMS)", styles['SubHeading']))
    story.append(Paragraph(
        """The trusted authority responsible for key lifecycle management. Upon receiving a key 
        request, the KMS invokes the BB84 engine, validates the generated key against the QBER 
        threshold (11%), and derives session keys using HKDF-SHA256. The KMS maintains session 
        state, tracks key usage, and enforces key rotation policies. All key material is held 
        only in volatile memory with no persistent storage.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("3.3 Field Device Clients", styles['SubHeading']))
    story.append(Paragraph(
        """Tactical endpoints (ruggedized laptops, mobile devices) that authenticate to the KMS 
        and obtain session keys. Clients perform AES-256-GCM encryption/decryption locally, 
        ensuring plaintext never leaves the device. Each message includes a unique 96-bit nonce 
        and 128-bit authentication tag, providing both confidentiality and integrity.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("3.4 Network Gateway", styles['SubHeading']))
    story.append(Paragraph(
        """Message routing infrastructure connecting field devices to the KMS and to each other. 
        The gateway handles only ciphertext and cannot access plaintext. Transport security 
        (TLS 1.3) provides defense-in-depth, but primary security relies on the quantum-derived 
        symmetric keys.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("3.5 Security Operations Dashboard", styles['SubHeading']))
    story.append(Paragraph(
        """Read-only monitoring interface displaying real-time system health: link status 
        (secure/compromised), QBER measurements, key issuance rate, and detected attack attempts. 
        Provides situational awareness for security operations center (SOC) personnel without 
        granting key access.""",
        styles['CustomBody']
    ))
    story.append(PageBreak())
    
    # ============================================================
    # PAGE 4: BB84 PROTOCOL + SECURITY ANALYSIS
    # ============================================================
    story.append(Paragraph("4. BB84 Protocol Implementation", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    
    story.append(create_bb84_protocol_diagram())
    story.append(Paragraph("Figure 3: BB84 protocol phases from preparation through verified key output.", styles['Caption']))
    
    story.append(Paragraph("4.1 Protocol Phases", styles['SubHeading']))
    
    phases_data = [
        ['Phase', 'Alice (Sender)', 'Bob (Receiver)', 'Output'],
        ['Preparation', 'Generate random bits b[i], bases B[i]', '-', 'Qubit states'],
        ['Transmission', 'Encode: |0>,|1>,|+>,|-> per b[i],B[i]', 'Choose random bases B\'[i]', 'Measured bits'],
        ['Sifting', 'Announce B[i] over classical channel', 'Compare B\'[i], keep matches', 'Sifted key (~50%)'],
        ['Verification', 'Sample subset, compute QBER', 'QBER < 11%: Accept', '256-bit raw key'],
    ]
    phases_table = Table(phases_data, colWidths=[0.8*inch, 1.9*inch, 1.8*inch, 1.1*inch])
    phases_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (-1,-1), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(phases_table)
    story.append(Paragraph("Table 2: BB84 protocol execution showing Alice and Bob operations per phase.", styles['Caption']))
    
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("5. Security Analysis", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    
    story.append(Paragraph("5.1 Eavesdropper Detection via QBER", styles['SubHeading']))
    story.append(Paragraph(
        """The security of BB84 relies on the quantum mechanical principle that measurement 
        disturbs quantum states. When an eavesdropper (Eve) intercepts qubits, she must measure 
        them to extract information. If Eve chooses the wrong measurement basis (50% probability), 
        her measurement projects the qubit into a random state. When Bob subsequently measures 
        with the correct basis, he obtains an incorrect result with 50% probability. The combined 
        effect: Eve's interception of all qubits introduces approximately 25% error rate in the 
        sifted key.""",
        styles['CustomBody']
    ))
    
    story.append(create_threat_model_diagram())
    story.append(Paragraph("Figure 4: Intercept-resend attack model showing Eve's measurement-induced disturbance.", styles['Caption']))
    
    story.append(Paragraph("5.2 Security Threshold Rationale", styles['SubHeading']))
    story.append(Paragraph(
        """The 11% QBER threshold is derived from information-theoretic security proofs for BB84. 
        Below this threshold, sufficient secret key can be extracted through privacy amplification 
        even if Eve obtained partial information. Above 11%, the protocol cannot guarantee secrecy 
        and must abort. Our implementation conservatively refuses key issuance at QBER > 11%, 
        alerting operators via the dashboard.""",
        styles['CustomBody']
    ))
    
    story.append(create_qber_chart())
    story.append(Paragraph("Figure 5: Measured QBER comparison between secure transmission (~2%) and active eavesdropping (~25%).", styles['Caption']))
    story.append(PageBreak())
    
    # ============================================================
    # PAGE 5: OPERATIONAL WORKFLOW + TECHNICAL SPECS
    # ============================================================
    story.append(Paragraph("6. Operational Workflow", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    story.append(Paragraph(
        """The following sequence illustrates a complete secure message exchange between two 
        field units, demonstrating the integration of quantum key distribution with classical 
        authenticated encryption.""",
        styles['CustomBody']
    ))
    
    workflow_data = [
        ['Step', 'Operation', 'Security Property'],
        ['1', 'Device A authenticates to KMS, requests session key', 'Device identity verified'],
        ['2', 'KMS executes BB84 simulation (512 qubits)', 'Quantum randomness generated'],
        ['3', 'Sifting produces ~256 correlated bits', 'Basis reconciliation complete'],
        ['4', 'KMS computes QBER; verifies < 11% threshold', 'No eavesdropper detected'],
        ['5', 'KMS derives AES-256 key via HKDF-SHA256', 'Key strengthening applied'],
        ['6', 'Session key returned to Device A', 'Secure key established'],
        ['7', 'Device A encrypts message (AES-256-GCM)', 'Confidentiality + integrity'],
        ['8', 'Ciphertext transmitted via Gateway', 'Defense-in-depth (TLS)'],
        ['9', 'Device B obtains session key from KMS', 'Symmetric key agreement'],
        ['10', 'Device B decrypts and verifies auth tag', 'Message authenticity confirmed'],
    ]
    workflow_table = Table(workflow_data, colWidths=[0.5*inch, 3.2*inch, 1.9*inch])
    workflow_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (1,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (-1,-1), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (1,0), (1,-1), 6),
    ]))
    story.append(workflow_table)
    story.append(Paragraph("Table 3: End-to-end message security workflow with cryptographic properties per step.", styles['Caption']))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("7. Technical Specifications", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    
    tech_data = [
        ['Component', 'Technology', 'Specification'],
        ['Key Generation', 'BB84 Simulation', '512 qubits, ~256-bit sifted key'],
        ['Key Derivation', 'HKDF-SHA256', '256-bit session key output'],
        ['Symmetric Cipher', 'AES-256-GCM', '96-bit nonce, 128-bit auth tag'],
        ['QBER Threshold', 'Information-theoretic', '11% abort threshold'],
        ['Transport', 'TLS 1.3', 'Defense-in-depth only'],
        ['Dashboard', 'Streamlit', 'Real-time SOC monitoring'],
        ['Runtime', 'Python 3.8+', 'Cross-platform deployment'],
    ]
    tech_table = Table(tech_data, colWidths=[1.4*inch, 1.6*inch, 2.5*inch])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (-1,-1), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tech_table)
    story.append(Paragraph("Table 4: Technical specifications and cryptographic parameters.", styles['Caption']))
    
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("Source Code Structure:", styles['SubHeading']))
    code_block = """quantum-tactical-comms/
|-- quantum_engine/bb84_simulator.py   # BB84 QKD protocol implementation
|-- kms/key_management_service.py      # Key authority and lifecycle management
|-- devices/client.py                  # Field device encryption client
|-- gateway/network_gateway.py         # Message routing infrastructure
|-- dashboard/dashboard_ui.py          # SOC monitoring interface (Streamlit)
|-- main.py                            # Console demonstration entry point
|-- tests/                             # Automated security verification tests"""
    story.append(BoxedText(code_block, page_width, height=80))
    story.append(PageBreak())
    
    # ============================================================
    # PAGE 6: CONCLUSION + ROADMAP
    # ============================================================
    story.append(Paragraph("8. Conclusion and Development Roadmap", styles['SectionHeading']))
    story.append(HorizontalLine(page_width, color=PRIMARY_LIGHT, thickness=1))
    
    story.append(Paragraph("8.1 Summary of Achievements", styles['SubHeading']))
    story.append(Paragraph(
        """QSTCS demonstrates a complete, functional prototype of quantum-safe tactical 
        communications. The system successfully implements BB84 key distribution with accurate 
        eavesdropper detection, integrates HKDF-based key derivation and AES-256-GCM encryption, 
        and provides real-time security monitoring. Automated tests verify both normal operation 
        (QBER ~0-3%) and attack detection (QBER ~25% triggering abort).""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph(
        """The software-defined architecture enables immediate deployment for training, 
        evaluation, and operational concept development. The modular design positions the system 
        for seamless transition to hardware QKD when tactically appropriate.""",
        styles['CustomBody']
    ))
    
    story.append(Paragraph("8.2 Development Roadmap", styles['SubHeading']))
    
    roadmap_data = [
        ['Phase', 'Capability', 'Timeline'],
        ['Current', 'Software QKD simulation, full encryption stack', 'Complete'],
        ['Near-term', 'Integration with commercial QKD hardware (QNu Labs)', '6-12 months'],
        ['Near-term', 'Hybrid PQC fallback (CRYSTALS-Kyber + BB84)', '6-12 months'],
        ['Mid-term', 'Multi-node mesh networking with key relay', '12-18 months'],
        ['Mid-term', 'Mobile platform clients (Android/iOS)', '12-18 months'],
        ['Long-term', 'Satellite QKD integration for global reach', '24+ months'],
    ]
    roadmap_table = Table(roadmap_data, colWidths=[1*inch, 3.3*inch, 1.3*inch])
    roadmap_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (0,1), SUCCESS_GREEN),
        ('TEXTCOLOR', (0,1), (0,1), white),
        ('BACKGROUND', (0,2), (-1,-1), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(roadmap_table)
    story.append(Paragraph("Table 5: Development roadmap from current prototype to operational deployment.", styles['Caption']))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("8.3 Strategic Value Proposition", styles['SubHeading']))
    story.append(Paragraph(
        """QSTCS addresses a critical gap in defence communications: providing quantum-resistant 
        security at the tactical edge. Unlike backbone QKD networks (e.g., QNu Labs' metropolitan 
        deployments), QSTCS focuses on the "last mile" - bringing quantum-derived security directly 
        to soldiers, drones, and mobile command posts. The software-defined approach enables:""",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        """<b>1. Rapid Deployment:</b> No specialized hardware required for initial evaluation.
        <br/><b>2. Training and Doctrine Development:</b> Enables personnel familiarization with 
        quantum security concepts before hardware deployment.
        <br/><b>3. Future-Proofing:</b> Architecture designed for hardware QKD integration without 
        application-layer changes.
        <br/><b>4. Cost Efficiency:</b> Software simulation validates operational concepts before 
        capital investment in quantum hardware.""",
        styles['CustomBody']
    ))
    
    story.append(Spacer(1, 0.3*inch))
    story.append(HorizontalLine(page_width, color=ACCENT_GOLD, thickness=2))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph(
        "This document and the accompanying prototype demonstrate readiness for Phase II development "
        "and operational pilot deployment. For technical inquiries or demonstration requests, "
        "contact the development team.",
        styles['CustomBody']
    ))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("--- END OF DOCUMENT ---", styles['Footer']))
    
    # Build PDF
    doc.build(story, onFirstPage=add_page_elements, onLaterPages=add_page_elements)
    print(f"Defense-grade PDF generated: {filename}")
    return filename

if __name__ == "__main__":
    build_report()
