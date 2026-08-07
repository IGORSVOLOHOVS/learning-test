# learning-test

A set of self-marking study tests, published as a static site on GitHub Pages.

Nineteen topics so far, from linear algebra and probability to computer vision,
low-level C++, network drivers and photographic exposure. Each test is fifty
multiple-choice questions with four options, an explanation, and a worked
"without this / with this" example.

## How it is put together

- `scripts/content/<slug>.json` - the source of one test: fifty questions as
  `{q, options[4], correct, explain, usage}`, where `correct` is the index of
  the right option and `usage` holds the worked example. The JSON is kept
  compact on purpose - one question per line - and the editing scripts preserve
  that.
- `scripts/template.html` - the page template.
- `scripts/build.py` - bakes the JSON into the template, producing
  `tests/<slug>.html`. **Run it after any change to the content.**
- `scripts/check_quality.py` - refuses content where the right answer can be
  guessed from its shape rather than from knowing the subject. Non-zero exit on
  a violation.
- `index.html` - the list of tests; `sims/` - interactive labs;
  `sync.js` - progress synchronisation; `config.js` - the Google client id.

Progress is kept in `localStorage` and synchronised with Google Drive.

## Publishing

The site is served from `main`. A change only appears once it is on `main`.

```bash
python3 scripts/build.py
python3 scripts/check_quality.py
```

`CLAUDE.md` holds the full rules for writing a test - read it before adding one.
