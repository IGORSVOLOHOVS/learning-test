"""Применяет переработанный практический блок (вопросы 40..49).

Практический блок каждого теста («Практика и расчёты», индексы 40..49)
переделывается в задачи на 2–3 шага. Новые вопросы генерируются отдельно и
лежат в scripts/practical/<slug>.json — объект { "40": {вопрос}, ..., "49": {..} }.

Скрипт заменяет questions[40..49] в scripts/content/<slug>.json, СТРОГО проверяя
структуру и что вопросы 0..39 не затрагиваются. Идемпотентен.

Запуск:
    python3 scripts/apply_practical.py --check
    python3 scripts/apply_practical.py
Затем: python3 scripts/check_quality.py && python3 scripts/build.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")
PRACT_DIR = os.path.join(HERE, "practical")

BLOCK = [str(i) for i in range(40, 50)]  # "40".."49"


def valid_question(q):
    problems = []
    if not (isinstance(q.get("q"), str) and q["q"].strip()):
        problems.append("пустой q")
    opts = q.get("options")
    if not (isinstance(opts, list) and len(opts) == 4 and all(isinstance(o, str) and o.strip() for o in opts)):
        problems.append("options не 4 непустых строки")
    elif len(set(opts)) != 4:
        problems.append("варианты не различны")
    if not isinstance(q.get("correct"), int) or not (0 <= q["correct"] <= 3):
        problems.append("correct вне 0..3")
    if not (isinstance(q.get("explain"), str) and q["explain"].strip()):
        problems.append("пустой explain")
    u = q.get("usage")
    if not (isinstance(u, dict) and isinstance(u.get("code"), bool)
            and all(isinstance(u.get(k), str) and u[k].strip() for k in ("without", "with", "benefit"))):
        problems.append("некорректный usage")
    return problems


def write_content(path, questions):
    lines = [json.dumps(q, ensure_ascii=False, separators=(",", ":")) for q in questions]
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(lines) + "\n]\n")


def main():
    check_only = "--check" in sys.argv
    if not os.path.isdir(PRACT_DIR):
        print("Нет scripts/practical — сначала сгенерируйте практические блоки.")
        return
    slugs = sorted(n[:-5] for n in os.listdir(PRACT_DIR) if n.endswith(".json"))
    if not slugs:
        print("В scripts/practical нет файлов.")
        return

    problems = []
    applied = 0
    for slug in slugs:
        cpath = os.path.join(CONTENT_DIR, slug + ".json")
        ppath = os.path.join(PRACT_DIR, slug + ".json")
        if not os.path.exists(cpath):
            print(f"  нет content для {slug} — пропуск"); continue
        pract = json.load(open(ppath, encoding="utf-8"))
        questions = json.load(open(cpath, encoding="utf-8"))

        local = []
        if set(pract.keys()) != set(BLOCK):
            local.append(f"{slug}: ключи должны быть ровно 40..49, а есть {sorted(pract.keys())}")
        else:
            for k in BLOCK:
                for pr in valid_question(pract[k]):
                    local.append(f"{slug} #{k}: {pr}")
        if len(questions) != 50:
            local.append(f"{slug}: в контенте {len(questions)} вопросов, ожидалось 50")
        if local:
            problems.extend(local)
            print(f"  ПРОПУСК {slug}: {len(local)} проблем")
            continue

        # распределение позиций в новом блоке (для наглядности)
        pos = [0, 0, 0, 0]
        for k in BLOCK:
            pos[pract[k]["correct"]] += 1
        if not check_only:
            for k in BLOCK:
                # сохраняем только валидированные поля
                src = pract[k]
                questions[int(k)] = {
                    "q": src["q"],
                    "options": src["options"],
                    "correct": src["correct"],
                    "explain": src["explain"],
                    "usage": {
                        "code": bool(src["usage"]["code"]),
                        "without": src["usage"]["without"],
                        "with": src["usage"]["with"],
                        "benefit": src["usage"]["benefit"],
                    },
                }
            write_content(cpath, questions)
            print(f"  OK {slug}: заменены вопросы 40..49; позиции правильного в блоке pos={pos}")
        else:
            print(f"  OK {slug}: проверка пройдена; позиции в блоке pos={pos}")
        applied += 1

    if problems:
        print(f"\nПРОБЛЕМЫ ({len(problems)}):")
        for p in problems[:80]:
            print("  -", p)
    print(f"\n{'проверено' if check_only else 'применено'} тестов: {applied}/{len(slugs)}")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
