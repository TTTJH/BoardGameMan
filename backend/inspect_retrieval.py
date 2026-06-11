from app.services.vector_store import VectorStore

vs = VectorStore()
for game_id in [12, 11, 10]:
    print('\n' + '='*80)
    print('GAME', game_id)
    results = vs.search(game_id, '战斗时候玩家先手还是怪物先手 combat initiative activation exile turn foe turn', top_k=10)
    print('count:', len(results))
    for i, item in enumerate(results, 1):
        doc, score = item
        print(f'\nRESULT {i} score={score:.4f}')
        print(doc[:800].replace('\n', ' '))
