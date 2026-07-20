"""Вписывает поле `usage` в вопросы тестов.

Примеры «как без этого / как с этим» генерируются отдельно и лежат в
scripts/usage/<slug>.json — массив из 50 объектов
{code, without, with, benefit} строго в порядке вопросов. Этот скрипт
проставляет их в scripts/content/<slug>.json как q["usage"], сохраняя
исходный компактный формат (по одному вопросу на строку). Идемпотентен.

Запуск:
    python3 scripts/merge_usage.py           # смёрджить всё, что есть в scripts/usage
    python3 scripts/merge_usage.py --check    # только проверить, ничего не писать

После мёрджа пересоберите HTML:
    python3 scripts/build.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")
USAGE_DIR = os.path.join(HERE, "usage")

REQUIRED = ("without", "with", "benefit")


def validate_usage(slug, usage):
    problems = []
    if not isinstance(usage, list):
        return [f"{slug}: usage не является массивом"]
    if len(usage) != 50:
        problems.append(f"{slug}: ожидалось 50 объектов usage, получено {len(usage)}")
    for i, u in enumerate(usage):
        if not isinstance(u, dict):
            problems.append(f"{slug} #{i}: usage не объект")
            continue
        if not isinstance(u.get("code"), bool):
            problems.append(f"{slug} #{i}: code не булево")
        for f in REQUIRED:
            v = u.get(f)
            if not isinstance(v, str) or not v.strip():
                problems.append(f"{slug} #{i}: пустое/некорректное поле '{f}'")
    return problems


def write_content(path, questions):
    # Компактный формат: массив, по одному вопросу на строку — как в исходниках
    # и в scripts/shuffle_options.py, чтобы diff был минимальным.
    lines = [json.dumps(q, ensure_ascii=False, separators=(",", ":")) for q in questions]
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(lines) + "\n]\n")


def main():
    check_only = "--check" in sys.argv
    if not os.path.isdir(USAGE_DIR):
        print("Нет директории scripts/usage — сначала сгенерируйте примеры.")
        return

    slugs = sorted(n[:-5] for n in os.listdir(USAGE_DIR) if n.endswith(".json"))
    if not slugs:
        print("В scripts/usage нет файлов *.json.")
        return

    total_problems = []
    merged = 0
    missing_content = []
    for slug in slugs:
        content_path = os.path.join(CONTENT_DIR, slug + ".json")
        usage_path = os.path.join(USAGE_DIR, slug + ".json")
        if not os.path.exists(content_path):
            missing_content.append(slug)
            continue

        with open(usage_path, encoding="utf-8") as f:
            usage = json.load(f)
        with open(content_path, encoding="utf-8") as f:
            questions = json.load(f)

        problems = validate_usage(slug, usage)
        if len(usage) != len(questions):
            problems.append(f"{slug}: {len(questions)} вопросов, но {len(usage)} usage")
        if problems:
            total_problems.extend(problems)
            print(f"  ПРОПУСК {slug}: {len(problems)} проблем")
            continue

        if not check_only:
            for q, u in zip(questions, usage):
                q["usage"] = {
                    "code": bool(u["code"]),
                    "without": u["without"],
                    "with": u["with"],
                    "benefit": u["benefit"],
                }
            write_content(content_path, questions)
        merged += 1
        code_n = sum(1 for u in usage if u["code"])
        print(f"  OK {slug}: 50 usage (code: {code_n}, проза: {50 - code_n})")

    if missing_content:
        print("\nНет content-файла для:", ", ".join(missing_content))
    if total_problems:
        print(f"\nПРОБЛЕМЫ ({len(total_problems)}):")
        for p in total_problems[:50]:
            print("  -", p)

    action = "проверено" if check_only else "смёрджено"
    print(f"\n{action} тестов: {merged}/{len(slugs)}")
    if total_problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
