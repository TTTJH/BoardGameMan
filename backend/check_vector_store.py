from app.services.vector_store import VectorStore

vs = VectorStore()
try:
    coll = vs.client.get_collection('game_2')
    print(f'Collection game_2 count: {coll.count()}')
    
    # Try a search
    results = coll.query(query_texts=['How do you play?'], n_results=5)
    print(f'Search results: {len(results["documents"][0]) if results["documents"] else 0} documents found')
    if results['documents'] and len(results['documents'][0]) > 0:
        print(f'First result: {results["documents"][0][0][:100]}...')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
