// Проверка progress.js и слияния в sync.js без браузера и без Google:
//   node scripts/test_progress.js
// Слияние гоняется на заглушке Drive: что свежее побеждает, что отстающая
// сторона обновляется и что сбой Drive не превращается в «там пусто» и не
// заливает всё заново дубликатами.
"use strict";
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const ROOT = path.resolve(__dirname, "..");
const P = require(path.join(ROOT, "progress.js"));
let failures = 0;
function check(name, fn) {
  try { fn(); console.log("ok   " + name); }
  catch (e) { failures++; console.log("FAIL " + name + "\n     " + e.message); }
}
function answers(n, wrong) {
  const a = {};
  for (let i = 0; i < n; i++) a[i] = { selectedText: "x", correct: !(wrong || []).includes(i) };
  return a;
}

check("done: reached the end, or answered everything after «Пересмотреть ответы»", () => {
  assert.strictEqual(P.isDone({ current: 50, answers: answers(50) }), true);
  assert.strictEqual(P.isDone({ current: 0, answers: answers(50) }), true);
  assert.strictEqual(P.isDone({ current: 12, answers: answers(12) }), false);
  assert.strictEqual(P.isDone(null), false);
  assert.strictEqual(P.status(null), "todo");
  assert.strictEqual(P.status({ current: 3, answers: answers(3) }), "progress");
});

check("mistakes: first-attempt errors minus the fixed ones", () => {
  const s = { current: 50, answers: answers(50, [2, 7, 30]), fixed: { 7: 1 } };
  assert.deepStrictEqual(P.mistakes(s), [2, 30]);
  assert.strictEqual(P.correctCount(s), 47);   // fixing does not rewrite the score
});

check("the removed «Пора повторить» left nothing behind in the shared logic", () => {
  for (const name of ["reviewDue", "isReviewDue", "nextReview", "REVIEW_SIZE", "INTERVALS_DAYS"]) {
    assert.strictEqual(P[name], undefined, name);
  }
  // old progress may still carry its fields; they change nothing
  const s = { current: 50, answers: answers(50, [3]), doneAt: 1, review: { count: 2, dueAt: 5 } };
  assert.strictEqual(P.status(s), "done");
  assert.deepStrictEqual(P.mistakes(s), [3]);
});

check("pickNewer: updatedAt wins; old progress without it — more answers wins", () => {
  assert.strictEqual(P.pickNewer({ updatedAt: 5 }, { updatedAt: 9 }), "remote");
  assert.strictEqual(P.pickNewer({ updatedAt: 9 }, { updatedAt: 5 }), "local");
  assert.strictEqual(P.pickNewer({ answers: answers(3) }, { answers: answers(10) }), "remote");
  assert.strictEqual(P.pickNewer({ answers: answers(10) }, { answers: answers(3) }), "local");
  assert.strictEqual(P.pickNewer({ current: 1, answers: answers(1) }, { current: 1, answers: answers(1) }), "same");
  assert.strictEqual(P.pickNewer(null, { current: 1 }), "remote");
  assert.strictEqual(P.pickNewer({ current: 1 }, null), "local");
});

check("courseOf: TSI course prefixes, nothing else", () => {
  assert.strictEqual(P.courseOf("TSI DSP 3: Инверсия и эквализация"), "TSI DSP");
  assert.strictEqual(P.courseOf("TSI Math 9: Функции нескольких переменных"), "TSI Math");
  assert.strictEqual(P.courseOf("TSI IS1: Нейронные сети"), "TSI IS1");
  assert.strictEqual(P.courseOf("TSI RMO: Моделирование роботов"), "TSI RMO");
  assert.strictEqual(P.courseOf("Git и патчи: format-patch, am, rebase"), null);
});

