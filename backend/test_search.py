#!/usr/bin/env python
"""Test vector store search"""

from app.services.vector_store import VectorStore

vs = VectorStore()
try:
    # Test search
    results = vs.search(game_id=2, query='怪物先手', top_k=3)
    print(f'Search results: {len(results)} found')
    for i, result in enumerate(results):
        print(f'\nResult {i+1}:')
        score = result.get('score')
        text = result.get('text', 'MISSING')[:100]
        metadata = result.get('metadata')
        print(f'  Score: {score}')
        print(f'  Text: {text}...')
        print(f'  Metadata: {metadata}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
