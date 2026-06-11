import sqlite3

conn = sqlite3.connect('boardgames.db')
cur = conn.cursor()

print('--- DB summary ---')
print('documents:', cur.execute('select id, game_id, filename, pages, status from documents').fetchall())
print('chunk_count:', cur.execute('select count(*) from chunks').fetchone()[0])
print('chat_count:', cur.execute('select count(*) from chat_history').fetchone()[0])

print('\n--- sample chunks ---')
for idx, content in cur.execute('select chunk_index, content from chunks order by chunk_index limit 10'):
    print(f'\nCHUNK {idx}')
    print((content or '')[:700])

print('\n--- combat keyword search ---')
terms = ['combat', 'battle', 'monster', 'initiative', 'turn order', 'player turn', 'enemy', 'creature', 'attack']
for term in terms:
    rows = cur.execute(
        'select chunk_index, content from chunks where lower(content) like ? limit 5',
        (f'%{term}%',)
    ).fetchall()
    print(f'\nTERM {term}: {len(rows)} sample(s)')
    for idx, content in rows[:3]:
        one_line = (content or '').replace('\n', ' ')
        print(f'chunk {idx}: {one_line[:400]}')

print('\n--- latest chat sources ---')
for chat_id, game_id, sources in cur.execute('select id, game_id, sources from chat_history order by id desc limit 3'):
    print(f'chat {chat_id}, game {game_id}: {(sources or "")[:500]}')

conn.close()
