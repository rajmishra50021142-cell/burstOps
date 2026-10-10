#!/usr/bin/env python3
"""
generate_documentation_pdfs.py
Generates two high-quality, professional, beautifully formatted PDFs from:
1. README_PROJECT_AND_AZURE_ARCHITECTURE.md -> BURSTOPS_PROJECT_AND_AZURE_ARCHITECTURE.pdf
2. README_CODEBASE_AND_CONTAINERS.md -> BURSTOPS_CODEBASE_AND_CONTAINERS.pdf
"""

import os
import re
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page count."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            header_text = getattr(self, "doc_header_title", "BurstOps Engineering Documentation — Microsoft Azure Architecture")
            self.drawString(36, 11 * inch - 28, header_text)
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 11 * inch - 34, 8.5 * inch - 36, 11 * inch - 34)
            
        # Footer (All pages)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 36, 24, page_str)
        self.drawString(36, 24, "BurstOps Technical Specification & Reference Manual — Confidential & Proprietary")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 32, 8.5 * inch - 36, 32)
        
        self.restoreState()


def get_styles():
    base_styles = getSampleStyleSheet()
    
    c_primary = colors.HexColor("#1E3A8A")    # Deep Azure Navy
    c_secondary = colors.HexColor("#0284C7")  # Azure Sky Blue
    c_dark = colors.HexColor("#0F172A")       # Slate 900
    c_body = colors.HexColor("#334155")       # Slate 700
    
    styles = {
        'DocTitle': ParagraphStyle(
            'DocTitle',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=c_primary,
            spaceAfter=4
        ),
        'DocSub': ParagraphStyle(
            'DocSub',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10
        ),
        'H1': ParagraphStyle(
            'H1',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=c_primary,
            spaceBefore=12,
            spaceAfter=4,
            keepWithNext=True
        ),
        'H2': ParagraphStyle(
            'H2',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10.5,
            leading=13.5,
            textColor=c_secondary,
            spaceBefore=9,
            spaceAfter=3,
            keepWithNext=True
        ),
        'H3': ParagraphStyle(
            'H3',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=c_dark,
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True
        ),
        'Body': ParagraphStyle(
            'Body',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=c_body,
            spaceAfter=4
        ),
        'Bullet': ParagraphStyle(
            'Bullet',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=c_body,
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=2.5
        ),
        'CalloutText': ParagraphStyle(
            'CalloutText',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10.5,
            textColor=colors.HexColor("#0369A1")
        ),
        'CodeLine': ParagraphStyle(
            'CodeLine',
            parent=base_styles['Normal'],
            fontName='Courier',
            fontSize=6.5,
            leading=8.5,
            textColor=colors.HexColor("#0F172A")
        ),
        'TableHeader': ParagraphStyle(
            'TableHeader',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white
        ),
        'TableCell': ParagraphStyle(
            'TableCell',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            leading=9,
            textColor=c_body
        )
    }
    return styles


def format_inline_markdown(text):
    """Converts inline Markdown (bold, italic, code, links) to ReportLab XML."""
    if not text:
        return ""
    
    # 1. Escape HTML special characters
    # But preserve intended formatting markers
    text = html.escape(text, quote=False)
    
    # Convert bold: **text** or __text__ -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # Convert italic: *text* or _text_ -> <i>text</i>
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # Convert inline code: `code` -> <font face="Courier" color="#0369A1"><b>code</b></font>
    text = re.sub(r'`([^`]+)`', r'<font face="Courier" color="#0369A1"><b>\1</b></font>', text)
    
    # Convert markdown links: [label](url) -> <u><font color="#0284C7">label</font></u>
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'<u><font color="#0284C7">\1</font></u>', text)
    
    # Convert common LaTeX math formulas to readable text
    text = text.replace(r'$$', '')
    text = text.replace(r'$', '')
    text = text.replace(r'\Delta', 'Δ')
    text = text.replace(r'\approx', '≈')
    text = text.replace(r'\ge', '≥')
    text = text.replace(r'\le', '≤')
    text = text.replace(r'\to', '→')
    text = text.replace(r'\infty', '∞')
    text = text.replace(r'\cdot', '·')
    text = text.replace(r'\int_{0}^{t}', '∫[0..t]')
    text = text.replace(r'\text{', '').replace(r'}', '')
    text = text.replace(r'\lceil', '⌈').replace(r'\rceil', '⌉')
    text = text.replace(r'\times', '×')
    text = text.replace(r'\frac{', '(').replace(r'}{', ' / ')
    
    return text


