"""Build SQLite embedding vectors for existing chunks.

Run from backend directory:
    python rebuild_sqlite_vectors.py
"""

from collections import defaultdict

from app.database import get_db_connection, init_db
from app.services.vector_store import VectorStore


def rebuild_sqlite_vectors() -> None:
    init_db()
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT d.game_id, c.document_id, c.chunk_index, c.content, c.embedding_id
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        LEFT JOIN chunk_embeddings e ON e.embedding_id = c.embedding_id
        WHERE e.embedding_id IS NULL
        ORDER BY d.game_id, c.document_id, c.chunk_index
        """
    ).fetchall()
    conn.close()

    if not rows:
        print("No missing vectors.")
        return

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["game_id"]].append(row)

    vector_store = VectorStore()
    total = 0
    for game_id, game_rows in grouped.items():
        ids = [row["embedding_id"] for row in game_rows]
        docs = [{"text": row["content"], "metadata": {}} for row in game_rows]
        print(f"Embedding game={game_id}, chunks={len(docs)}")
        vector_store.add_documents(game_id, docs, ids)
        total += len(docs)

    print(f"Requested vectors for {total} chunks.")


if __name__ == "__main__":
    rebuild_sqlite_vectors()
