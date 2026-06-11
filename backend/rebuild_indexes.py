"""Rebuild all document chunks and Chroma collections from uploaded PDFs.

Run from backend directory:
    python rebuild_indexes.py
"""

import os
import sqlite3
from pathlib import Path

from app.config import settings
from app.services.pdf_processor import PDFProcessor, TextChunker
from app.services.vector_store import VectorStore


def rebuild_all() -> None:
    conn = sqlite3.connect("boardgames.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    docs = cur.execute("SELECT * FROM documents ORDER BY game_id, id").fetchall()
    if not docs:
        print("No documents found.")
        conn.close()
        return

    game_ids = sorted({doc["game_id"] for doc in docs})
    vector_store = VectorStore()

    # Start with clean collections for games that have documents.
    for game_id in game_ids:
        vector_store.delete_collection(game_id)
        vector_store.create_collection(game_id)
        cur.execute(
            "DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE game_id = ?)",
            (game_id,),
        )
    conn.commit()

    total_chunks = 0
    for doc in docs:
        file_path = doc["file_path"]
        if not os.path.exists(file_path):
            print(f"Skip missing file: document={doc['id']} path={file_path}")
            continue

        print(f"Rebuilding game={doc['game_id']} document={doc['id']} file={Path(file_path).name}")
        text, page_count = PDFProcessor.extract_text_from_pdf(file_path)
        cleaned_text = TextChunker.clean_text(text)
        chunks = TextChunker.chunk_text(
            cleaned_text,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )

        chunk_ids = []
        chunk_dicts = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"doc_{doc['id']}_chunk_{i}"
            chunk_text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
            metadata = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
            if not chunk_text.strip():
                continue

            cur.execute(
                "INSERT INTO chunks (document_id, chunk_index, content, embedding_id) VALUES (?, ?, ?, ?)",
                (doc["id"], i, chunk_text, chunk_id),
            )
            chunk_ids.append(chunk_id)
            chunk_dicts.append({"text": chunk_text, "metadata": metadata})

        cur.execute("UPDATE documents SET pages = ?, status = ? WHERE id = ?", (page_count, "completed", doc["id"]))
        conn.commit()

        if chunk_dicts:
            vector_store.add_documents(doc["game_id"], chunk_dicts, chunk_ids)
            total_chunks += len(chunk_dicts)
            print(f"  added {len(chunk_dicts)} chunks")
        else:
            print("  no valid chunks")

    conn.close()
    print(f"Rebuilt {len(docs)} documents, {total_chunks} chunks total.")


if __name__ == "__main__":
    rebuild_all()
