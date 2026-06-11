#!/usr/bin/env python
"""Test document upload functionality"""

import requests
from pathlib import Path

# Create uploads directory
Path('uploads').mkdir(exist_ok=True)

# Create a simple test PDF using reportlab
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    pdf_path = 'uploads/test_rulebook.pdf'
    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # Add some test content
    c.drawString(100, 750, "Test Rulebook")
    c.drawString(100, 700, "How to gain experience points:")
    c.drawString(120, 680, "1. Defeat enemies")
    c.drawString(120, 660, "2. Complete quests")
    c.drawString(120, 640, "3. Explore the world")
    c.drawString(100, 600, "Character Upgrade Rules:")
    c.drawString(120, 580, "- Reach level 10 to unlock new abilities")
    c.drawString(120, 560, "- Spend skill points on upgrades")
    
    # Add more pages to test chunking
    for page_num in range(2, 5):
        c.showPage()
        c.drawString(100, 750, f"Page {page_num}")
        c.drawString(100, 700, f"Content for page {page_num}")
        c.drawString(100, 650, "Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
        c.drawString(100, 600, "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.")
    
    c.save()
    print(f"✓ Created test PDF: {pdf_path}")
    
    # Now test upload
    game_id = 8
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        resp = requests.post(f'http://localhost:8000/api/documents/{game_id}/upload', files=files)
        print(f"✓ Upload status: {resp.status_code}")
        if resp.status_code not in [200, 201]:
            print(f"✗ Error response: {resp.text}")
        else:
            result = resp.json()
            print(f"✓ Upload successful!")
            print(f"  - Document ID: {result.get('id')}")
            print(f"  - Pages: {result.get('pages')}")
            print(f"  - Status: {result.get('status')}")
            
except ImportError:
    print("✗ reportlab not installed")
    print("  Installing...")
    import subprocess
    subprocess.run(['pip', 'install', 'reportlab', '-q'])
    print("  Retrying...")
    exec(open(__file__).read())
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
