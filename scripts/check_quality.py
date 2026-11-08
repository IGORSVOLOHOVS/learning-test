"""Проверка качества тестов: анти-подсказки, чтобы правильный ответ нельзя было
угадать по форме, а не по знанию.

Правила (см. CLAUDE.md → «Правила создания тестов»):
  1. Ровно 50 вопросов в тесте.
  2. У каждого вопроса ровно 4 варианта, непустых и различных; correct в 0..3.
  3. Позиция правильного ответа распределена ~равномерно по 0..3
     (нет позиции, встречающейся < MIN_PER_POS раз из 50).
  4. Правильный ответ НЕ опознаётся по длине: доля «правильный строго самый
     длинный» ≤ MAX_LONGEST_FRAC; средняя длина правильного ≈ средней длине
     неправильных (в пределах ±LEN_MEAN_TOL).
  5. Круглые скобки НЕ выдают правильный ответ: НЕТ вопросов, где скобка есть
     только у правильного варианта (only-correct-paren == 0).

Запуск:
    python3 scripts/check_quality.py           # проверить все тесты
    python3 scripts/check_quality.py <slug>...  # только указанные

Код возврата != 0, если есть нарушения (удобно для CI / перед коммитом).
"""

import json
import re
import os
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")
ROOT = os.path.dirname(HERE)

# Пороги (на выборке 50 вопросов; случайное ожидание позиции — 12.5)
N_QUESTIONS = 50
N_OPTIONS = 4
MIN_PER_POS = 5          # каждая позиция правильного должна встречаться >= 5/50
MAX_LONGEST_FRAC = 0.35  # «правильный строго самый длинный» не чаще 35%
LEN_MEAN_TOL = 0.15      # средняя длина правильного в пределах ±15% от неправильных


MATH_DELIM = re.compile(r"\\[()\[\]]")


def shown(s):
    """Приблизительно то, что видно после KaTeX: без разделителей \\( \\) \\[ \\],
    команда вроде \\omega или \\frac — один знак, без {}, ^ и _. Длину и скобки
    правил 3–4 человек оценивает по видимому тексту, а не по исходнику LaTeX."""
    s = MATH_DELIM.sub("", s)
    s = re.sub(r"\\(left|right|big|Big|,|;|!|quad)", "", s)
    s = re.sub(r"\\[a-zA-Z]+", "x", s)
    return re.sub(r"[{}^_]", "", s)


def has_math(s):
    return bool(MATH_DELIM.search(s))


def has_paren(s):
    s = shown(s)
    return ("(" in s) or (")" in s)


def math_balance_errors(text):
    """Каждый \\( закрыт \\) и каждый \\[ закрыт \\], без вложенности."""
    depth, errs = None, []
    for m in MATH_DELIM.finditer(text):
        tok = m.group(0)
        if tok in ("\\(", "\\["):
            if depth:
                errs.append(f"{tok} внутри {depth}")
            depth = tok
        else:
            want = "\\(" if tok == "\\)" else "\\["
            if depth != want:
                errs.append(f"{tok} без {want}")
            depth = None
    if depth:
        errs.append(f"{depth} не закрыт")
    return errs


