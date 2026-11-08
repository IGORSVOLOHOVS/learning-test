// Проверка формул: каждый фрагмент \( ... \) и \[ ... \] в контенте должен
// разбираться KaTeX без ошибок. На странице KaTeX ошибку не роняет, а рисует
// исходник красным — глазами такое легко пропустить на сорок девятом вопросе.
//   node scripts/check_math.js            # все тесты
//   node scripts/check_math.js <slug>...  # только указанные
const fs = require("fs");
const path = require("path");
const katex = require("../vendor/katex/katex.min.js");

const dir = path.join(__dirname, "content");
const slugs = process.argv.slice(2).length ? process.argv.slice(2)
  : fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));

const RE = /\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]/g;
let total = 0, bad = 0;
for (const slug of slugs) {
  const qs = JSON.parse(fs.readFileSync(path.join(dir, slug + ".json"), "utf8"));
  let n = 0;
  qs.forEach((q, i) => {
    const u = q.usage || {};
    const fields = { q: q.q, explain: q.explain };
    q.options.forEach((o, j) => { fields["option" + j] = o; });
    if (!u.code) for (const k of ["without", "with", "benefit"]) fields["usage." + k] = u[k];
    for (const [name, text] of Object.entries(fields)) {
      if (!text) continue;
      // Код в ``` ``` не рендерится, его не проверяем.
      const plain = String(text).split("```").filter((_, k) => k % 2 === 0).join(" ");
      for (const m of plain.matchAll(RE)) {
        const tex = m[1] !== undefined ? m[1] : m[2];
        n++;
        try {
          katex.renderToString(tex, { throwOnError: true, displayMode: m[2] !== undefined, strict: "ignore" });
        } catch (e) {
          bad++;
          console.log(`  ОШИБКА ${slug} #${i + 1} ${name}: ${e.message.split("\n")[0]}\n         ${tex}`);
        }
      }
    }
  });
  total += n;
  if (n) console.log(`${slug}: формул ${n}`);
}
console.log(`\nФормул проверено: ${total}, с ошибками: ${bad}`);
process.exit(bad ? 1 : 0);
