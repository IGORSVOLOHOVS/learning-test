"""Картинки к вопросам: проверка, привязка к контенту, контактный лист.

Картинка вопроса N (1..50) теста <slug> лежит в img/<slug>/NN.<ext>
(svg, gif, png, jpg, webp), подписи — в img/<slug>/meta.json:
    {"01": {"alt": "что нарисовано", "credit": "автор, лицензия, URL"}, ...}
credit обязателен для картинок из интернета и пуст для своих.

    python scripts/images.py check  [slug ...]   # файлы, размеры, утечки ответа
    python scripts/images.py attach [slug ...]   # вписать поле img в content/<slug>.json
    python scripts/images.py sheet  <slug>       # PNG-листы по 10 картинок для осмотра
    python scripts/images.py frames <slug>       # кадры анимаций на 0, 1/4, 1/2, 3/4 цикла

Без slug — все тесты, у которых есть папка img/<slug>/.
Код возврата != 0 при ошибке check.
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTENT_DIR = os.path.join(HERE, "content")
IMG_DIR = os.path.join(ROOT, "img")
EXTS = ("svg", "gif", "png", "jpg", "jpeg", "webp")
MAX_SVG = 60 * 1024
MAX_RASTER = 900 * 1024
SVG_NS = "{http://www.w3.org/2000/svg}"


def load_content(slug):
    with open(os.path.join(CONTENT_DIR, slug + ".json"), encoding="utf-8") as f:
        return json.load(f)


def write_content(slug, questions):
    # Компактный формат: массив, по вопросу на строку, без пробелов в разделителях.
    lines = [json.dumps(q, ensure_ascii=False, separators=(",", ":")) for q in questions]
    with open(os.path.join(CONTENT_DIR, slug + ".json"), "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(lines) + "\n]\n")


def slugs_with_images():
    if not os.path.isdir(IMG_DIR):
        return []
    return sorted(d for d in os.listdir(IMG_DIR) if os.path.isdir(os.path.join(IMG_DIR, d)))


def find_files(slug):
    """{NN: имя файла}; два файла на один номер — ошибка."""
    d = os.path.join(IMG_DIR, slug)
    found, errors = {}, []
    for name in sorted(os.listdir(d)):
        m = re.fullmatch(r"(\d\d)\.([a-z]+)", name)
        if not m or m.group(2) not in EXTS:
            continue
        if m.group(1) in found:
            errors.append(f"{slug}/{m.group(1)}: два файла ({found[m.group(1)]}, {name})")
        found[m.group(1)] = name
    return found, errors


def load_meta(slug):
    p = os.path.join(IMG_DIR, slug, "meta.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def svg_text(root):
    return " ".join(t.strip() for el in root.iter() if el.tag in (SVG_NS + "text", SVG_NS + "tspan")
                    for t in [el.text or ""] if t.strip())


def check_svg(path, tag, q):
    errs = []
    size = os.path.getsize(path)
    if size > MAX_SVG:
        errs.append(f"{tag}: {size // 1024} КБ, предел {MAX_SVG // 1024} КБ")
    raw = open(path, encoding="utf-8").read()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return errs + [f"{tag}: SVG не разбирается: {e}"]
    if root.tag != SVG_NS + "svg":
        errs.append(f"{tag}: корень не <svg> с xmlns")
    vb = (root.get("viewBox") or "").split()
    if len(vb) != 4:
        errs.append(f"{tag}: нет viewBox")
    elif float(vb[2]) != 480 or not 240 <= float(vb[3]) <= 360:
        errs.append(f"{tag}: viewBox {' '.join(vb)}, нужно 480 × 240..360")
    kids = list(root)
    first = kids[0] if kids else None
    if first is None or first.tag != SVG_NS + "rect" or (first.get("fill") or "").lower() not in ("#ffffff", "#fff", "white"):
        errs.append(f"{tag}: первый элемент не белая подложка <rect fill=\"#ffffff\">")
    sizes = [el.get("font-size") for el in root.iter() if el.get("font-size")]
    sizes += re.findall(r"font-size\s*:\s*([\d.]+)", raw)
    small = sorted({x for x in sizes if re.fullmatch(r"[\d.]+(px)?", x) and float(x.rstrip("px")) < 16})
    if small:
        errs.append(f"{tag}: шрифт меньше 16 ({', '.join(small)}) — на телефоне не прочесть")
    thin = sorted({el.get("stroke-width") for el in root.iter()
                   if re.fullmatch(r"[\d.]+", el.get("stroke-width") or "x") and float(el.get("stroke-width")) < 1.5})
    if thin:
        errs.append(f"{tag}: линии тоньше 1.5 ({', '.join(thin)})")
    low = raw.lower()
    for bad in ("<script", "foreignobject", "onload=", "onclick="):
        if bad in low:
            errs.append(f"{tag}: запрещено {bad}")
    if re.search(r'(?:href|src)\s*=\s*["\'](?:https?:)?//', raw) or "@import" in low or "url(http" in low:
        errs.append(f"{tag}: внешняя ссылка — картинка должна работать офлайн")
    # Утечка ответа: правильный вариант целиком (после нормализации) написан на картинке.
    text = norm(svg_text(root))
    correct = norm(q["options"][q["correct"]])
    if text and len(correct) >= 12 and correct in text:
        errs.append(f"{tag}: на картинке написан правильный вариант целиком")
    return errs


def check(slugs):
    errors, total = [], 0
    for slug in slugs:
        questions = load_content(slug)
        files, errs = find_files(slug)
        errors += errs
        meta = load_meta(slug)
        for nn, name in files.items():
            idx = int(nn) - 1
            tag = f"{slug}/{name}"
            if not 0 <= idx < len(questions):
                errors.append(f"{tag}: вопроса {nn} нет")
                continue
            total += 1
            m = meta.get(nn) or {}
            if not (m.get("alt") or "").strip():
                errors.append(f"{tag}: нет alt в meta.json")
            path = os.path.join(IMG_DIR, slug, name)
            if name.endswith(".svg"):
                errors += check_svg(path, tag, questions[idx])
            else:
                if os.path.getsize(path) > MAX_RASTER:
                    errors.append(f"{tag}: {os.path.getsize(path) // 1024} КБ, предел {MAX_RASTER // 1024} КБ")
                if not (m.get("credit") or "").strip():
                    errors.append(f"{tag}: растровая картинка без credit — откуда она и под какой лицензией")
        missing = [f"{i + 1:02d}" for i in range(len(questions)) if f"{i + 1:02d}" not in files]
        print(f"{slug}: {len(files)}/{len(questions)} картинок" + (f", нет: {' '.join(missing)}" if missing else ""))
    for e in errors:
        print("  ОШИБКА", e)
    print(f"\nПроверено картинок: {total}, ошибок: {len(errors)}")
    return 1 if errors else 0


def attach(slugs):
    for slug in slugs:
        questions = load_content(slug)
        files, errs = find_files(slug)
        if errs:
            sys.exit("\n".join(errs))
        meta = load_meta(slug)
        n = 0
        for i, q in enumerate(questions):
            nn = f"{i + 1:02d}"
            if nn not in files:
                q.pop("img", None)
                continue
            m = meta.get(nn) or {}
            img = {"src": f"img/{slug}/{files[nn]}", "alt": (m.get("alt") or "").strip()}
            if (m.get("credit") or "").strip():
                img["credit"] = m["credit"].strip()
            q["img"] = img
            n += 1
        write_content(slug, questions)
        print(f"{slug}: привязано {n}/{len(questions)}")


def sheet(slug, per_page=10):
    questions = load_content(slug)
    files, _ = find_files(slug)
    out_dir = os.path.join(tempfile.gettempdir(), "lt-sheets", slug)
    os.makedirs(out_dir, exist_ok=True)
    nns = sorted(files)
    pngs = []
    for p in range(0, len(nns), per_page):
        cells = []
        for nn in nns[p:p + per_page]:
            q = questions[int(nn) - 1]
            src = "file:///" + os.path.join(IMG_DIR, slug, files[nn]).replace("\\", "/")
            cells.append(f'<div class="c"><div class="t"><b>{nn}.</b> {html.escape(q["q"][:260])}</div>'
                         f'<div class="ph"><img src="{src}"></div></div>')
        page = ('<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:12px;background:#1b1e27;'
                'font:14px system-ui;color:#e8e9ef}.g{display:grid;grid-template-columns:1fr 1fr;gap:12px}'
                '.c{background:#232734;border-radius:10px;padding:10px}.t{margin-bottom:8px;line-height:1.3}'
                '.ph{width:360px}.ph img{width:360px;display:block;border-radius:8px}</style>'
                '<div class="g">' + "".join(cells) + "</div>")
        hp = os.path.join(out_dir, f"sheet_{p // per_page + 1}.html")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(page)
        png = hp[:-5] + ".png"
        subprocess.run(["node", os.path.join(HERE, "sheet_shot.js"), hp, png, "800"], check=True)
        pngs.append(png)
    print("\n".join(pngs))
    print("Ширина картинки на листе 360 px — примерно как на телефоне.")


def frames(slug):
    """Анимированные SVG, остановленные на 0, 1/4, 1/2, 3/4 цикла, — один PNG-лист."""
    d = os.path.join(IMG_DIR, slug)
    rows = []
    for name in sorted(os.listdir(d)):
        if not name.endswith(".svg"):
            continue
        svg = open(os.path.join(d, name), encoding="utf-8").read()
        if not re.search(r"<animate|@keyframes", svg):
            continue
        durs = [float(x) * (0.001 if u == "ms" else 1) for x, u in re.findall(r'dur="([\d.]+)(m?s)"', svg)]
        durs += [float(x) for x in re.findall(r"animation[^;\"]*?([\d.]+)s", svg)]
        loop = max(durs) if durs else 4.0
        cells = [f'<div class="lab">{name[:2]}<br>{loop:g} с</div>']
        for k in range(4):
            t = loop * k / 4
            cells.append(f'<div class="c" data-t="{t:.3f}">{svg}<div class="t">t = {t:.2f} с</div></div>')
        rows.append('<div class="r">' + "".join(cells) + "</div>")
    if not rows:
        print("анимированных нет")
        return
    page = ('<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:8px;background:#1b1e27;color:#ddd;'
            'font:13px system-ui}.r{display:flex;gap:6px;align-items:flex-start;margin-bottom:8px}.lab{width:44px}'
            '.c{width:220px}.c svg{width:220px;display:block}.t{font-size:11px}</style>' + "".join(rows) +
            '<script>document.querySelectorAll(".c").forEach(c=>{const s=c.querySelector("svg");'
            's.pauseAnimations();s.setCurrentTime(+c.dataset.t);'
            's.getAnimations&&s.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=1000*c.dataset.t;});});</script>')
    out_dir = os.path.join(tempfile.gettempdir(), "lt-sheets", slug)
    os.makedirs(out_dir, exist_ok=True)
    hp = os.path.join(out_dir, "frames.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(page)
    png = hp[:-5] + ".png"
    subprocess.run(["node", os.path.join(HERE, "sheet_shot.js"), hp, png, "960"], check=True)
    print(png)
    print("Кадры анимаций на 0, 1/4, 1/2, 3/4 цикла: движение должно быть видно и не выдавать ответ.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "attach", "sheet", "frames"):
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd in ("sheet", "frames"):
        if len(args) != 1:
            sys.exit(cmd + " <slug>")
        return sheet(args[0]) if cmd == "sheet" else frames(args[0])
    slugs = args or slugs_with_images()
    if cmd == "check":
        sys.exit(check(slugs))
    attach(slugs)


if __name__ == "__main__":
    main()
