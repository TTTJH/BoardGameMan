from app.database import get_db_connection
from app.services.vector_store import VectorStore

# Get all chunks from database
conn = get_db_connection()
cursor = conn.cursor()

# Get all chunks grouped by game
cursor.execute("""
    SELECT c.id, c.content, d.game_id, c.document_id, c.chunk_index
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    ORDER BY d.game_id, d.id, c.chunk_index
""")

chunks_by_game = {}
for row in cursor.fetchall():
    chunk_id = row['id']
    content = row['content']
    game_id = row['game_id']
    doc_id = row['document_id']
    chunk_idx = row['chunk_index']
    
    if game_id not in chunks_by_game:
        chunks_by_game[game_id] = []
    
    # Create a unique ID for the chunk
    unique_id = f"doc_{doc_id}_chunk_{chunk_idx}"
    chunks_by_game[game_id].append((unique_id, content))

conn.close()

# Add chunks to vector store
vs = VectorStore()
for game_id, chunks in chunks_by_game.items():
    chunk_ids = [c[0] for c in chunks]
    chunk_texts = [c[1] for c in chunks]
    
    print(f"Adding {len(chunks)} chunks to game {game_id}...")
    try:
        vs.add_documents(game_id, chunk_texts, chunk_ids)
        print(f"✓ Successfully added {len(chunks)} chunks to game {game_id}")
    except Exception as e:
        print(f"✗ Error adding chunks to game {game_id}: {e}")

print("Done!")
