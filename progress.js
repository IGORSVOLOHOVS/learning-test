// Общая логика прогресса: главная (index.html), страницы тестов (tests/*.html)
// и node-проверка (scripts/test_progress.js) считают одно и то же одними и теми
// же функциями — иначе группа на главной и подпись в тесте однажды разойдутся.
//
// Состояние теста в localStorage["learntest_<slug>"] (и в Drive тем же JSON):
//   current   — номер текущего вопроса (0..50)
//   answers   — {i: {selectedText, correct}} — первый ответ на каждый вопрос
//   updatedAt — когда состояние менялось последний раз (мс); по нему синхронизация
//               решает, какая копия свежее. У старого прогресса поля нет.
//   doneAt    — когда тест впервые пройден до конца (мс)
//   fixed     — {i: мс} — ошибки, исправленные в «Работе над ошибками». Счёт теста
//               (answers) при этом не меняется: исправление — отдельный факт.
//   review    — {count, dueAt, last: {at, correct, total}} — интервальное повторение
(function (root) {
  var TOTAL = 50;
  var DAY = 24 * 3600 * 1000;
  // Через сколько дней повторять: после прохождения — 3, потом 7, потом 30 и дальше
  // раз в 30. Повторение хуже PASS_SHARE возвращает к первому интервалу.
  var INTERVALS_DAYS = [3, 7, 30];
  var PASS_SHARE = 0.7;
  var REVIEW_SIZE = 10;

  function answeredCount(state) {
    return state && state.answers ? Object.keys(state.answers).length : 0;
  }

  // Пройден — если дошёл до конца ИЛИ ответил на все вопросы. Второе нужно потому,
  // что «Пересмотреть ответы» возвращает current к 0, и раньше пройденный тест
  // после просмотра ответов снова числился начатым.
  function isDone(state) {
    if (!state) return false;
    return (state.current || 0) >= TOTAL || answeredCount(state) >= TOTAL;
  }

  function status(state) {
    if (isDone(state)) return "done";
    return answeredCount(state) > 0 ? "progress" : "todo";
  }

  function correctCount(state) {
    var n = 0;
    if (state && state.answers) {
      Object.keys(state.answers).forEach(function (k) { if (state.answers[k] && state.answers[k].correct) n++; });
    }
    return n;
  }

  // Индексы вопросов с неисправленной ошибкой, по возрастанию.
  function mistakes(state) {
    var out = [];
    if (!state || !state.answers) return out;
    var fixed = state.fixed || {};
    Object.keys(state.answers).forEach(function (k) {
      var a = state.answers[k];
      if (a && a.correct === false && !fixed[k]) out.push(parseInt(k, 10));
    });
    return out.sort(function (a, b) { return a - b; });
  }

  // Когда пора повторять пройденный тест: число (мс), 0 — «уже пора, дата
  // прохождения неизвестна» (прогресс записан до появления doneAt), null — не пройден.
  function reviewDue(state) {
    if (!isDone(state)) return null;
    if (state.review && typeof state.review.dueAt === "number") return state.review.dueAt;
    if (typeof state.doneAt === "number") return state.doneAt + INTERVALS_DAYS[0] * DAY;
    return 0;
  }

  function isReviewDue(state, now) {
    var due = reviewDue(state);
    return due !== null && due <= now;
  }

  // Записать итог повторения и назначить следующее. Возвращает новый review.
  function nextReview(state, correct, total, now) {
    var prev = (state && state.review) || {};
    var passed = total > 0 && correct / total >= PASS_SHARE;
    var count = passed ? (prev.count || 0) + 1 : 0;
    var days = INTERVALS_DAYS[Math.min(count, INTERVALS_DAYS.length - 1)];
    return { count: count, dueAt: now + days * DAY, last: { at: now, correct: correct, total: total } };
  }

  // Какая копия свежее: "local", "remote" или "same". Сначала по updatedAt; у
  // старого прогресса его нет, тогда по объёму — больше отвеченных значит дальше;
  // при равенстве оставляем локальную: молча перезаписать то, что на экране,
  // хуже, чем отправить её ещё раз.
  function pickNewer(local, remote) {
    if (!remote) return "local";
    if (!local) return "remote";
    var lt = local.updatedAt || 0, rt = remote.updatedAt || 0;
    if (lt !== rt) return lt > rt ? "local" : "remote";
    var la = answeredCount(local), ra = answeredCount(remote);
    if (la !== ra) return la > ra ? "local" : "remote";
    return JSON.stringify(local) === JSON.stringify(remote) ? "same" : "local";
  }

  // «TSI DSP 3: Инверсия…» → "TSI DSP"; «TSI IS1: Нейронные сети» → "TSI IS1";
  // не курс TSI → null.
  function courseOf(title) {
    var m = /^(TSI [^\s:]+)(?:\s+\d+)?:/.exec(title || "");
    return m ? m[1] : null;
  }

  var api = {
    TOTAL: TOTAL, DAY: DAY, INTERVALS_DAYS: INTERVALS_DAYS, PASS_SHARE: PASS_SHARE, REVIEW_SIZE: REVIEW_SIZE,
    answeredCount: answeredCount, isDone: isDone, status: status, correctCount: correctCount,
    mistakes: mistakes, reviewDue: reviewDue, isReviewDue: isReviewDue, nextReview: nextReview,
    pickNewer: pickNewer, courseOf: courseOf
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LTProgress = api;
})(typeof window !== "undefined" ? window : this);
