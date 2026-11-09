"""Листы предпросмотра формул: вопросы теста, где есть LaTeX, с вариантами и
объяснением, отрисованные KaTeX'ом в ширину телефона.

    python scripts/math_sheet.py <slug> [--all]

Без --all — только вопросы с формулами. Печатает пути PNG (по 5 вопросов на
лист); правильный вариант помечен ✓, чтобы видеть, не отличается ли он
оформлением от остальных.
"""

import html
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import images  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MATH = re.compile(r"\\[(\[]")


def esc(s):
    return html.escape(s or "", quote=False).replace("\n", "<br>")


def has_math(q):
    u = q.get("usage") or {}
    texts = [q["q"], q.get("explain", "")] + q["options"]
    if not u.get("code"):
        texts += [u.get("without", ""), u.get("with", ""), u.get("benefit", "")]
    return any(MATH.search(t or "") for t in texts)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    slug, show_all = sys.argv[1], "--all" in sys.argv
    qs = images.load_content(slug)
    idx = [i for i, q in enumerate(qs) if show_all or has_math(q)]
    if not idx:
        print("формул нет")
        return
    kdir = "file:///" + os.path.join(ROOT, "vendor", "katex").replace("\\", "/")
    out_dir = os.path.join(tempfile.gettempdir(), "lt-sheets", slug)
    os.makedirs(out_dir, exist_ok=True)
    pngs = []
    for p in range(0, len(idx), 5):
        cards = []
        for i in idx[p:p + 5]:
            q = qs[i]
            opts = "".join(f'<div class="o{" c" if j == q["correct"] else ""}">{"✓ " if j == q["correct"] else ""}{esc(o)}</div>'
                           for j, o in enumerate(q["options"]))
            u = q.get("usage") or {}
            usage = "" if u.get("code") else "".join(
                f'<div class="u">{esc(u.get(k))}</div>' for k in ("without", "with", "benefit") if u.get(k))
            cards.append(f'<div class="card"><div class="n">#{i + 1}</div><div class="q">{esc(q["q"])}</div>'
                         f'{opts}<div class="e">{esc(q.get("explain"))}</div>{usage}</div>')
        page = (f'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="{kdir}/katex.min.css">'
                f'<script src="{kdir}/katex.min.js"></script><script src="{kdir}/auto-render.min.js"></script>'
                '<style>body{margin:0;padding:10px;background:#f4f5f9;font:16px system-ui;color:#1f2430}'
                '.card{background:#fff;border-radius:12px;padding:12px;margin-bottom:10px}.n{color:#8a90a2;font-size:13px}'
                '.q{margin:4px 0 8px;white-space:pre-wrap}.o{border:1px solid #dde;border-radius:8px;padding:6px 8px;margin:4px 0}'
                '.o.c{border-color:#2a9d63}.e,.u{font-size:14px;color:#444;background:#f0f2fa;border-radius:8px;padding:6px 8px;margin-top:6px;white-space:pre-wrap}'
                '.katex{font-size:1.08em}.katex-display{overflow-x:auto;overflow-y:hidden}</style>'
                + "".join(cards) +
                '<script>renderMathInElement(document.body,{delimiters:[{left:"\\\\(",right:"\\\\)",display:false},'
                '{left:"\\\\[",right:"\\\\]",display:true}],throwOnError:false});</script>')
        hp = os.path.join(out_dir, f"math_{p // 5 + 1}.html")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(page)
        png = hp[:-5] + ".png"
        subprocess.run(["node", os.path.join(HERE, "sheet_shot.js"), hp, png, "420"], check=True,
                       stdout=subprocess.DEVNULL)
        pngs.append(png)
    print(f"вопросов с формулами: {len(idx)}")
    print("\n".join(pngs))


if __name__ == "__main__":
    main()
