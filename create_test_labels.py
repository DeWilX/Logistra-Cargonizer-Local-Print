"""Regenerate the bundled labels: python create_test_labels.py --font-dir FONT_DIR.

Requires ReportLab for authoring only; the packaged app uses the generated PDFs.
The font directory must contain DejaVuSans.ttf; DejaVuSans-Bold.ttf is optional.
"""
import argparse
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.graphics.barcode.code128 import Code128

LABELS = {
    'lv': ['TESTA DRUKA', 'Printera pārbaude', 'Izmērs: 102 x 192 mm',
           'Drukā 100% mērogā, bez pielāgošanas.', 'Šī nav sūtījuma etiķete.',
           'Mēroga pārbaude: 50 mm', 'Kontrasts',
           'Pārbaudi malas, tekstu un svītrkodu.', 'Pēc drukas apstiprini rezultātu lietotnē.'],
    'en': ['TEST PRINT', 'Printer check', 'Size: 102 x 192 mm',
           'Print at 100% scale, without resizing.', 'This is not a shipping label.',
           'Scale check: 50 mm', 'Contrast',
           'Check the edges, text and barcode.', 'After printing, confirm the result in the app.'],
    'nb': ['TESTUTSKRIFT', 'Skriverkontroll', 'Størrelse: 102 x 192 mm',
           'Skriv ut i 100 % skala, uten tilpasning.', 'Dette er ikke en fraktetikett.',
           'Skalakontroll: 50 mm', 'Kontrast',
           'Kontroller kanter, tekst og strekkode.', 'Bekreft resultatet i appen etter utskrift.'],
}


def create_labels(font_dir):
    pdfmetrics.registerFont(TTFont('LabelSans', str(font_dir / 'DejaVuSans.ttf')))
    bold_path = font_dir / 'DejaVuSans-Bold.ttf'
    pdfmetrics.registerFont(TTFont('LabelBold', str(bold_path if bold_path.exists() else font_dir / 'DejaVuSans.ttf')))
    output = Path(__file__).resolve().parent / 'assets'
    width, height = 102 * mm, 192 * mm
    for language, words in LABELS.items():
        pdf = canvas.Canvas(str(output / f'default-test-label-{language}.pdf'), pagesize=(width, height),
                            pageCompression=1, invariant=1)
        pdf.setTitle('Logistra Print - ' + words[0])
        pdf.setAuthor('Logistra Print')
        pdf.setLineWidth(.7)
        pdf.rect(4*mm, 4*mm, 94*mm, 184*mm)
        def text(value, y, size=10, bold=False):
            font = 'LabelBold' if bold else 'LabelSans'
            assert pdfmetrics.stringWidth(value, font, size) <= 84*mm, value
            pdf.setFont(font, size)
            if bold and not bold_path.exists():
                pdf.saveState()
                pdf.setLineWidth(.22)
                run = pdf.beginText(9*mm, y*mm)
                run.setTextRenderMode(2)
                run.textLine(value)
                pdf.drawText(run)
                pdf.restoreState()
            else:
                pdf.drawString(9*mm, y*mm, value)
        text('Logistra Print', 176, 19, True)
        text(words[0], 165, 12, True)
        pdf.line(9*mm, 157*mm, 93*mm, 157*mm)
        text(words[1], 146, 12, True)
        text(words[2], 136)
        text(words[3], 128, 8.5)
        text(words[4], 120, 10, True)
        barcode = Code128('LOGISTRA-TEST-0001', barHeight=22*mm, barWidth=.29*mm)
        barcode.drawOn(pdf, (width-barcode.width)/2, 91*mm)
        pdf.setFont('LabelSans', 9)
        pdf.drawCentredString(width/2, 84*mm, 'LOGISTRA-TEST-0001')
        text(words[5], 71, 9)
        pdf.line(10*mm, 62*mm, 60*mm, 62*mm)
        for x in range(10, 61, 10):
            pdf.line(x*mm, 60*mm, x*mm, 64*mm)
        text(words[6], 50, 10, True)
        for index, shade in enumerate((0, .2, .4, .6, .8, 1)):
            pdf.setFillGray(shade)
            pdf.rect((9+index*14)*mm, 37*mm, 14*mm, 7*mm, fill=1, stroke=1)
        pdf.setFillGray(0)
        text(words[7], 24, 8.5)
        text(words[8], 15, 8.2)
        pdf.showPage()
        pdf.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir', required=True, type=Path)
    create_labels(parser.parse_args().font_dir)
