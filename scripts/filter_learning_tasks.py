import json
import os
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))

KEYWORDS = [
    'выучить', 'выучи', 'учить', 'заучить',
    'повторить', 'повтори', 'повторение', 'повторять',
    'изучить', 'изучи', 'изучение',
    'разобраться', 'разобрать',
    'test', 'тест', 'экзамен', 'зачет', 'зачёт',
    'подготовиться', 'подготовка',
    'курс', 'урок', 'лекция',
    'практика', 'практиковать',
    'освежить', 'вспомнить',
    'прочитать книгу', 'прочесть',
    'конспект',
    'билет',
]

pattern = re.compile('|'.join(re.escape(k) for k in KEYWORDS), re.IGNORECASE)

def matches(task):
    text = f"{task.get('title','')} {task.get('notes','')}"
    return bool(pattern.search(text))

def main():
    with open(os.path.join(HERE, 'tasks_raw.json'), encoding='utf-8') as f:
        data = json.load(f)

    found = []
    for tl in data:
        for t in tl['tasks']:
            if t.get('status') == 'completed':
                continue
            if matches(t):
                found.append({
                    'tasklist': tl['tasklist_title'],
                    'title': t['title'],
                    'notes': t.get('notes', ''),
                    'due': t.get('due', ''),
                })

    out_path = os.path.join(HERE, 'filtered_candidates.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(found, f, ensure_ascii=False, indent=2)

    print(f'Found {len(found)} candidate learning/review tasks (active only):\n')
    for i, t in enumerate(found, 1):
        notes_preview = (t['notes'][:80] + '...') if len(t['notes']) > 80 else t['notes']
        print(f"{i}. [{t['tasklist']}] {t['title']}")
        if notes_preview:
            print(f"    notes: {notes_preview}")
        if t['due']:
            print(f"    due: {t['due']}")

    print(f'\nSaved to {out_path}')

if __name__ == '__main__':
    main()
