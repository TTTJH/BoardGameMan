import os
import sqlite3
import shutil
from pathlib import Path

from app.services.pdf_processor import PDFProcessor, TextChunker
from app.services.vector_store import VectorStore
from app.config import settings

GAME_ID = 12

conn = sqlite3.connect('boardgames.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

doc = cur.execute('SELECT * FROM documents WHERE game_id = ? ORDER BY id DESC LIMIT 1', (GAME_ID,)).fetchone()
if not doc:
    upload_files = sorted(Path(settings.UPLOAD_DIR).glob(f'game_{GAME_ID}_*.pdf'))
    if not upload_files:
        raise SystemExit(f'No document row or uploaded PDF found for game {GAME_ID}')
    file_path = str(upload_files[-1])
    filename = upload_files[-1].name.replace(f'game_{GAME_ID}_', '', 1)
    file_size = os.path.getsize(file_path)
    text, page_count = PDFProcessor.extract_text_from_pdf(file_path)
    cur.execute(
        """INSERT INTO documents (game_id, filename, file_path, file_size, pages, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (GAME_ID, filename, file_path, file_size, page_count, 'completed')
    )
    conn.commit()
    doc_id = cur.lastrowid
else:
    doc_id = doc['id']
    file_path = doc['file_path']
    text, page_count = PDFProcessor.extract_text_from_pdf(file_path)

print('Rebuilding document', doc_id, 'from', file_path)
cleaned = TextChunker.clean_text(text)
chunks = TextChunker.chunk_text(cleaned, chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP)

cur.execute('DELETE FROM chat_history WHERE game_id = ?', (GAME_ID,))
cur.execute('DELETE FROM chunks WHERE document_id = ?', (doc_id,))
conn.commit()

vs = VectorStore()
try:
    vs.delete_collection(GAME_ID)
except Exception:
    pass
vs.create_collection(GAME_ID)

ids = []
docs = []
for i, chunk in enumerate(chunks):
    chunk_id = f'doc_{doc_id}_chunk_{i}'
    chunk_text = chunk['text'] if isinstance(chunk, dict) else str(chunk)
    metadata = chunk.get('metadata', {}) if isinstance(chunk, dict) else {}
    cur.execute(
        'INSERT INTO chunks (document_id, chunk_index, content, embedding_id) VALUES (?, ?, ?, ?)',
        (doc_id, i, chunk_text, chunk_id)
    )
    ids.append(chunk_id)
    docs.append({'text': chunk_text, 'metadata': metadata})

conn.commit()
conn.close()

vs.add_documents(GAME_ID, docs, ids)
print(f'Rebuilt {len(docs)} chunks for game {GAME_ID}')
