# learning-test: software requirements specification

This specification was reverse-engineered from the code at commit `f31a945`
(2026-11-10) and written on 2026-11-18. It lists only behaviour that the code
implements. Where the code gives no answer, the question goes to
[section 9](#9-open-questions). The documentation hub is
[docs/README.md](docs/README.md).

## 1. Purpose and scope

The system turns test content (50 multiple-choice questions per test) into
static HTML pages. You take the tests in a browser. Progress is kept on the
device and can be merged through the user's Google Drive (`README.md:3-9`,
`README.md:27`).

**In scope**

- Test pages: shuffling, answering, explanations, results, mistakes mode
  (`scripts/template.html`).
- Home page: grouping by status, the "continue" card, labs (`index.html`).
- Progress model and Drive sync (`progress.js`, `sync.js`).
- Local tooling: build, content quality checks, formula checks, image checks
  and attachment, preview sheets, content patch tools, one-command test
  creation (`scripts/`).
- Harvesting study topics from Google Tasks (`scripts/fetch_tasks.py`,
  `scripts/filter_learning_tasks.py`).

**Out of scope** (no code in this repository)

- The GitHub Pages hosting configuration (`CLAUDE.md:193` refers to GitHub's
  workflow).
- The Google Cloud OAuth client and its consent screen.
- The image-drawing runner `_tools/lt-images` and the Telegram notifier, which
  `scripts/new_test.py:38-39` calls by absolute path.
- The `learning-test-new` skill named in `CLAUDE.md:115`.
- The content of the 19 labs in `sims/`. They are self-contained pages and this
  spec covers only how they are linked.

## 2. Context

**Actors**

| Actor | Evidence |
|---|---|
| Learner using the site in a browser | `index.html`, `scripts/template.html`. `scripts/authoring/AUTHOR_PROMPT.md:12` names the repository owner as the intended learner |
| Maintainer running local scripts | `CLAUDE.md:170-187` |
| Automated test author (`claude -p` process) started by `new_test.py` | `scripts/new_test.py:138-161` |

**External systems**

| System | Used for | Source |
|---|---|---|
| GitHub Pages | Serving the site from branch `main` | `README.md:31`, `CLAUDE.md:4-5` |
| Google Identity Services (`accounts.google.com/gsi/client`) | OAuth access token in the browser | `sync.js:53-93` |
| Google Drive API v3 | Storing `learntest_<slug>.json` per test | `sync.js:97-144`, `188` |
| Google Search | "Найти в Google" link per question | `scripts/template.html:260` |
| Google Tasks API | Source of study topics | `scripts/fetch_tasks.py:24-41` |
| `claude` CLI | Writing a new test | `scripts/new_test.py:143-145` |
| git remote `origin` | Commit and push of a new test | `scripts/new_test.py:194-203` |
| Google Chrome (headless, CDP) | PNG preview sheets | `scripts/sheet_shot.js:9`, `16-18` |

**Runtime environment**

- Browser: static HTML, CSS and JavaScript. The pages use a mobile viewport and
  light/dark colours via `prefers-color-scheme` (`index.html:5`, `86-88`). No
  minimum browser version is stated.
