from pathlib import Path
import pdfplumber

pdf_path = Path('uploads/game_12_844543842-Arydia-Rulebook-ENG-DeU.pdf')
if not pdf_path.exists():
    pdf_path = Path('uploads/game_11_844543842-Arydia-Rulebook-ENG-DeU.pdf')

print('PDF:', pdf_path)
with pdfplumber.open(str(pdf_path)) as pdf:
    for p in [19, 20, 21, 23, 24, 28, 29, 30]:  # 0-based pages around Combat/Foes/Exile Turns
        if p >= len(pdf.pages):
            continue
        page = pdf.pages[p]
        print('\n' + '='*80)
        print('PAGE', p + 1)
        print('- extract_text default -')
        txt = page.extract_text() or ''
        print(txt[:1500])
        print('\n- table count -', len(page.extract_tables() or []))
