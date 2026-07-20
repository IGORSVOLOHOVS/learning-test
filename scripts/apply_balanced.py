"""Применяет выровненные по длине варианты ответов к контенту тестов.

Балансировка длины генерируется отдельно (агентами) и лежит в
scripts/balanced/<slug>.json — массив из 50 объектов
{ "options": [4 строки], "correct": <индекс> } строго в порядке вопросов.
Этот скрипт заменяет q["options"] в scripts/content/<slug>.json, СТРОГО
проверяя, что индекс correct не изменился и структура валидна. Поля
q, correct, explain, usage не трогаются. Идемпотентен.

Запуск:
    python3 scripts/apply_balanced.py --check   # только проверка, без записи
    python3 scripts/apply_balanced.py           # проверить и применить

После применения пересоберите HTML:
    python3 scripts/build.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")
BALANCED_DIR = os.path.join(HERE, "balanced")


def validate(slug, questions, balanced):
    problems = []
    if not isinstance(balanced, list):
        return [f"{slug}: balanced не массив"]
    if len(balanced) != len(questions):
        problems.append(f"{slug}: {len(questions)} вопросов, но {len(balanced)} balanced")
        return problems
    for i, (q, b) in enumerate(zip(questions, balanced)):
        opts = b.get("options") if isinstance(b, dict) else None
        if not isinstance(opts, list) or len(opts) != 4:
            problems.append(f"{slug} #{i}: options не 4 строки")
            continue
        if any((not isinstance(o, str) or not o.strip()) for o in opts):
            problems.append(f"{slug} #{i}: пустой вариант")
        if len(set(opts)) != 4:
            problems.append(f"{slug} #{i}: варианты не различны")
        if b.get("correct") != q["correct"]:
            problems.append(f"{slug} #{i}: correct изменился ({q['correct']} -> {b.get('correct')})")
    return problems


def write_content(path, questions):
    lines = [json.dumps(q, ensure_ascii=False, separators=(",", ":")) for q in questions]
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(lines) + "\n]\n")


def longest_leak(questions):
    """Доля вопросов, где правильный вариант строго самый длинный."""
    n = strict = 0
    for q in questions:
        lens = [len(o) for o in q["options"]]
        c = q["correct"]
        n += 1
        if all(lens[c] >= l for l in lens) and lens.count(lens[c]) == 1:
            strict += 1
    return strict, n


def main():
    check_only = "--check" in sys.argv
    if not os.path.isdir(BALANCED_DIR):
        print("Нет директории scripts/balanced — сначала сгенерируйте балансировку.")
        return

    slugs = sorted(n[:-5] for n in os.listdir(BALANCED_DIR) if n.endswith(".json"))
    if not slugs:
        print("В scripts/balanced нет файлов *.json.")
        return

    all_problems = []
    applied = 0
    for slug in slugs:
        content_path = os.path.join(CONTENT_DIR, slug + ".json")
        balanced_path = os.path.join(BALANCED_DIR, slug + ".json")
        if not os.path.exists(content_path):
            print(f"  нет content для {slug} — пропуск")
            continue

        with open(balanced_path, encoding="utf-8") as f:
            balanced = json.load(f)
        with open(content_path, encoding="utf-8") as f:
            questions = json.load(f)

        problems = validate(slug, questions, balanced)
        if problems:
            all_problems.extend(problems)
            print(f"  ПРОПУСК {slug}: {len(problems)} проблем")
            continue

        before_strict, n = longest_leak(questions)
        if not check_only:
            for q, b in zip(questions, balanced):
                q["options"] = b["options"]
            write_content(content_path, questions)
            after_strict, _ = longest_leak(questions)
            print(f"  OK {slug}: правильный=самый длинный {before_strict}/{n} -> {after_strict}/{n}")
        else:
            print(f"  OK {slug}: проверка пройдена (сейчас правильный=самый длинный {before_strict}/{n})")
        applied += 1

    if all_problems:
        print(f"\nПРОБЛЕМЫ ({len(all_problems)}):")
        for p in all_problems[:60]:
            print("  -", p)

    action = "проверено" if check_only else "применено"
    print(f"\n{action} тестов: {applied}/{len(slugs)}")
    if all_problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
