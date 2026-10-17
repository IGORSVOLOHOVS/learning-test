// Общая синхронизация прогресса всех тестов с Google Drive.
// Подключается и на главной (index.html), и на страницах тестов (tests/*.html).
//
// Что решает:
//  1. Синхронизирует ВСЕ тесты сразу (все ключи localStorage вида learntest_*),
//     а не по одному.
//  2. Не заставляет проходить авторизацию каждый раз: access-token и его срок
//     кэшируются в localStorage и переиспользуются, пока не истекли (~1 час).
//     При обновлении токена сначала пробуется «тихий» запрос без экрана согласия.
//
// Формат хранения на Drive не меняется: один файл на тест — learntest_<id>.json,
// содержимое совпадает с localStorage["learntest_<id>"].
//
//  3. syncAll — слияние по свежести (updatedAt, см. progress.js): само на главной,
//     пока токен жив, и по кнопке. uploadOne — тихая отправка одного теста после
//     ответа. Без живого токена (Google даёт его на ~час) автоматика молчит, а не
//     открывает окно входа: всплывающее окно без касания браузер всё равно режет.
(function () {
  var TOKEN_KEY = "gdrive_access_token";
  var TOKEN_EXP_KEY = "gdrive_token_expiry";
  var PROGRESS_PREFIX = "learntest_";
  var SCOPE = "https://www.googleapis.com/auth/drive.file";
  var tokenClient = null;

  function configured() {
    return typeof window.GOOGLE_CLIENT_ID === "string" && window.GOOGLE_CLIENT_ID.length > 0;
  }

  function cachedToken() {
    try {
      var t = localStorage.getItem(TOKEN_KEY);
      var exp = parseInt(localStorage.getItem(TOKEN_EXP_KEY) || "0", 10);
      // запас 2 минуты, чтобы токен не истёк посреди операции
      if (t && exp > Date.now() + 120000) return t;
    } catch (e) {}
    return null;
  }

  function storeToken(token, expiresInSec) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + (expiresInSec || 3600) * 1000));
    } catch (e) {}
  }

  function signOut() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXP_KEY);
    } catch (e) {}
  }

  function ensureGis(cb, onErr) {
    if (window.google && window.google.accounts && window.google.accounts.oauth2) { cb(); return; }
    var s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.onload = cb;
    s.onerror = function () { onErr("Не удалось загрузить Google Identity Services (нет интернета?)"); };
    document.head.appendChild(s);
  }

  // Получить токен: сначала из кэша, иначе тихо, иначе с экраном согласия.
  function getToken(cb, onErr) {
    var cached = cachedToken();
    if (cached) { cb(cached); return; }
    if (!configured()) { onErr("Синхронизация не настроена: укажите GOOGLE_CLIENT_ID в config.js"); return; }
    ensureGis(function () {
      if (!tokenClient) {
        tokenClient = google.accounts.oauth2.initTokenClient({
          client_id: window.GOOGLE_CLIENT_ID,
          scope: SCOPE,
          callback: function () {}
        });
      }
      var triedConsent = false;
      tokenClient.callback = function (resp) {
        if (resp && resp.access_token) {
          storeToken(resp.access_token, parseInt(resp.expires_in || "3600", 10));
          cb(resp.access_token);
          return;
        }
        // Тихий запрос не удался — один раз показываем экран согласия.
        if (!triedConsent) {
          triedConsent = true;
          tokenClient.requestAccessToken({ prompt: "consent" });
          return;
        }
        onErr("Ошибка авторизации: " + ((resp && resp.error) || "неизвестно"));
      };
      // Тихая попытка: если доступ уже выдан — вернётся токен без окна согласия.
      tokenClient.requestAccessToken({ prompt: "" });
    }, onErr);
  }

  function authHeader(token) { return { Authorization: "Bearer " + token }; }

  function findFile(token, filename, cb) {
    var q = "name='" + filename + "' and trashed=false";
    fetch("https://www.googleapis.com/drive/v3/files?q=" + encodeURIComponent(q) + "&spaces=drive&fields=files(id,name)", { headers: authHeader(token) })
      .then(function (r) { return r.json(); })
      .then(function (d) { cb((d.files && d.files[0]) || null); })
      .catch(function () { cb(null); });
  }

  function listProgressFiles(token, cb) {
    var q = "name contains '" + PROGRESS_PREFIX + "' and trashed=false";
    fetch("https://www.googleapis.com/drive/v3/files?q=" + encodeURIComponent(q) + "&spaces=drive&fields=files(id,name)&pageSize=1000", { headers: authHeader(token) })
      .then(function (r) { return r.json(); })
      .then(function (d) { cb(d.files || []); })
      .catch(function () { cb([]); });
  }

  // Как listProgressFiles, но сбой — это null, а не пустой список. Иначе слияние
  // приняло бы «Drive не ответил» за «в Drive ничего нет» и залило бы всё заново,
  // а uploadFile без найденного файла создаёт ещё один с тем же именем.
  function listProgressFilesStrict(token, cb) {
    var q = "name contains '" + PROGRESS_PREFIX + "' and trashed=false";
    fetch("https://www.googleapis.com/drive/v3/files?q=" + encodeURIComponent(q) + "&spaces=drive&fields=files(id,name)&pageSize=1000", { headers: authHeader(token) })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) { cb(d.files || []); })
      .catch(function () { cb(null); });
  }

  function uploadFile(token, filename, contentObj, cb) {
    findFile(token, filename, function (file) {
      var metadata = { name: filename, mimeType: "application/json" };
      var boundary = "-------314159265358979323846";
      var body =
        "--" + boundary + "\r\nContent-Type: application/json\r\n\r\n" + JSON.stringify(metadata) +
        "\r\n--" + boundary + "\r\nContent-Type: application/json\r\n\r\n" + JSON.stringify(contentObj) +
        "\r\n--" + boundary + "--";
      var url = file
        ? "https://www.googleapis.com/upload/drive/v3/files/" + file.id + "?uploadType=multipart"
        : "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart";
      fetch(url, {
        method: file ? "PATCH" : "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "multipart/related; boundary=" + boundary },
        body: body
      }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        cb(null);
      }).catch(function (e) { cb(e); });
    });
  }

  function localProgressKeys() {
    var keys = [];
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && k.indexOf(PROGRESS_PREFIX) === 0) keys.push(k);
    }
    return keys;
  }

  // Отправить прогресс всех тестов в Drive.
  // cbs: { onProgress(done,total), onDone(ok,failed), onError(msg) }
  function uploadAll(cbs) {
    cbs = cbs || {};
    getToken(function (token) {
      var keys = localProgressKeys();
      if (!keys.length) { cbs.onDone && cbs.onDone(0, 0); return; }
      var done = 0, failed = 0;
      keys.forEach(function (k) {
        var val = null;
        try { val = JSON.parse(localStorage.getItem(k)); } catch (e) {}
        if (val == null) { step(true); return; }
        uploadFile(token, k + ".json", val, function (err) { step(!err); });
      });
      function step(ok) {
        done++;
        if (!ok) failed++;
        cbs.onProgress && cbs.onProgress(done, keys.length);
        if (done === keys.length) cbs.onDone && cbs.onDone(done - failed, failed);
      }
    }, cbs.onError || function () {});
  }

  // Загрузить прогресс всех тестов из Drive в localStorage.
  // cbs: { onProgress(done,total), onDone(ok,failed), onError(msg) }
  function downloadAll(cbs) {
    cbs = cbs || {};
    getToken(function (token) {
      listProgressFiles(token, function (files) {
        var progress = files.filter(function (f) { return /^learntest_.+\.json$/.test(f.name); });
        if (!progress.length) { cbs.onDone && cbs.onDone(0, 0); return; }
        var done = 0, failed = 0;
        progress.forEach(function (f) {
          fetch("https://www.googleapis.com/drive/v3/files/" + f.id + "?alt=media", { headers: authHeader(token) })
            .then(function (r) { return r.json(); })
            .then(function (remote) {
              var key = f.name.replace(/\.json$/, "");
              try { localStorage.setItem(key, JSON.stringify(remote)); } catch (e) {}
              step(true);
            })
            .catch(function () { step(false); });
        });
        function step(ok) {
          done++;
          if (!ok) failed++;
          cbs.onProgress && cbs.onProgress(done, progress.length);
          if (done === progress.length) cbs.onDone && cbs.onDone(done - failed, failed);
        }
      });
    }, cbs.onError || function () {});
  }

  // Слияние вместо «отправить всё» / «заменить всё»: по каждому тесту побеждает
  // более свежая копия (LTProgress.pickNewer), отстающая сторона обновляется.
  // cbs: { interactive, onDone({pulled, pushed, same, failed}), onError(msg) }
  // interactive=false — только с уже выданным токеном, без окна входа: так
  // вызывают автоматически, а всплывающее окно без касания браузер заблокирует.
  function syncAll(cbs) {
    cbs = cbs || {};
    var fail = cbs.onError || function () {};
    function start(token) {
      listProgressFilesStrict(token, function (files) {
        if (files === null) { fail("Drive не ответил — синхронизация отложена"); return; }
        var remote = {};
        files.forEach(function (f) {
          if (/^learntest_.+\.json$/.test(f.name)) remote[f.name.replace(/\.json$/, "")] = f;
        });
        var keys = Object.keys(remote);
        localProgressKeys().forEach(function (k) { if (!remote[k]) keys.push(k); });
        var stats = { pulled: 0, pushed: 0, same: 0, failed: 0 };
        var left = keys.length;
        if (!left) { cbs.onDone && cbs.onDone(stats); return; }
        function step() { if (--left === 0) cbs.onDone && cbs.onDone(stats); }
        function push(key, val) {
          if (val == null) { step(); return; }
          uploadFile(token, key + ".json", val, function (err) { if (err) stats.failed++; else stats.pushed++; step(); });
        }
        keys.forEach(function (key) {
          var local = null;
          try { local = JSON.parse(localStorage.getItem(key)); } catch (e) {}
          if (!remote[key]) { push(key, local); return; }
          fetch("https://www.googleapis.com/drive/v3/files/" + remote[key].id + "?alt=media", { headers: authHeader(token) })
            .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
            .then(function (theirs) {
              var winner = window.LTProgress ? LTProgress.pickNewer(local, theirs) : "same";
              if (winner === "remote") {
                try { localStorage.setItem(key, JSON.stringify(theirs)); stats.pulled++; } catch (e) { stats.failed++; }
                step();
              } else if (winner === "local") {
                push(key, local);
              } else {
                stats.same++;
                step();
              }
            })
            .catch(function () { stats.failed++; step(); });
        });
      });
    }
    if (cbs.interactive) { getToken(start, fail); return; }
    var token = cachedToken();
    if (!token) { fail("no-token"); return; }
    start(token);
  }

  // Отправить один тест — только с уже выданным токеном, молча. Для автоотправки
  // со страницы теста; без токена ничего не делает и говорит об этом колбэком.
  function uploadOne(key, cb) {
    cb = cb || function () {};
    var token = cachedToken();
    if (!token) { cb("no-token"); return; }
    var val = null;
    try { val = JSON.parse(localStorage.getItem(key)); } catch (e) {}
    if (val == null) { cb(null); return; }
    uploadFile(token, key + ".json", val, function (err) { cb(err ? String(err.message || err) : null); });
  }

  window.LTSync = {
    configured: configured,
    hasToken: function () { return !!cachedToken(); },
    uploadAll: uploadAll,
    downloadAll: downloadAll,
    syncAll: syncAll,
    uploadOne: uploadOne,
    signOut: signOut
  };
})();