def parse_markdown_to_flowables(md_content, styles, total_width=540):
    lines = md_content.splitlines()
    flowables = []
    
    i = 0
    n = len(lines)
    
    in_code_block = False
    code_lines = []
    code_lang = ""
    
    in_table = False
    table_rows = []
    
    in_callout = False
    callout_lines = []
    
    def flush_code():
        nonlocal code_lines, code_lang
        if not code_lines:
            return
        
        # Split large code blocks if more than 35 lines to prevent overflow
        max_chunk = 35
        for chunk_idx in range(0, len(code_lines), max_chunk):
            sub_chunk = code_lines[chunk_idx:chunk_idx + max_chunk]
            code_text = "\n".join(sub_chunk)
            
            # Use Preformatted inside a styled Table container
            pre = Preformatted(code_text, styles['CodeLine'])
            t = Table([[pre]], colWidths=[total_width])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            flowables.append(Spacer(1, 2))
            flowables.append(t)
            flowables.append(Spacer(1, 3))
            
        code_lines = []
        code_lang = ""

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        
        parsed_table_data = []
        # Filter separator row (e.g. |---|---|)
        valid_rows = [r for r in table_rows if not re.match(r'^\s*\|?\s*[-:]+[-| :]*\|?\s*$', r)]
        
        if not valid_rows:
            table_rows = []
            return
        
        num_cols = 0
        for r_idx, r_str in enumerate(valid_rows):
            # Split cells by pipe
            raw_cells = [c.strip() for c in r_str.split('|')]
            # Remove leading/trailing empty cells from outer pipes
            if raw_cells and raw_cells[0] == "":
                raw_cells = raw_cells[1:]
            if raw_cells and raw_cells[-1] == "":
                raw_cells = raw_cells[:-1]
            
            if not raw_cells:
                continue
                
            num_cols = max(num_cols, len(raw_cells))
            row_paras = []
            for c_text in raw_cells:
                formatted = format_inline_markdown(c_text)
                if r_idx == 0:
                    p = Paragraph(formatted, styles['TableHeader'])
                else:
                    p = Paragraph(formatted, styles['TableCell'])
                row_paras.append(p)
            parsed_table_data.append(row_paras)
            
        if parsed_table_data and num_cols > 0:
            # Ensure rectangular matrix
            for row in parsed_table_data:
                while len(row) < num_cols:
                    row.append(Paragraph("", styles['TableCell']))
            
            # Determine column widths
            if num_cols == 5:
                col_widths = [85, 80, 75, 210, 90]
            elif num_cols == 4:
                col_widths = [110, 130, 140, 160]
            elif num_cols == 3:
                col_widths = [140, 160, 240]
            elif num_cols == 2:
                col_widths = [200, 340]
            else:
                col_widths = [total_width / num_cols] * num_cols
                
            table_obj = Table(parsed_table_data, colWidths=col_widths, repeatRows=1)
            table_obj.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            flowables.append(Spacer(1, 3))
            flowables.append(table_obj)
            flowables.append(Spacer(1, 4))
            
        table_rows = []

    def flush_callout():
        nonlocal callout_lines
        if not callout_lines:
            return
        callout_text = "<br/>".join([format_inline_markdown(l) for l in callout_lines])
        p = Paragraph(callout_text, styles['CalloutText'])
        t = Table([[p]], colWidths=[total_width])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
            ('LINELEFT', (0, 0), (-1, -1), 2.5, colors.HexColor("#0284C7")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#BAE6FD")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        flowables.append(Spacer(1, 3))
        flowables.append(t)
        flowables.append(Spacer(1, 4))
        callout_lines = []

    while i < n:
        line = lines[i]
        stripped = line.strip()
        
        # 1. Fenced Code Block handling
        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                flush_code()
            else:
                if in_table:
                    flush_table()
                    in_table = False
                if in_callout:
                    flush_callout()
                    in_callout = False
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_lines = []
            i += 1
            continue
            
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue
            
        # 2. Markdown Table handling
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_callout:
                flush_callout()
                in_callout = False
            in_table = True
            table_rows.append(stripped)
            i += 1
            continue
        elif in_table:
            flush_table()
            in_table = False
            
        # 3. Blockquote / Callout handling
        if stripped.startswith(">"):
            in_callout = True
            callout_lines.append(stripped.lstrip(">").strip())
            i += 1
            continue
        elif in_callout and stripped == "":
            flush_callout()
            in_callout = False
            i += 1
            continue
        elif in_callout and not stripped.startswith(">"):
            flush_callout()
            in_callout = False
            
        # 4. Horizontal Rule
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', stripped):
            # Subtle divider
            t = Table([[""]], colWidths=[total_width], rowHeights=[1])
            t.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            flowables.append(Spacer(1, 4))
            flowables.append(t)
            flowables.append(Spacer(1, 4))
            i += 1
            continue
            
        # 5. Empty line
        if stripped == "":
            i += 1
            continue
            
        # 6. Headings
        if stripped.startswith("# "):
            title_text = format_inline_markdown(stripped[2:].strip())
            flowables.append(Paragraph(title_text, styles['DocTitle']))
            i += 1
            continue
        elif stripped.startswith("## "):
            h1_text = format_inline_markdown(stripped[3:].strip())
            flowables.append(Paragraph(h1_text, styles['H1']))
            i += 1
            continue
        elif stripped.startswith("### "):
            h2_text = format_inline_markdown(stripped[4:].strip())
            flowables.append(Paragraph(h2_text, styles['H2']))
            i += 1
            continue
        elif stripped.startswith("#### "):
            h3_text = format_inline_markdown(stripped[5:].strip())
            flowables.append(Paragraph(h3_text, styles['H3']))
            i += 1
            continue
            
        # 7. Bullet or Numbered List
        bullet_match = re.match(r'^([-*]|\d+\.)\s+(.+)$', stripped)
        if bullet_match:
            prefix = bullet_match.group(1)
            content = bullet_match.group(2)
            if prefix in ('-', '*'):
                bullet_char = "&bull;&nbsp;&nbsp;"
            else:
                bullet_char = f"<b>{prefix}</b>&nbsp;&nbsp;"
            formatted = bullet_char + format_inline_markdown(content)
            flowables.append(Paragraph(formatted, styles['Bullet']))
            i += 1
            continue
            
        # 8. Regular Body Paragraph
        formatted = format_inline_markdown(stripped)
        flowables.append(Paragraph(formatted, styles['Body']))
        i += 1

    # Final cleanup flushes
    if in_code_block:
        flush_code()
    if in_table:
        flush_table()
    if in_callout:
        flush_callout()
        
    return flowables


def build_architecture_pdf():
    md_file = "/Users/rajmishara/burstOps/README_PROJECT_AND_AZURE_ARCHITECTURE.md"
    pdf_file = "/Users/rajmishara/burstOps/BURSTOPS_PROJECT_AND_AZURE_ARCHITECTURE.pdf"
    
    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=42
    )
    
    styles = get_styles()
    printable_width = 8.5 * inch - 72  # 540 pt
    flowables = parse_markdown_to_flowables(md_content, styles, total_width=printable_width)
    
    # Custom NumberedCanvas callback
    def canvas_factory(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.doc_header_title = "BurstOps: Overall Architecture, Research Grounding & Azure Cloud Manual"
        return c

    print(f"Compiling {pdf_file}...")
    doc.build(flowables, canvasmaker=canvas_factory)
    print(f"SUCCESS: Generated {pdf_file} ({os.path.getsize(pdf_file):,} bytes)")


def build_codebase_pdf():
    md_file = "/Users/rajmishara/burstOps/README_CODEBASE_AND_CONTAINERS.md"
    pdf_file = "/Users/rajmishara/burstOps/BURSTOPS_CODEBASE_AND_CONTAINERS.pdf"
    
    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=42
    )
    
    styles = get_styles()
    printable_width = 8.5 * inch - 72  # 540 pt
    flowables = parse_markdown_to_flowables(md_content, styles, total_width=printable_width)
    
    def canvas_factory(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.doc_header_title = "BurstOps: Codebase Architecture, Docker Containers & Run Guide"
        return c

    print(f"Compiling {pdf_file}...")
    doc.build(flowables, canvasmaker=canvas_factory)
    print(f"SUCCESS: Generated {pdf_file} ({os.path.getsize(pdf_file):,} bytes)")


if __name__ == "__main__":
    build_architecture_pdf()
    build_codebase_pdf()
