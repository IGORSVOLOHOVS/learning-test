// Снимок страницы через headless Chrome (CDP), для контактных листов картинок.
// node scripts/sheet_shot.js <file-or-url> <out.png> [width] [js-выражение перед снимком]
// Порт и профиль свои на каждый запуск: несколько агентов могут снимать одновременно.
const { spawn, execSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const CHROME = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const [target, out, widthArg, setup] = process.argv.slice(2);
const width = +(widthArg || 1000);
const url = /^[a-z]+:\/\//i.test(target) ? target : "file:///" + path.resolve(target).replace(/\\/g, "/");
const port = 9400 + Math.floor(Math.random() * 500);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "lt-shot-"));

const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
  "--allow-file-access-from-files", "--remote-debugging-port=" + port, "--user-data-dir=" + profile,
  "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let browserWs = null;
// Chrome на Windows отцепляет дочерние процессы от того, что запустил spawn:
// taskkill /T по chrome.pid их не находит, и за ночь прогонов осталось 278
// живых headless-процессов. Поэтому: Browser.close по CDP, затем добивание
// всех процессов с нашим профилем в командной строке, затем удаление профиля.
async function done(code) {
  if (browserWs) {
    try {
      const b = new WebSocket(browserWs);
      await new Promise((r, j) => { b.addEventListener("open", r); b.addEventListener("error", j); });
      b.send(JSON.stringify({ id: 1, method: "Browser.close" }));
      await sleep(700);
    } catch (e) {}
  }
  try { execSync("taskkill /PID " + chrome.pid + " /T /F", { stdio: "ignore" }); } catch (e) {}
  try {
    execSync(`powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"name='chrome.exe'\\" | ` +
      `Where-Object { $_.CommandLine -like '*${path.basename(profile)}*' } | ` +
      `ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"`,
      { stdio: "ignore", timeout: 30000 });
  } catch (e) {}
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) {}
  process.exit(code);
}
setTimeout(() => { console.error("timeout"); done(2); }, 60000);

(async () => {
  for (let i = 0; i < 80; i++) {
    try { browserWs = (await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl; break; }
    catch (e) { await sleep(250); }
  }
  const t = await (await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  const send = (method, params = {}) => new Promise((res) => {
    const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
  });
  await new Promise((r) => ws.addEventListener("open", r));
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
  });
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Page.reload");
  await sleep(2500);
  if (setup) {
    await send("Runtime.evaluate", { expression: setup, awaitPromise: true });
    await sleep(800);
  }
  const lm = await send("Page.getLayoutMetrics");
  const h = Math.ceil((lm.cssContentSize || lm.contentSize).height);
  const shot = await send("Page.captureScreenshot", {
    format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width, height: h, scale: 1 },
  });
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log("wrote " + out + " " + width + "x" + h);
  ws.close(); done(0);
})().catch((e) => { console.error(e); done(1); });
