from app.services.vector_store import VectorStore

vs = VectorStore()
queries = [
    '战斗时候玩家先手还是怪物先手',
    '战斗时 怪物先手还是玩家先手',
    'combat turn order player first monster first',
    'Foe Turn Exile Turn combat'
]
for q in queries:
    print('\n' + '='*80)
    print('QUERY:', q)
    results = vs.search(12, q, top_k=8)
    for i, (doc, score) in enumerate(results, 1):
        print(f'\n{i}. score={score:.4f}')
        print(doc[:450].replace('\n', ' '))
