"""Новый тест на 50 вопросов: автор (claude -p) в отдельном процессе, затем
проверки, публикация и уведомление в Telegram.

    python scripts/new_test.py --title "TSI DSP 5: Дискретизация" --topic "что покрыть" \\
        [--slug dsp_sampling] [--source "G:\\My Drive\\TSI\\...\\lecture.pdf" ...] \\
        [--model opus] [--no-images] [--no-push] [--no-commit]

Команда возвращается сразу: пишет тест отдельный процесс (автор работает
40–60 мин, а чат канвы dg живёт 15 мин). Ход работы — в журнале
%LOCALAPPDATA%\\learning-test\\jobs\\<slug>.log.

Что делает процесс:
1. Автор по scripts/authoring/AUTHOR_PROMPT.md пишет scripts/authoring/<slug>.py
   и scripts/content/<slug>.json и сам проверяет их.
2. Здесь проверки повторяются: check_quality, check_math, build, test_shuffle.
   Не прошли — одна попытка починки с текстом ошибки; снова нет — тест не
   публикуется, в Telegram уходит причина.
3. Прошли — строка на главной (index.html), коммит, пуш в main, ссылка в Telegram.
4. Без --no-images — картинки к вопросам раннером _tools/lt-images (Sonnet).

LT_CLAUDE — путь к claude вместо найденного в PATH (для проверки на заглушке).
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JOBS = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "learning-test", "jobs")
LOCK = os.path.join(JOBS, "git.lock")
SITE = "https://igorsvolohovs.github.io/learning-test/tests/"
IMAGES_RUNNER = r"C:\Users\igors\Projects\_tools\lt-images\run.py"
NOTIFY = r"C:\Users\igors\Projects\personal-agent\tools\send_card_to_owner_telegram.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r",
                     "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def slug_from(title):
    t = "".join(TRANSLIT.get(c, c) for c in title.lower())
    t = re.sub(r"^tsi\s+", "", t)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:60].rstrip("_")


def topics_text():
    return open(os.path.join(HERE, "build.py"), encoding="utf-8").read()


def registered(slug):
    return re.search(r'^    "%s": \{' % re.escape(slug), topics_text(), re.M) is not None


class GitLock:
    """Межпроцессный замок на правки build.py/index.html и git: тестов может
    писаться несколько сразу."""

    def __enter__(self):
        os.makedirs(JOBS, exist_ok=True)
        for _ in range(600):
            try:
                self.fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() - os.path.getmtime(LOCK) > 900:
                    os.remove(LOCK)
                time.sleep(1)
        raise RuntimeError("замок git занят больше 10 минут: " + LOCK)

    def __exit__(self, *a):
        os.close(self.fd)
        os.remove(LOCK)


def register_build(slug, title):
    build_title = re.sub(r"^TSI\s+", "", title)
    s = topics_text()
    entry = '    "%s": {"title": %s, "sim": ""},\n' % (slug, json.dumps(build_title, ensure_ascii=False))
    end = s.index("\n}\n", s.index("TOPICS = {"))
    s = s[:end + 1] + entry + s[end + 1:]
    open(os.path.join(HERE, "build.py"), "w", encoding="utf-8", newline="").write(s)


def register_index(slug, title):
    p = os.path.join(ROOT, "index.html")
    s = open(p, encoding="utf-8").read()
    if '["%s",' % slug in s:
        return
    head = s.index("const TESTS = [") + len("const TESTS = [")
    end = s.index("\n  ];", head)
    lines = [ln.rstrip().rstrip(",") for ln in s[head:end].split("\n") if ln.strip()]
    assert all(re.fullmatch(r'    \["[^"]+", "[^"]*"\]', ln) for ln in lines), "неожиданный формат TESTS в index.html"
    new = '    [%s, %s]' % (json.dumps(slug), json.dumps(title, ensure_ascii=False))
    # Тест курса TSI встаёт после последнего теста того же курса, иначе — в конец.
    m = re.match(r"(TSI \S+?)(?:\s+\d+)?:", title)
    at = len(lines)
    if m:
        same = [i for i, ln in enumerate(lines) if re.search(r', "%s[ :]' % re.escape(m.group(1)), ln)]
        if same:
            at = same[-1] + 1
    lines.insert(at, new)
    s = s[:head] + "\n" + ",\n".join(lines) + s[end:]
    open(p, "w", encoding="utf-8", newline="").write(s)


def run(cmd, log, timeout=None, **kw):
    r = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, **kw)
    shown = [a if len(a) <= 120 else f"<{len(a)} знаков>" for a in cmd[:6]]
    log(f"$ {' '.join(shown)}{' …' if len(cmd) > 6 else ''} → {r.returncode}")
    return r


def notify(text):
    if os.path.exists(NOTIFY):
        subprocess.run([sys.executable, NOTIFY, "--text", text], cwd=os.path.dirname(os.path.dirname(NOTIFY)),
                       env=ENV, capture_output=True)


def checks(slug, log):
    out = []
    if not os.path.exists(os.path.join(HERE, "content", slug + ".json")):
        return "нет scripts/content/%s.json — автор не записал тест" % slug
    for cmd in ([sys.executable, "scripts/check_quality.py", slug], ["node", "scripts/check_math.js", slug],
                [sys.executable, "scripts/build.py"], ["node", "scripts/test_shuffle.js"]):
        r = run(cmd, log)
        if r.returncode != 0:
            out.append(f"{' '.join(cmd[-2:])}:\n{(r.stdout + r.stderr)[-1500:]}")
    return "\n\n".join(out)


def author(spec, log, extra=""):
    tpl = open(os.path.join(HERE, "authoring", "AUTHOR_PROMPT.md"), encoding="utf-8").read()
    sources = "\n".join(f"- `{s}`" for s in spec["sources"]) or "(none given)"
    prompt = (tpl.replace("{slug}", spec["slug"]).replace("{title}", spec["title"])
              .replace("{topic}", spec["topic"]).replace("{sources}", sources)) + extra
    claude = os.environ.get("LT_CLAUDE") or "claude"
    cmd = [claude, "-p", prompt, "--permission-mode", "bypassPermissions", "--setting-sources", "project",
           "--output-format", "json"]
    if spec.get("model"):
        cmd += ["--model", spec["model"]]
    if claude.endswith(".py"):
        cmd = [sys.executable] + cmd
    t0 = time.time()
    try:
        r = run(cmd, log, timeout=150 * 60)
        out = r.stdout
    except subprocess.TimeoutExpired:
        out = ""
        log("автор не уложился в 150 мин")
    try:
        j = json.loads(out)
        log(f"автор: {int(time.time() - t0) // 60} мин, ${j.get('total_cost_usd')}, итог:\n{str(j.get('result'))[:1500]}")
    except Exception:
        log(f"автор: {int(time.time() - t0) // 60} мин, ответ не JSON: {out[-500:]}")


def run_job(slug):
    spec = json.load(open(os.path.join(JOBS, slug + ".json"), encoding="utf-8"))
    logf = open(os.path.join(JOBS, slug + ".log"), "a", encoding="utf-8")

    def log(msg):
        logf.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
        logf.flush()

    log(f"старт: {spec['title']}")
    author(spec, log)
    fail = checks(slug, log)
    if fail:
        log("проверки не прошли, одна попытка починки:\n" + fail)
        author(spec, log, "\n\n## A previous run left the test failing these checks — fix them\n```\n" + fail + "\n```\n")
        fail = checks(slug, log)
    if fail:
        log("НЕ ОПУБЛИКОВАН:\n" + fail)
        notify(f"learning-test: тест «{spec['title']}» не прошёл проверки, не опубликован. "
               f"Журнал: {os.path.join(JOBS, slug + '.log')}")
        return 1
    if spec.get("no_commit"):
        with GitLock():
            register_index(slug, spec["title"])
        log("проверки прошли; --no-commit: строка на главной добавлена, коммита нет")
        return 0
    with GitLock():
        register_index(slug, spec["title"])
        run([sys.executable, "scripts/build.py"], log)
        files = [f"scripts/authoring/{slug}.py", f"scripts/content/{slug}.json", f"tests/{slug}.html",
                 "scripts/build.py", "index.html"]
        run(["git", "add"] + [f for f in files if os.path.exists(os.path.join(ROOT, f))], log)
        msg = (f"Тест «{spec['title']}»\n\n{spec['topic'][:600]}\n\nИсточники:\n"
               + ("\n".join("- " + s for s in spec["sources"]) or "- нет, по учебной литературе")
               + "\n\nНаписан scripts/new_test.py (автор claude -p), проверен check_quality, check_math, "
                 "build, test_shuffle.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
        r = run(["git", "commit", "-q", "-F", "-"], log, input=msg)
        pushed = False
        if r.returncode == 0 and not spec.get("no_push"):
            r1 = run(["git", "pull", "-q", "--rebase", "--autostash"], log)
            pushed = r1.returncode == 0 and run(["git", "push", "-q", "origin", "main"], log).returncode == 0
    log(f"опубликован: {'да' if pushed else 'коммит локально, без пуша'}")
    notify(f"learning-test: готов тест «{spec['title']}» — {SITE}{slug}.html"
           + ("" if pushed else " (не запушен — см. журнал)"))
    if spec.get("images") and os.path.exists(IMAGES_RUNNER):
        log("картинки: раннер lt-images, Sonnet")
        subprocess.run([sys.executable, IMAGES_RUNNER, "--model", "sonnet", "--workers", "1", slug]
                       + (["--no-push"] if spec.get("no_push") else []), env=ENV)
        log("картинки: раннер закончил")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--title")
    ap.add_argument("--topic")
    ap.add_argument("--slug")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--model", default="opus")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--run-job", metavar="SLUG", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.run_job:
        sys.exit(run_job(a.run_job))
    if not a.title or not a.topic:
        ap.error("нужны --title и --topic")
    slug = a.slug or slug_from(a.title)
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,59}", slug):
        ap.error(f"slug «{slug}» не подходит: латиница, цифры, _, 3–60 знаков")
    if registered(slug) or os.path.exists(os.path.join(HERE, "content", slug + ".json")):
        ap.error(f"тест {slug} уже есть — выберите другой --slug")
    missing = [s for s in a.source if not os.path.exists(s)]
    if missing:
        ap.error("источника нет на диске: " + "; ".join(missing))
    os.makedirs(JOBS, exist_ok=True)
    spec = dict(slug=slug, title=a.title, topic=a.topic, sources=[os.path.abspath(s) for s in a.source],
                model=a.model, images=not a.no_images, no_push=a.no_push or a.no_commit, no_commit=a.no_commit)
    json.dump(spec, open(os.path.join(JOBS, slug + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with GitLock():
        register_build(slug, a.title)
    logp = os.path.join(JOBS, slug + ".log")
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    cmd = [sys.executable, os.path.abspath(__file__), "--run-job", slug]
    out = open(logp + ".stdout", "a", encoding="utf-8")
    try:
        p = subprocess.Popen(cmd, cwd=ROOT, env=ENV, stdout=out, stderr=out, stdin=subprocess.DEVNULL,
                             creationflags=flags | (0x01000000 if os.name == "nt" else 0))  # BREAKAWAY_FROM_JOB
    except OSError:
        p = subprocess.Popen(cmd, cwd=ROOT, env=ENV, stdout=out, stderr=out, stdin=subprocess.DEVNULL,
                             creationflags=flags)
    print(f"Запущен автор теста «{a.title}» ({slug}), процесс {p.pid}.")
    print(f"Журнал: {logp}")
    print(f"Когда пройдут проверки: {SITE}{slug}.html (придёт сообщение в Telegram).")


if __name__ == "__main__":
    main()
