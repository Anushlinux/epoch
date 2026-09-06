"""Initial renderer: draws complete content, but never advances an overflowing page.

This is the preserved faulty implementation, not a candidate or successful fallback.
"""


def render_pdf(document):
    import io
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph, Table, TableStyle

    pdfmetrics.registerFont(TTFont("Body", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(
        TTFont("Strong", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    )
    out = io.BytesIO()
    canvas = Canvas(out, pagesize=A4)
    width, height = A4
    left, available, y = 42, width - 84, height - 42
    normal = ParagraphStyle("normal", fontName="Body", fontSize=11, leading=16, spaceAfter=10)
    heading = ParagraphStyle("heading", fontName="Strong", fontSize=16, leading=22, spaceAfter=12)
    parts = [("heading", document["title"])]
    for block in document["blocks"]:
        if block["kind"] in ("heading", "paragraph"):
            parts.append((block["kind"], block["text"]))
        elif block["kind"] == "bullets":
            parts.extend(("paragraph", "• " + text) for text in block["items"])
        else:
            parts.append(("table", block["rows"]))
    for kind, value in parts:
        if kind == "table":
            flow = Table(
                [[Paragraph(escape(cell), normal) for cell in row] for row in value],
                colWidths=[available / len(value[0])] * len(value[0]),
            )
            flow.setStyle(
                TableStyle(
                    [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]
                )
            )
        else:
            flow = Paragraph(
                escape(value).replace("\n", "<br/>"), heading if kind == "heading" else normal
            )
        _, used = flow.wrap(available, 100000)
        y -= used
        flow.drawOn(canvas, left, y)
        y -= 12
    canvas.save()
    return out.getvalue()
