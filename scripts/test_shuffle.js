// Verification script for the answer-shuffling fix in template.html.
// Extracts the actual `shuffle` and `buildShuffledQuestions` functions from
// the template's source (not a reimplementation) and exercises them.
//
// Run with: node scripts/test_shuffle.js

const fs = require("fs");
const path = require("path");

const templatePath = path.join(__dirname, "template.html");
const src = fs.readFileSync(templatePath, "utf-8");

const startMarker = "// Fisher-Yates shuffle";
const endMarker = "let state = loadState();";
const startIdx = src.indexOf(startMarker);
const endIdx = src.indexOf(endMarker, startIdx);

if (startIdx === -1 || endIdx === -1) {
  console.error("FAIL: could not locate shuffle/buildShuffledQuestions block in template.html");
  process.exit(1);
}

const extracted = src.slice(startIdx, endIdx);

// QUESTIONS is referenced as a free variable inside buildShuffledQuestions;
// we inject our own fixture before evaluating the extracted code.
function loadFunctions(questionsFixture) {
  const wrapped = `
    (function(QUESTIONS) {
      ${extracted}
      return { shuffle, buildShuffledQuestions };
    })
  `;
  const factory = eval(wrapped);
  return factory(questionsFixture);
}

let failures = 0;
function check(label, cond) {
  if (cond) {
    console.log("PASS - " + label);
  } else {
    console.log("FAIL - " + label);
    failures++;
  }
}

// ---- Fixture: one question, correct answer at index 2 ----
const Q = {
  q: "Sample question?",
  options: ["Wrong A", "Wrong B", "Correct C", "Wrong D"],
  correct: 2,
  explain: "because C is right"
};
const TRUE_CORRECT_TEXT = Q.options[Q.correct];

const { shuffle, buildShuffledQuestions } = loadFunctions([Q]);

// ---- Test 1: correctness invariant holds across many shuffles ----
const TRIALS = 500;
let correctnessOk = true;
const positionCounts = [0, 0, 0, 0];

for (let t = 0; t < TRIALS; t++) {
  const [sq] = buildShuffledQuestions();
  // The option sitting at sq.correct must always be the true correct text.
  if (sq.options[sq.correct] !== TRUE_CORRECT_TEXT) {
    correctnessOk = false;
  }
  // Every option's text must still be one of the original 4 (no corruption).
  const allPresent = Q.options.every(o => sq.options.includes(o)) && sq.options.length === Q.options.length;
  if (!allPresent) correctnessOk = false;

  positionCounts[sq.correct]++;
}
check("Correct answer's text matches original across " + TRIALS + " reshuffles", correctnessOk);

// ---- Test 2: position distribution is not degenerate (not always position 0) ----
console.log("Position distribution over " + TRIALS + " trials:", positionCounts);
const minShare = Math.min(...positionCounts) / TRIALS;
const maxShare = Math.max(...positionCounts) / TRIALS;
check("Every position appears (min share " + (minShare * 100).toFixed(1) + "% > 10%)", minShare > 0.10);
check("No position dominates (max share " + (maxShare * 100).toFixed(1) + "% < 40%)", maxShare < 0.40);
check("This reproduces the OLD bug as a sanity check: NOT always position 0", !(positionCounts[0] === TRIALS));

// ---- Test 3: selectedText round-trip survives a reshuffle (simulates resuming a test) ----
// Simulate: user answers on shuffle #1, then a NEW page load reshuffles (shuffle #2).
// The stored selectedText must still resolve to the right position/correctness on shuffle #2.
let roundTripOk = true;
for (let t = 0; t < 200; t++) {
  const [shuffle1] = buildShuffledQuestions();
  // user picks the correct option
  const selIdx = shuffle1.correct;
  const selectedText = shuffle1.options[selIdx];
  const wasCorrect = selIdx === shuffle1.correct; // true by construction here

  const [shuffle2] = buildShuffledQuestions(); // next load/restart => new order
  const newPos = shuffle2.options.indexOf(selectedText);
  const stillIdentifiedAsCorrectPosition = newPos === shuffle2.correct;
  // Since the user picked the TRUE correct answer, it must still be at shuffle2.correct.
  if (!stillIdentifiedAsCorrectPosition || newPos === -1) roundTripOk = false;
}
check("selectedText correctly re-locates after a reshuffle (200 trials)", roundTripOk);

// ---- Test 4: no duplicate option text in any real question (design assumption) ----
const contentDir = path.join(__dirname, "content");
let dupFound = null;
for (const file of fs.readdirSync(contentDir)) {
  if (!file.endsWith(".json")) continue;
  const data = JSON.parse(fs.readFileSync(path.join(contentDir, file), "utf-8"));
  data.forEach((q, i) => {
    const set = new Set(q.options);
    if (set.size !== q.options.length) {
      dupFound = file + " q" + i;
    }
  });
}
check("No question in content/*.json has duplicate option text (selectedText matching requires uniqueness)", dupFound === null);
if (dupFound) console.log("  -> duplicate found in: " + dupFound);

console.log("");
if (failures === 0) {
  console.log("ALL CHECKS PASSED");
  process.exit(0);
} else {
  console.log(failures + " CHECK(S) FAILED");
  process.exit(1);
}