// ---- sync.js on a fake Drive ----
function loadSync(drive, { token = true, listFails = false } = {}) {
  const store = new Map();
  const localStorage = {
    get length() { return store.size; },
    key: (i) => Array.from(store.keys())[i],
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  if (token) {
    localStorage.setItem("gdrive_access_token", "t");
    localStorage.setItem("gdrive_token_expiry", String(Date.now() + 3600 * 1000));
  }
  const uploads = [];
  const fetch = async (url, opts) => {
    opts = opts || {};
    const ok = (body) => ({ ok: true, status: 200, json: async () => body });
    if (url.includes("/drive/v3/files?q=")) {
      if (listFails) return { ok: false, status: 401, json: async () => ({ error: "x" }) };
      const q = decodeURIComponent(url.split("q=")[1].split("&")[0]);
      const exact = /name='([^']+)'/.exec(q);
      const files = Object.keys(drive).map((name) => ({ id: "id_" + name, name }));
      return ok({ files: exact ? files.filter((f) => f.name === exact[1]) : files });
    }
    if (url.includes("?alt=media")) {
      const name = url.split("/files/")[1].split("?")[0].replace(/^id_/, "");
      return ok(drive[name]);
    }
    if (url.includes("/upload/drive/v3/files")) {
      const body = String(opts.body);
      const name = /"name":"([^"]+)"/.exec(body)[1];
      const json = body.split("\r\n\r\n")[2].split("\r\n--")[0];
      uploads.push({ name, method: opts.method, content: JSON.parse(json) });
      drive[name] = JSON.parse(json);
      return ok({});
    }
    throw new Error("unexpected " + url);
  };
  const window = { LTProgress: P };
  new Function("window", "localStorage", "fetch", "LTProgress", "document",
    fs.readFileSync(path.join(ROOT, "sync.js"), "utf8"))(window, localStorage, fetch, P, {});
  return { LTSync: window.LTSync, localStorage, uploads, drive };
}
function sync(env, opts) {
  return new Promise((resolve) => env.LTSync.syncAll(Object.assign({
    onDone: (s) => resolve({ stats: s }), onError: (m) => resolve({ error: m }),
  }, opts || {})));
}

const asyncChecks = [];
function acheck(name, fn) { asyncChecks.push([name, fn]); }

acheck("merge: the fresher copy wins on each side", async () => {
  const drive = {
    "learntest_a.json": { current: 9, answers: answers(9), updatedAt: 200 },   // remote newer
    "learntest_b.json": { current: 2, answers: answers(2), updatedAt: 100 },   // local newer
  };
  const env = loadSync(drive);
  env.localStorage.setItem("learntest_a", JSON.stringify({ current: 4, answers: answers(4), updatedAt: 150 }));
  env.localStorage.setItem("learntest_b", JSON.stringify({ current: 7, answers: answers(7), updatedAt: 300 }));
  env.localStorage.setItem("learntest_c", JSON.stringify({ current: 1, answers: answers(1), updatedAt: 50 })); // not on Drive
  const r = await sync(env);
  assert.ok(r.stats, r.error);
  assert.deepStrictEqual(r.stats, { pulled: 1, pushed: 2, same: 0, failed: 0 });
  assert.strictEqual(JSON.parse(env.localStorage.getItem("learntest_a")).current, 9);
  assert.strictEqual(drive["learntest_b.json"].current, 7);
  assert.strictEqual(drive["learntest_c.json"].current, 1);
  assert.ok(env.uploads.every((u) => !(u.name === "learntest_b.json" && u.method === "POST")), "existing file must be PATCHed, not duplicated");
});

acheck("merge: Drive not answering is an error, not «Drive is empty»", async () => {
  const env = loadSync({ "learntest_a.json": { updatedAt: 1 } }, { listFails: true });
  env.localStorage.setItem("learntest_a", JSON.stringify({ current: 1, answers: answers(1), updatedAt: 5 }));
  const r = await sync(env);
  assert.ok(r.error && /не ответил/.test(r.error), "expected an error, got " + JSON.stringify(r));
  assert.strictEqual(env.uploads.length, 0, "nothing may be uploaded on a failed listing");
});

acheck("auto mode never asks for a login: no token means it says so", async () => {
  const env = loadSync({}, { token: false });
  const r = await sync(env, { interactive: false });
  assert.strictEqual(r.error, "no-token");
});

acheck("uploadOne: quiet, one test, only with a live token", async () => {
  const drive = {};
  const env = loadSync(drive);
  env.localStorage.setItem("learntest_z", JSON.stringify({ current: 3, updatedAt: 7 }));
  const err = await new Promise((res) => env.LTSync.uploadOne("learntest_z", res));
  assert.strictEqual(err, null);
  assert.strictEqual(drive["learntest_z.json"].current, 3);
  const none = loadSync({}, { token: false });
  const err2 = await new Promise((res) => none.LTSync.uploadOne("learntest_z", res));
  assert.strictEqual(err2, "no-token");
});

(async () => {
  for (const [name, fn] of asyncChecks) {
    try { await fn(); console.log("ok   " + name); }
    catch (e) { failures++; console.log("FAIL " + name + "\n     " + e.message); }
  }
  console.log(failures ? "\n" + failures + " FAILED" : "\nALL CHECKS PASSED");
  process.exit(failures ? 1 : 0);
})();
