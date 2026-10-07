"""Generate native application icons and crisp row actions from vector geometry."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent / 'assets'
root.mkdir(exist_ok=True)
im = Image.new('RGBA', (1024, 1024))
d = ImageDraw.Draw(im)
d.rounded_rectangle((32,32,992,992), radius=220, fill='#155eef')
d.rounded_rectangle((296,205,728,483), radius=42, fill='white')
d.rounded_rectangle((202,379,822,697), radius=66, fill='#b7d5ff')
d.ellipse((721,442,765,486), fill='#155eef')
d.rounded_rectangle((303,566,721,820), radius=40, fill='white')
d.line((374,667,586,667), fill='#155eef', width=28)
d.line((374,719,519,719), fill='#155eef', width=28)
d.ellipse((618,630,842,854), fill='#12b886')
d.line((677,745,711,779,780,704), fill='white', width=28, joint='curve')
im.save(root/'logistra.png')
im.save(root/'logistra.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
im.save(root/'logistra.icns')
# Two separate pill targets: a PDF label and a print pictogram, rendered at 2x.
actions = Image.new('RGBA', (208,64))
a = ImageDraw.Draw(actions)
a.rounded_rectangle((2,3,96,61), radius=14, fill='#e8efff', outline='#c7d7ff', width=2)
a.rounded_rectangle((106,3,204,61), radius=14, fill='#e6f7f1', outline='#b8e8d8', width=2)
try:
 font = ImageFont.truetype('DejaVuSans-Bold.ttf', 21)
except OSError:
 font = ImageFont.load_default(size=21)
a.text((49,32), 'PDF', font=font, anchor='mm', fill='#1849b1')
a.rounded_rectangle((137,23,175,45), radius=4, fill='#087f5b')
a.rectangle((145,13,167,25), fill='#087f5b')
a.rectangle((146,37,166,51), fill='white', outline='#087f5b', width=3)
actions.resize((104,32), Image.Resampling.LANCZOS).save(root/'row-actions.png')
print('Generated PNG, ICO, ICNS and row action assets.')
