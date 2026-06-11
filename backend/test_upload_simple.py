#!/usr/bin/env python
"""Test document upload with minimal PDF"""

import requests
from pathlib import Path
import base64

# Create uploads directory
Path('uploads').mkdir(exist_ok=True)

# Create a minimal valid PDF
minimal_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test Rulebook) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
0000000301 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
395
%%EOF
"""

pdf_path = 'uploads/test_rulebook.pdf'
with open(pdf_path, 'wb') as f:
    f.write(minimal_pdf)

print(f"✓ Created test PDF: {pdf_path}")

# Test upload
game_id = 8
try:
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        resp = requests.post(f'http://localhost:8000/api/documents/{game_id}/upload', files=files)
        print(f"✓ Upload status: {resp.status_code}")
        if resp.status_code not in [200, 201]:
            print(f"✗ Error: {resp.text}")
        else:
            result = resp.json()
            print(f"✓ Upload successful!")
            print(f"  - Document ID: {result.get('id')}")
            print(f"  - Pages: {result.get('pages')}")
            print(f"  - Status: {result.get('status')}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