def check_file(path):
    slug = os.path.basename(path)[:-5]
    qs = json.load(open(path, encoding="utf-8"))
    problems = []

    if len(qs) != N_QUESTIONS:
        problems.append(f"{slug}: вопросов {len(qs)}, а нужно {N_QUESTIONS}")

    pos = [0, 0, 0, 0]
    longest = only_paren = 0
    c_len = 0
    o_len = 0
    o_n = 0
    for i, q in enumerate(qs):
        opts = q.get("options", [])
        c = q.get("correct")
        if len(opts) != N_OPTIONS:
            problems.append(f"{slug} #{i}: вариантов {len(opts)}, нужно {N_OPTIONS}")
            continue
        if any((not isinstance(o, str) or not o.strip()) for o in opts):
            problems.append(f"{slug} #{i}: пустой вариант")
        if len(set(opts)) != N_OPTIONS:
            problems.append(f"{slug} #{i}: варианты не различны")
        if not isinstance(c, int) or not (0 <= c < N_OPTIONS):
            problems.append(f"{slug} #{i}: correct вне диапазона: {c}")
            continue

        u = q.get("usage") or {}
        fields = [q.get("q", ""), q.get("explain", "")] + list(opts) + [
            u.get(k) or "" for k in ("without", "with", "benefit")]
        for f in fields:
            for e in math_balance_errors(f):
                problems.append(f"{slug} #{i}: формула: {e}")
        if has_math(opts[c]) and not any(has_math(o) for j, o in enumerate(opts) if j != c):
            problems.append(f"{slug} #{i}: формула LaTeX только у правильного варианта — выдаёт ответ")

        pos[c] += 1
        lens = [len(shown(o)) for o in opts]
        c_len += lens[c]
        for j in range(N_OPTIONS):
            if j != c:
                o_len += lens[j]
                o_n += 1
        if all(lens[c] >= l for l in lens) and lens.count(lens[c]) == 1:
            longest += 1
        if has_paren(opts[c]) and not any(has_paren(o) for j, o in enumerate(opts) if j != c):
            only_paren += 1

    n = len(qs) or 1
    # Правило 3: распределение позиций
    for p in range(N_OPTIONS):
        if pos[p] < MIN_PER_POS:
            problems.append(f"{slug}: позиция {p} у правильного всего {pos[p]}/{n} (< {MIN_PER_POS}) — перемешайте (shuffle_options.py)")
    # Правило 4: длина
    frac_longest = longest / n
    if frac_longest > MAX_LONGEST_FRAC:
        problems.append(f"{slug}: правильный = самый длинный в {longest}/{n} ({frac_longest:.0%} > {MAX_LONGEST_FRAC:.0%}) — выровняйте длину")
    if o_n:
        cm, om = c_len / n, o_len / o_n
        if om and abs(cm - om) / om > LEN_MEAN_TOL:
            problems.append(f"{slug}: средняя длина правильного {cm:.0f} vs неправильных {om:.0f} (разрыв > {LEN_MEAN_TOL:.0%})")
    # Правило 5: скобки
    if only_paren:
        problems.append(f"{slug}: скобка только у правильного в {only_paren} вопросах — добавьте скобку в дистрактор или уберите у правильного")

    # Картинка вопроса (поле img, пишет scripts/images.py attach): файл на месте и есть alt.
    # Содержимое самих картинок проверяет python scripts/images.py check.
    imgs = 0
    for i, q in enumerate(qs):
        img = q.get("img")
        if not img:
            continue
        imgs += 1
        if not os.path.exists(os.path.join(ROOT, img.get("src", ""))):
            problems.append(f"{slug} q{i + 1}: картинки {img.get('src')} нет на диске")
        if not (img.get("alt") or "").strip():
            problems.append(f"{slug} q{i + 1}: у картинки нет alt")

    stats = f"pos={pos} longest={longest}/{n} only_paren={only_paren}" + (f" img={imgs}" if imgs else "")
    return slug, problems, stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        paths = [os.path.join(CONTENT_DIR, a + ".json") for a in args]
    else:
        paths = sorted(glob.glob(os.path.join(CONTENT_DIR, "*.json")))

    all_problems = []
    for path in paths:
        if not os.path.exists(path):
            print(f"  НЕТ ФАЙЛА: {path}")
            all_problems.append(path)
            continue
        slug, problems, stats = check_file(path)
        if problems:
            print(f"  FAIL {slug}: {stats}")
            for p in problems:
                print(f"       - {p}")
            all_problems.extend(problems)
        else:
            print(f"  OK   {slug}: {stats}")

    if all_problems:
        print(f"\nНАРУШЕНИЙ: {len(all_problems)}")
        sys.exit(1)
    print(f"\nВсе тесты прошли проверку качества ({len(paths)}).")


if __name__ == "__main__":
    main()
