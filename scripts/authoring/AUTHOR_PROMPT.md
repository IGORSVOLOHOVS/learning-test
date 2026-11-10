You are writing one new 50-question study test for the repo C:\Users\igors\Projects\learning-test (a static GitHub Pages site of self-marking tests in Russian). The run is unattended: nobody will answer questions, so decide and proceed. Read the repo's CLAUDE.md first — every rule there is mandatory: 50 questions, 4 options, blocks of 10, block 5 = multi-step practical problems, the anti-tell rules on length and parentheses, formulas in LaTeX `\( \)` / `\[ \]` and never `$`.

## The test
Slug: `{slug}`. Title: «{title}».
What it must cover: {topic}

## Source material
{sources}
If sources are given, the test follows them: their notation, their kind of problems, their order of ideas. Read every source before writing (PDF: render or extract with pymupdf; images and scans: open with the Read tool; folders: look at every file). If no sources are given, use standard textbook knowledge and say so in the final answer. Do not invent "what the teacher said".

## Who it is for
Igor, a master's student (Smart Electronic Systems and Robotics, TSI Riga) and an embedded/robotics engineer. Tests are a way to learn, not only to check: `explain` must teach — why the right answer is right, what typical mistake each wrong option comes from, the formula and one line of intuition, in plain Russian. If the subject is taught in English, put the English terms next to the Russian ones in questions and explanations (never only in the correct option — anti-tell rule 4).

## Structure (5 blocks × 10)
1. Основы — definitions and intuition.
2. Формулы, правила и свойства — recognising and applying them.
3. Типовые случаи — the standard objects, signals, cases or examples of the topic.
4. Понимание и подвохи — common mistakes, traps, edge cases, reading graphs or outputs.
5. Практика (questions 41–50) — 10 problems of 2–3 steps each (numeric for technical topics, a worked case for soft topics); distractors are the results of typical mistakes in those steps.

## Correctness — mandatory
Every numeric answer and every formula in an option must be verified by a script `%TEMP%\lt-author-{slug}\verify.py` (sympy is installed) that recomputes each correct answer from the givens, asserts it matches the option text, and asserts every numeric distractor differs from it. Derive analytic results symbolically in that script, not from memory. For non-technical topics, write the check as a list of claims with the source page or section each one comes from.

## How to write it
Follow the pattern of `scripts/authoring/english_work.py`: a source script `scripts/authoring/{slug}.py` with `add(q, correct, [3 wrong], explain, without, with_, benefit)` entries that writes `scripts/content/{slug}.json` (balanced position of the correct option, compact one-question-per-line JSON). `usage` = a short "without this / with this" example from Igor's world (robotics, sensors, embedded, welding/WAAM, his studies); `code: false` unless it really is code. Write files with the Write tool — the Bash tool mangles backslashes, so never pass LaTeX through bash heredocs or `python -c`; in Python source use raw strings `r"..."` for LaTeX.

`scripts/build.py` already has an entry for this slug. Edit ONLY `scripts/authoring/{slug}.py`, `scripts/content/{slug}.json` and (via build) `tests/{slug}.html`. Do not edit build.py, index.html or other tests. Do not git add or commit — the launcher does that after its own checks.

## Checks you must run and pass
1. Your verify.py — all assertions pass.
2. `python scripts/check_quality.py {slug}` — OK.
3. `node scripts/check_math.js {slug}` — 0 errors.
4. `python scripts/build.py` — builds.
5. `python scripts/math_sheet.py {slug} --all` — PNG sheets (5 questions each, correct option marked ✓). Open EVERY PNG with the Read tool and read every question as the student: unambiguous, exactly one right option, the explanation teaches, formulas render, the correct option does not stand out by form. Fix and re-run until clean.

## Final answer
Plain text, short: the 5 block names, how many items verify.py checked, conventions you had to choose and how you stated them, sources you could not read.