- Tooling: Python 3 and Node.js. Neither version is declared. The checks in
  [section 8](#8-acceptance) ran with Python 3.13.3 and Node v23.11.0.
- OS: `new_test.py` and `sheet_shot.js` contain Windows-specific code: detached
  process flags, `taskkill`, PowerShell and a Windows Chrome path
  (`scripts/new_test.py:246-256`, `scripts/sheet_shot.js:9`, `34-41`). The
  browser side and the check scripts have no OS-specific code.

## 3. Functional requirements

### 3.1 Test page

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-1 | The system shall present a test as 50 questions, one per screen, with a progress bar and a label naming one of five fixed blocks of 10 questions. | `scripts/template.html:173-179`, `252`, `287-305` | no test |
| FR-2 | The system shall shuffle the options of every question on each page load, on entering mistakes mode and on reset, and remap the correct index to match. The shuffled order shall not be stored. | `scripts/template.html:219-244`, `388`, `526` | `test_shuffle.js` (tests 1–3, 6) |
| FR-3 | The system shall accept only the first answer to each question and store it as `{selectedText, correct}`. | `scripts/template.html:314-316` | `test_shuffle.js` (round-trip test, wiring check `usesSelectedText`) |
| FR-4 | After an answer, the system shall mark the correct option, mark a wrong chosen option, and show the explanation and the "Без этого / С этим" example with its benefit line. | `scripts/template.html:262-283` | no test |
| FR-5 | The system shall render question fragments inside triple backticks as preformatted code, and an option wrapped entirely in backticks as inline code. | `scripts/template.html:482-490`, `515-521` | no test |
| FR-6 | The system shall typeset `\( \)` and `\[ \]` formulas with the bundled KaTeX, not use `$` as a delimiter, and show the source instead of failing on a bad formula. | `scripts/template.html:503-512` | content: `check_math.js`. Page: no test |
| FR-7 | The system shall show a question's image under its text, link it to the full-size file and show its credit caption if present. | `scripts/template.html:460-467` | `images.py check`, `check_quality.py` (file exists, alt present) |
| FR-8 | The system shall offer a Google search link built from the question text, with code fragments and LaTeX delimiters removed. | `scripts/template.html:260`, `493-497` | no test |
| FR-9 | After the last question, the system shall show the score out of 50 and the score per block. | `scripts/template.html:333-358` | no test |
| FR-10 | "Пересмотреть ответы" shall return to question 1 for review, and the test shall still count as done. | `scripts/template.html:367-370`, `progress.js:24-27` | `test_progress.js` "done: reached the end, or answered everything…" |
| FR-11 | Reset shall ask for confirmation, clear the test's state and reshuffle. | `scripts/template.html:523-530` | `test_shuffle.js` (wiring check `reshuffledOnReset`) |
| FR-12 | Mistakes mode (`?mode=mistakes` or the result-screen button) shall go only through questions whose first answer was wrong and not yet fixed. A correct answer there shall record `fixed[i]` with a timestamp and leave the score unchanged. | `scripts/template.html:378-456`, `540-542`, `progress.js:43-52` | `test_progress.js` "mistakes: first-attempt errors minus the fixed ones" |
| FR-13 | If no unfixed mistakes remain when mistakes mode starts, the system shall return to the normal view and say so in a toast. | `scripts/template.html:379-386` | no test |
| FR-14 | The test page shall show a lab button when the test has a `sim`: a local `sims/<sim>.html`, or an external URL opened in a new tab. | `scripts/build.py:83-90` | no test |

### 3.2 Progress state

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-15 | The system shall save the test state to `localStorage["learntest_<slug>"]` and set `updatedAt` on every save. | `scripts/template.html:172`, `188-191` | no test |
| FR-16 | The system shall treat a test as `done` when `current >= 50` or all 50 questions are answered, as `progress` when at least one is answered, and as `todo` otherwise. | `progress.js:24-32` | `test_progress.js` "done: …" |
| FR-17 | On saves outside mistakes mode, the system shall record the test as the last opened one in `ltindex_last`. | `scripts/template.html:193-196` | no test |

### 3.3 Home page

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-18 | The home page shall list every test in `TESTS`, grouped as "В процессе", "Работа над ошибками", "Не начаты", "Выполнены" and "Лаборатории", with a count per group. It shall remember each group's open state in `ltindex_open`. | `index.html:209-226`, `265-277`, `323-344` | no test |
| FR-19 | The home page shall show a "Продолжить" card for the last opened test if it is in progress, otherwise for the in-progress test with the latest `updatedAt`. | `index.html:299-321` | no test |
| FR-20 | Within a group, the home page shall fold two or more tests of the same `TSI <course>` title prefix into one expandable row. | `index.html:280-295`, `progress.js:70-73` | `test_progress.js` "courseOf: TSI course prefixes, nothing else" |
| FR-21 | Each test card shall show "Не начато", the answered position, the final score or the open mistake count, with a percentage bar outside the mistakes group. | `index.html:231-255` | no test |
| FR-22 | Cards in the mistakes group shall open the test with `?mode=mistakes`. | `index.html:238-240`, `330` | no test |
| FR-23 | The home page shall list the labs in `SIMS` as links to `sims/<slug>.html`. | `index.html:185-205`, `257-263`, `332` | no test |

### 3.4 Synchronisation with Google Drive

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-24 | When `GOOGLE_CLIENT_ID` is empty, the system shall disable sync, say so when the sync button is pressed, and keep working from `localStorage`. | `config.js:1-4`, `sync.js:25-27`, `66`, `index.html:365-369` | no test |
| FR-25 | The system shall reuse a cached access token until 2 minutes before it expires. Otherwise it shall load Google Identity Services, request a token silently, and show the consent screen at most once. | `sync.js:29-37`, `53-93` | no test |
| FR-26 | `syncAll` shall compare each test present locally or on Drive and keep the newer copy. The order is `updatedAt` first, then the answered count; on a tie the local copy wins. It shall pull the remote copy or push the local one, and report `{pulled, pushed, same, failed}`. | `sync.js:212-253`, `progress.js:58-66` | `test_progress.js` "merge: the fresher copy wins on each side", "pickNewer: …" |
| FR-27 | If the Drive file listing fails, `syncAll` shall report an error and upload nothing. | `sync.js:116-122`, `217` | `test_progress.js` "merge: Drive not answering is an error…" |
| FR-28 | Non-interactive sync shall never open a sign-in window and shall report `no-token` when no live token exists. | `sync.js:254-257` | `test_progress.js` "auto mode never asks for a login…" |
| FR-29 | The home page shall run non-interactive sync on open. The line under the title shall become a tap target that starts interactive sync. The list shall be redrawn when anything was pulled. | `index.html:381-403` | no test |
| FR-30 | While a token is alive, a test page shall upload its own state 4 s after a save, and at once when the page becomes hidden. | `scripts/template.html:203-216`, `sync.js:262-270` | `test_progress.js` "uploadOne: quiet, one test, only with a live token" |
| FR-31 | An upload shall update an existing Drive file by `PATCH`, or create one by `POST` when none is found, as a multipart request. | `sync.js:124-144` | `test_progress.js` (asserts no duplicate `POST` for an existing file) |
| FR-32 | The sync dialog shall also offer "upload all" and "download all". Download asks for confirmation before replacing local progress. | `sync.js:157-205`, `index.html:421-451`, `scripts/template.html:581-611` | no test |

### 3.5 Build and content checks

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-33 | `build.py` shall write `tests/<slug>.html` for every `TOPICS` entry that has a content file, by replacing `__TITLE__`, `__TEST_ID__`, `__SIM_LINK__` and `__QUESTIONS_JSON__`. It shall list and skip entries with no content file. | `scripts/build.py:92-125` | manual: in-memory replay matched all 52 pages at `f31a945` |
| FR-34 | `build.py` shall stop with an error when a test does not have exactly 50 questions, a question does not have exactly 4 options, or `correct` is outside 0..3. | `scripts/build.py:75-81` | no test |
| FR-35 | `check_quality.py` shall exit 1 and list violations for any of the following. Option text is measured as displayed, with LaTeX stripped. | `scripts/check_quality.py:43-50`, `86-157`, `185-187` | the script itself |
| | a question count other than 50 | | |
| | an option count other than 4 | | |
| | empty or duplicate options | | |
| | `correct` out of range | | |
| | unbalanced math delimiters | | |
| | LaTeX only in the correct option | | |
| | any answer position used fewer than 5 times | | |
| | correct option strictly longest in more than 35% of questions | | |
| | mean length of correct options more than 15% from the others | | |
| | any question where only the correct option has a parenthesis | | |
| | a missing image file or alt text | | |
| FR-36 | `check_math.js` shall render every formula in the questions, options, explanations and non-code `usage` with KaTeX (`throwOnError`), skipping fenced code, and exit 1 on any error. | `scripts/check_math.js:14-44` | the script itself |
| FR-37 | `images.py check` shall report and exit non-zero on any of the following. | `scripts/images.py:54-65`, `85-159` | the script itself |
| | two files for one question number | | |
| | a file for a question that does not exist | | |
| | missing alt | | |
| | a raster image without credit | | |
| | SVG over 60 KB, raster over 900 KB | | |
| | wrong `viewBox` | | |
| | no white first `rect` | | |
| | font size below 16 | | |
| | stroke width below 1.5 | | |
| | `<script>`, `foreignObject`, `onload=` or `onclick=` (no other event handlers are checked) | | |
| | external references | | |
| | the full correct option (at least 12 characters, normalised) written in the SVG text | | |
| FR-38 | `images.py attach` shall set `img = {src, alt, credit?}` for every question with a file `img/<slug>/NN.<ext>`, remove `img` where no file exists, and write compact JSON. | `scripts/images.py:162-182` | no test |
| FR-39 | `images.py sheet` and `frames`, and `math_sheet.py`, shall write HTML preview pages to a temp directory and turn them into PNGs through `sheet_shot.js`. The pages are images 10 per sheet, animation frames at 0, ¼, ½ and ¾ of the cycle, and 5 questions per sheet with the correct option marked. | `scripts/images.py:185-249`, `scripts/math_sheet.py:38-80` | no test |
| FR-40 | `shuffle_options.py` shall permute options with seed 20260720 for all or the given slugs and recompute `correct`. With `--check` it shall only print the position distribution. | `scripts/shuffle_options.py:28`, `46-90` | no test |
| FR-41 | `apply_balanced.py`, `apply_parenfix.py`, `apply_practical.py` and `merge_usage.py` shall apply stored patch data to content only after their integrity checks pass, and with `--check` shall validate without writing. The checks are: correct index unchanged, correct option unchanged byte for byte, questions 0..39 untouched, 50 valid `usage` objects. | file docstrings (`scripts/apply_balanced.py:1-16`, `apply_parenfix.py:1-16`, `apply_practical.py:1-14`, `merge_usage.py:1-15`) | the `--check` modes |

### 3.6 One-command test creation (`scripts/new_test.py`)

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-42 | The command shall require `--title` and `--topic`, derive or accept a slug matching `[a-z][a-z0-9_]{2,59}`, and refuse a slug already registered or present in content. It shall also refuse a `--source` path that does not exist. | `scripts/new_test.py:46-57`, `229-238` | no test |
| FR-43 | The command shall write a job spec, add the slug to `TOPICS` in `build.py` under an inter-process lock, start a detached job process, print the log path and return. | `scripts/new_test.py:239-259`, `60-87` | no test |
| FR-44 | The job shall run the author (`claude -p` with `AUTHOR_PROMPT.md` filled in) and then run `check_quality`, `check_math`, `build` and `test_shuffle`. If they fail, it shall run the author once more with the failure text. If they still fail, it shall send a failure notice and not publish. | `scripts/new_test.py:126-183` | no test |
| FR-45 | On success the job shall do the following, in order. | `scripts/new_test.py:184-211`, `90-109` | no test |
| | add the test to `TESTS` in `index.html`, after the last test of the same TSI course or at the end | | |
| | rebuild | | |
| | commit the test's files | | |
| | `pull --rebase --autostash` and push to `origin main`, unless `--no-push` | | |
| | send the page link | | |
| | run the image runner, unless `--no-images` | | |
| | with `--no-commit`: only add the home page row | | |

### 3.7 Study-topic harvesting

| ID | Requirement | Source | Verification |
|---|---|---|---|
| FR-46 | `fetch_tasks.py` shall download up to 100 Google Tasks lists (the list request is not paged) with all their tasks, including completed and hidden tasks, to `scripts/tasks_raw.json`, refreshing `scripts/token.json` when it has expired. | `scripts/fetch_tasks.py:15-65`, `28` | no test |
| FR-47 | `filter_learning_tasks.py` shall keep tasks that are not completed and whose title or notes contain a keyword from its list, case-insensitive, write them to `scripts/filtered_candidates.json` and print them. | `scripts/filter_learning_tasks.py:9-47` | no test |

### 3.8 Declared but not implemented

| Item | Source | State in code |
|---|---|---|
| Spaced repetition "Пора повторить" | `CLAUDE.md:41-43`, `progress.js:12-13` | Removed on 2026-10-17. Old `doneAt` and `review` fields are ignored. `test_progress.js:39-47` asserts that nothing of it remains. A template comment still names «Повторения» (`scripts/template.html:254-255`) |
| The multi-step practical-block rule "applies to tests the user has not passed yet", judged from Drive progress | `CLAUDE.md:101-102` | No code reads Drive progress to decide this. `apply_practical.py` applies whatever is in `scripts/practical/` |
| `check_quality.py` "handy for CI" | `scripts/check_quality.py:19` | No CI configuration in the repository |
| Author's `verify.py` that recomputes every numeric answer | `scripts/authoring/AUTHOR_PROMPT.md:22` | Written to `%TEMP%` by the author process, not stored in the repository. Not verifiable here |
| Content block structure in the author prompt | `scripts/authoring/AUTHOR_PROMPT.md:14-19` | The page always shows the template's fixed block names (`scripts/template.html:173-179`) |

## 4. Interfaces

### 4.1 Web pages and URL parameters

| Path | Purpose | Source |
|---|---|---|
| `index.html` | Home page | `index.html` |
| `tests/<slug>.html` | Test page | `scripts/build.py:97` |
| `tests/<slug>.html?mode=mistakes` | Mistakes mode | `scripts/template.html:540-542` |
| `sims/<slug>.html` | Lab page | `index.html:260` |

### 4.2 JavaScript modules

| Global | Functions | Source |
|---|---|---|
| `LTProgress` (a CommonJS export instead when `module` exists, as under Node) | `TOTAL`, `answeredCount`, `isDone`, `status`, `correctCount`, `mistakes`, `pickNewer`, `courseOf` | `progress.js:75-81` |
| `LTSync` | `configured`, `hasToken`, `uploadAll`, `downloadAll`, `syncAll`, `uploadOne`, `signOut` | `sync.js:272-280` |

### 4.3 Google Drive calls (`sync.js`)

| Call | Request | Source |
|---|---|---|
| Find one file | `GET /drive/v3/files?q=name='<file>' and trashed=false` | `sync.js:97-103` |
| List progress files | `GET /drive/v3/files?q=name contains 'learntest_' and trashed=false&pageSize=1000` | `sync.js:105-122` |
| Read file | `GET /drive/v3/files/<id>?alt=media` | `sync.js:188`, `236` |
| Create file | `POST /upload/drive/v3/files?uploadType=multipart` | `sync.js:132-136` |
| Update file | `PATCH /upload/drive/v3/files/<id>?uploadType=multipart` | `sync.js:132-136` |

All calls send `Authorization: Bearer <token>`. The OAuth scope is `drive.file`
(`sync.js:22`).

### 4.4 Command-line tools

| Command | Arguments | Exit code | Source |
|---|---|---|---|
| `python3 scripts/build.py` | none | non-zero on a validation error | `scripts/build.py:103-125` |
| `python3 scripts/check_quality.py` | `[slug ...]` | 1 on violations | `scripts/check_quality.py:15-19` |
| `node scripts/check_math.js` | `[slug ...]` | 1 on any formula error | `scripts/check_math.js:4-5`, `44` |
| `node scripts/test_shuffle.js` | none | 1 on failure | `scripts/test_shuffle.js:5` |
| `node scripts/test_progress.js` | none | 1 on failure | `scripts/test_progress.js:2` |
| `python scripts/images.py` | `check [slug ...]` \| `attach [slug ...]` \| `sheet <slug>` \| `frames <slug>` | non-zero on `check` errors | `scripts/images.py:8-14` |
| `python scripts/math_sheet.py` | `<slug> [--all]` | not stated | `scripts/math_sheet.py:4` |
| `node scripts/sheet_shot.js` | `<file-or-url> <out.png> [width] [js]` | 1 on error, 2 on 60 s timeout | `scripts/sheet_shot.js:1-2`, `44` |
| `python scripts/new_test.py` | `--title --topic [--slug] [--source ...] [--model] [--no-images] [--no-push] [--no-commit]` | argparse error on bad input | `scripts/new_test.py:4-6`, `215-238` |
| `python3 scripts/shuffle_options.py` | `[--check] [slug ...]` | not stated | `scripts/shuffle_options.py:9-11` |
| `python3 scripts/apply_balanced.py`, `apply_parenfix.py`, `apply_practical.py`, `merge_usage.py` | `[--check]` | 1 on problems | file docstrings |
| `python scripts/authoring/<slug>.py` | none | `AssertionError` if not exactly 50 entries | e.g. `scripts/authoring/dsp_fourier_series_spectra.py:563` |

### 4.5 File formats

| File | Format | Source |
|---|---|---|
| `scripts/content/<slug>.json` | JSON array of 50 questions, one compact object per line | `CLAUDE.md:9-12`, `52-53`, `scripts/images.py:41-45` |
| `img/<slug>/meta.json` | `{"NN": {"alt": "...", "credit": "..."}}` | `scripts/images.py:3-6` |
| `scripts/balanced/<slug>.json` | array of 50 `{options[4], correct}` | `scripts/apply_balanced.py:3-6` |
| `scripts/parenfix/<slug>.json` | `{"<idx>": [4 options]}` | `scripts/apply_parenfix.py:6-7` |
| `scripts/practical/<slug>.json` | `{"40": question, ..., "49": question}` | `scripts/apply_practical.py:3-6` |
| `scripts/usage/<slug>.json` | array of 50 `{code, without, with, benefit}` | `scripts/merge_usage.py:3-6` |
| Drive `learntest_<slug>.json` | same JSON as `localStorage["learntest_<slug>"]` | `sync.js:11-12` |
| Job spec `%LOCALAPPDATA%\learning-test\jobs\<slug>.json` | `{slug, title, topic, sources, model, images, no_push, no_commit}` | `scripts/new_test.py:240-242` |

## 5. Data

**Question**

`{q, options[4], correct, explain, usage, img?}`, where `correct` is 0..3,
`usage` is `{code: bool, without, with, benefit}` and `img` is
`{src, alt, credit?}` (`CLAUDE.md:9-12`, `CLAUDE.md:119-123`). At `f31a945`
there were 2600 questions in 52 files, and every question had `usage` (508 with
`code: true`), according to a read-only count. There were 1415 images
(`images.py check`).

**Test state** (`progress.js:5-13`)

| Field | Meaning |
|---|---|
| `current` | Index of the current question, 0..50 |
| `answers` | `{i: {selectedText, correct}}`, the first answer per question |
| `updatedAt` | Time of the last save, in milliseconds |
| `fixed` | `{i: ms}`, mistakes fixed in mistakes mode |
| `doneAt`, `review` | Optional legacy fields from the removed repetition feature. They are ignored |

**Browser storage (`localStorage`)**

| Key | Content | Synced | Source |
|---|---|---|---|
| `learntest_<slug>` | Test state | yes | `scripts/template.html:172` |
| `ltindex_last` | `{slug, at}` | no | `scripts/template.html:195` |
| `ltindex_open` | `{groupKey: bool}` | no | `index.html:218` |
| `gdrive_access_token`, `gdrive_token_expiry` | OAuth token and its expiry time in ms | no | `sync.js:19-20`, `39-44` |

**Local job data** (`scripts/new_test.py:35-36`, `166`, `250`)

The directory `%LOCALAPPDATA%\learning-test\jobs\` holds:

- `<slug>.json`: the job spec;
- `<slug>.log` and `<slug>.log.stdout`: the job's log and its captured output;
- `git.lock`: the inter-process lock.

**Git-ignored local files** (`.gitignore:1-7`)

`scripts/token.json`, `scripts/credentials.json`, `scripts/tasks_raw.json`,
`scripts/filtered_candidates.json` and `.env`. No code in the repository reads
`.env`.

## 6. Non-functional requirements

| ID | Requirement | Source |
|---|---|---|
| NFR-1 | Tests shall work without a network connection except for sync and the search link. KaTeX is bundled, with no CDN. | `scripts/template.html:7`, `166-167`, `vendor/katex/README.txt`, `CLAUDE.md:157` |
| NFR-2 | SVG images shall work offline. External references, scripts and `foreignObject` are rejected. | `scripts/images.py:115-120` |
| NFR-3 | Drive access shall be limited to the `drive.file` scope. | `sync.js:22` |
| NFR-4 | A cached token shall be treated as expired 2 minutes before its expiry time. The default lifetime is 3600 s. | `sync.js:34`, `42` |
| NFR-5 | Automatic sync shall not open pop-ups. | `sync.js:254-257`, `index.html:377-380` |
| NFR-6 | A Drive listing returns at most 1000 files. There is no pagination. | `sync.js:107`, `118` |
| NFR-7 | Per-test uploads shall be debounced by 4000 ms. | `scripts/template.html:206` |
| NFR-8 | Question text, options, explanations, `usage` and image attributes shall be HTML-escaped before insertion. | `scripts/template.html:469-478`, `262-283` |
| NFR-9 | Image size limits: SVG up to 60 KB, raster up to 900 KB. SVG `viewBox` width 480 and height 240..360, font at least 16, stroke at least 1.5. | `scripts/images.py:31-32`, `97-114` |
| NFR-10 | The author process shall time out after 150 minutes. The git lock waits up to 600 s, and a lock older than 900 s is treated as stale. | `scripts/new_test.py:152`, `66-74` |
| NFR-11 | The author process runs with `--permission-mode bypassPermissions` and `--setting-sources project`. | `scripts/new_test.py:144-145` |
| NFR-12 | Screenshot runs shall be isolated (random port 9400–9899, a temporary Chrome profile), shall end within 60 s and shall kill leftover Chrome processes. | `scripts/sheet_shot.js:13-14`, `25-44` |
| NFR-13 | Content JSON shall stay in the compact one-question-per-line format when written by tools. | `CLAUDE.md:52-53`, `scripts/images.py:41-45`, `scripts/shuffle_options.py:70-74` |
| NFR-14 | Subprocesses of `new_test.py` shall run with UTF-8 I/O (`PYTHONIOENCODING`, `PYTHONUTF8`). | `scripts/new_test.py:40` |

## 7. Constraints and dependencies

- The repository has no package manifest or lock file (`git ls-files`).
- KaTeX 0.19.1 (MIT) is vendored: `katex.min.js`, `katex.min.css`,
  `auto-render.min.js` and fonts (`vendor/katex/README.txt`).
- Google Identity Services is loaded at run time from
  `https://accounts.google.com/gsi/client` (`sync.js:56`).
- Python: `build.py`, `check_quality.py`, `images.py`, `math_sheet.py`,
  `new_test.py` and the `apply_*` tools use only the standard library (their
  imports).
- `fetch_tasks.py` imports `google.auth`, `google.oauth2` and
  `googleapiclient` (`scripts/fetch_tasks.py:3-5`). No file declares them.
- Node: built-in `fs`, `path`, `os`, `assert` and `child_process`. `sheet_shot.js`
  uses the global `fetch` and `WebSocket` (`scripts/sheet_shot.js:4-7`, `48`,
  `52`).
- External programs:
  - Google Chrome (`scripts/sheet_shot.js:9`);
  - the `claude` CLI and `git` (`scripts/new_test.py:143`, `194-203`);
  - the image runner and the Telegram notifier at absolute paths outside the
    repository (`scripts/new_test.py:38-39`).
- The author prompt expects `sympy` and `pymupdf` in the author's environment
  (`scripts/authoring/AUTHOR_PROMPT.md:9`, `22`).
- Licence: MIT (`LICENSE`).

## 8. Acceptance

Automated checks, all read-only, with their results at `f31a945` on
2026-11-18:

| Command | Expected | Observed |
|---|---|---|
| `python3 scripts/check_quality.py` | exit 0 | 52 tests OK, exit 0 |
| `node scripts/check_math.js` | 0 errors | 2799 formulas, 0 errors |
| `node scripts/test_shuffle.js` | ALL CHECKS PASSED | passed: 52 pages, 7800 question shuffles |
| `node scripts/test_progress.js` | ALL CHECKS PASSED | 9 of 9 passed |
| `python scripts/images.py check` | 0 errors | 1415 images, 0 errors |
| `python3 scripts/apply_practical.py --check`, `merge_usage.py --check` | exit 0 | 15/15 and 19/19 |
| `python3 scripts/apply_balanced.py --check`, `apply_parenfix.py --check` | exit 0 | **fail**: 14 of 19 and 2 of 13 tests no longer match the stored patch data |

Freshness of the generated pages: `tests/*.html` should equal what
`python3 scripts/build.py` produces. An in-memory replay of the build at
`f31a945` matched all 52 pages. The replay was a one-off command, not a project
script.

Manual checks (no automation exists):

1. Serve the root with `python -m http.server 8123` (`.claude/launch.json:5-8`)
   and open `index.html`.
2. Answer a question, reload, and check that the options moved and the answer
   kept its highlight (FR-2, FR-3).
3. Finish a test with wrong answers, open mistakes mode, fix one, and check
   that the score is unchanged (FR-9, FR-12).
4. With a configured client ID, sign in from the sync line, then check that a
   second device receives the newer copy (FR-26, FR-29).

## 9. Open questions

1. Who uses the site besides the owner? The code does not say. Does the OAuth
   consent screen admit other Google accounts? That is configured outside the
   repository.
2. Which browsers and versions are targeted? Nothing in the code states it.
3. How is GitHub Pages set up (branch, folder, Jekyll processing)? The
   repository only says it is served from `main`.
4. Which Python and Node versions are required? None are declared.
   `.claude/launch.json` points to Python 3.13. Inference: `sheet_shot.js`
   uses the global `WebSocket` (`scripts/sheet_shot.js:28`, `52`), which Node
   enables by default only from version 22. That sets a floor for the preview
   tooling, not for the other scripts.
5. Are `scripts/balanced/`, `scripts/parenfix/`, `scripts/practical/` and
   `scripts/usage/` still needed? Two of the four tools fail `--check` against
   the current content.
6. Should the block names on the page follow each test's own structure? The
   template fixes them, while the author prompt defines different ones.
7. Is it intended that home-page titles (`index.html`) and page titles
   (`scripts/build.py`) differ? Partly answered by the code: the `TSI ` prefix
   is dropped on purpose. `new_test.py` strips it from the `build.py` title
   (`scripts/new_test.py:82`) and keeps it in `index.html`
   (`scripts/new_test.py:99`), where course grouping reads it
   (`progress.js:70-73`). Still open: other differences, such as the shortened
   home-page titles (`index.html:150` against `scripts/build.py:47`).
8. How is `scripts/token.json` for `fetch_tasks.py` obtained the first time?
   No authorisation flow exists in the repository.
9. Can a failed `findFile` lookup create duplicate Drive files
   (`sync.js:97-103`, `125-134`)? The code says yes. `findFile` returns `null`
   on a network error and also on a non-OK response, because it does not check
   `r.ok`. `uploadFile` then sends a `POST` that creates a second file with the
   same name. If duplicates exist, uploads update the first file the name query
   returns (`sync.js:101`). `syncAll` instead compares against the last listed
   file of that name (`sync.js:219-221`). Still open: the order Drive returns
   them in, because the code sets no `orderBy`. No test covers this path.
10. What do the external image runner `_tools/lt-images` and the Telegram
    notifier do, and what do they require? They are outside this repository.
11. Should `new_test.py` push straight to `main` (`scripts/new_test.py:203`),
    given `CLAUDE.md:191` says development happens on a separate branch?
