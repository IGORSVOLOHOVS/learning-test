"""Перемешивает порядок вариантов ответов во всех тестах.

Проблема: правильный ответ почти всегда стоял на позиции 0–1 (≈90% случаев),
поэтому тесты угадывались по позиции, а не по знанию. Этот скрипт делает
случайную перестановку четырёх вариантов в каждом вопросе и пересчитывает
индекс `correct`, чтобы правильный ответ равномерно распределился по всем
четырём позициям.

Запуск:
    python3 scripts/shuffle_options.py          # перемешать и перезаписать content/*.json
    python3 scripts/shuffle_options.py --check   # только показать распределение, не менять

После перемешивания пересоберите HTML:
    python3 scripts/build.py
"""

import json
import os
import random
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")

# Фиксированный seed -> сборка воспроизводима, но порядок для человека
# непредсказуем и равномерен. Поменяйте число, чтобы получить другой расклад.
SEED = 20260720


def distribution():
    counter = collections.Counter()
    for name in sorted(os.listdir(CONTENT_DIR)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(CONTENT_DIR, name), encoding="utf-8") as f:
            for q in json.load(f):
                counter[q["correct"]] += 1
    total = sum(counter.values()) or 1
    print("Распределение позиции правильного ответа:")
    for i in range(4):
        print(f"  позиция {i}: {counter[i]:4d}  ({100 * counter[i] / total:5.1f}%)")
    print(f"  всего вопросов: {total}")


def shuffle_all(slugs=None):
    rng = random.Random(SEED)
    changed = 0
    for name in sorted(os.listdir(CONTENT_DIR)):
        if not name.endswith(".json"):
            continue
        if slugs and name[:-5] not in slugs:
            continue
        path = os.path.join(CONTENT_DIR, name)
        with open(path, encoding="utf-8") as f:
            questions = json.load(f)

        for q in questions:
            options = q["options"]
            n = len(options)
            correct_text = options[q["correct"]]

            order = list(range(n))
            rng.shuffle(order)

            q["options"] = [options[k] for k in order]
            q["correct"] = q["options"].index(correct_text)
            changed += 1

        # Сохраняем исходный формат: массив, по одному вопросу на строку,
        # компактные разделители — чтобы diff был минимальным.
        lines = [json.dumps(q, ensure_ascii=False, separators=(",", ":")) for q in questions]
        with open(path, "w", encoding="utf-8") as f:
            f.write("[\n" + ",\n".join(lines) + "\n]\n")
        print(f"  перемешан: {name} ({len(questions)} вопросов)")

    print(f"\nГотово. Перемешано вопросов: {changed}")


def main():
    # Позиционные аргументы = slug'и тестов для перемешивания (по умолчанию все).
    # Так можно перемешать только новый тест, не трогая существующие.
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")]
    slugs = slugs or None
    if "--check" in sys.argv:
        distribution()
        return
    print("Перемешиваю" + (f" ({', '.join(slugs)})" if slugs else " все тесты") + "...")
    shuffle_all(slugs)


if __name__ == "__main__":
    main()
