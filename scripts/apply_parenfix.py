"""Применяет точечную правку «скобочного» тэлла.

В части вопросов скобки были ТОЛЬКО у правильного варианта, из-за чего он
выдавался. Агенты добавили естественные скобки в один из НЕПРАВИЛЬНЫХ вариантов
(правильный не трогали). Правки лежат в scripts/parenfix/<slug>.json —
объект { "<idx>": [4 варианта после правки], ... }.

Этот скрипт применяет их к scripts/content/<slug>.json, СТРОГО проверяя, что
вариант на позиции correct не изменился (побайтно), а остальные поля вопроса
(q, correct, explain, usage) не тронуты. Идемпотентен.

Запуск:
    python3 scripts/apply_parenfix.py --check
    python3 scripts/apply_parenfix.py
Затем: python3 scripts/build.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")
FIX_DIR = os.path.join(HERE, "parenfix")


def has_paren(s):
    return ("(" in s) or (")" in s)


def only_correct_paren_count(questions):
    n = 0
    for q in questions:
        c = q["correct"]
        others = [has_paren(o) for i, o in enumerate(q["options"]) if i != c]
        if has_paren(q["options"][c]) and not any(others):
            n += 1
    return n


def write_content(path, questions):
    lines = [json.dumps(q, ensure_ascii=False, separators=(",", ":")) for q in questions]
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(lines) + "\n]\n")


def main():
    check_only = "--check" in sys.argv
    if not os.path.isdir(FIX_DIR):
        print("Нет scripts/parenfix — сначала сгенерируйте правки.")
        return
    slugs = sorted(n[:-5] for n in os.listdir(FIX_DIR) if n.endswith(".json"))
    if not slugs:
        print("В scripts/parenfix нет файлов.")
        return

    problems = []
    applied = 0
    for slug in slugs:
        cpath = os.path.join(CONTENT_DIR, slug + ".json")
        fpath = os.path.join(FIX_DIR, slug + ".json")
        if not os.path.exists(cpath):
            print(f"  нет content для {slug} — пропуск"); continue
        fixes = json.load(open(fpath, encoding="utf-8"))
        questions = json.load(open(cpath, encoding="utf-8"))

        local = []
        for k, opts in fixes.items():
            i = int(k)
            if not (isinstance(opts, list) and len(opts) == 4 and all(isinstance(o, str) and o.strip() for o in opts)):
                local.append(f"{slug} #{i}: не 4 непустых строки"); continue
            if len(set(opts)) != 4:
                local.append(f"{slug} #{i}: варианты не различны")
            c = questions[i]["correct"]
            if opts[c] != questions[i]["options"][c]:
                local.append(f"{slug} #{i}: правильный вариант ИЗМЕНЁН — запрещено")
            if not any(has_paren(o) for j, o in enumerate(opts) if j != c):
                local.append(f"{slug} #{i}: скобку в дистрактор не добавили")
        if local:
            problems.extend(local)
            print(f"  ПРОПУСК {slug}: {len(local)} проблем")
            continue

        before = only_correct_paren_count(questions)
        if not check_only:
            for k, opts in fixes.items():
                questions[int(k)]["options"] = opts
            write_content(cpath, questions)
            after = only_correct_paren_count(questions)
            print(f"  OK {slug}: скобка-только-у-правильного {before} -> {after} (правок: {len(fixes)})")
        else:
            print(f"  OK {slug}: проверка пройдена ({len(fixes)} правок; сейчас only-correct-paren={before})")
        applied += 1

    if problems:
        print(f"\nПРОБЛЕМЫ ({len(problems)}):")
        for p in problems[:60]:
            print("  -", p)
    print(f"\n{'проверено' if check_only else 'применено'} тестов: {applied}/{len(slugs)}")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
