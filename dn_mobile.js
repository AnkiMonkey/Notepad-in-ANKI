/* Deep Notes Mobile (AnkiDroid / AnkiMobile)
 * Auto rows + Check inside the card template, put there by the Deep Notes Mobile add-on.
 * Runs only on a phone or tablet; on the PC it does nothing, Deep Notes keeps doing the job.
 * The same matching rules as Deep Notes (__init__.py), ported 1:1.
 * NOTE: never put two curly braces next to each other in this file –
 * Anki would read them as a template field. The setup script checks it.
 */
(function () {
  "use strict";
  var W = window;
  var CFG = W.DN_CFG || {};
  var ABBR = W.DN_ABBR || {};
  var STOP = ["a", "et", "na", "do", "s", "se", "v", "ve", "z", "ze", "pro", "jeho", "jako", "k", "ke", "o", "u"];
  var LONG_WORDS = Number(CFG.check_long_words != null ? CFG.check_long_words : 4);
  var LONG_PCT = Number(CFG.check_long_percent != null ? CFG.check_long_percent : 30);
  var DASH = CFG.smart_dash || "-";
  var C_OK = CFG.check_ok_color || "#55ff55";
  var C_BAD = CFG.check_bad_color || "#ff5555";
  var C_DUNNO = CFG.check_dunno_color || "#55aaff";
  var DUNNO = String(CFG.check_dunno_words || "?, idk, neviem, nwm, nv")
    .split(",").map(function (x) { return x.trim().toLowerCase(); }).filter(Boolean);

  /* ------------------------------------------------------------ matching */

  function plain(s) {
    return String(s).toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");
  }

  function words(s) {
    return plain(s).match(/[a-z0-9]+/g) || [];
  }

  // one typo allowed in longer words (missing, extra, wrong or two swapped letters)
  function close(a, b) {
    if (Math.abs(a.length - b.length) > 1 || Math.min(a.length, b.length) < 5) return false;
    var i, j;
    if (a.length === b.length) {
      var diff = [];
      for (i = 0; i < a.length; i++) if (a[i] !== b[i]) diff.push(i);
      if (diff.length === 2 && diff[1] === diff[0] + 1 &&
          a[diff[0]] === b[diff[1]] && a[diff[1]] === b[diff[0]]) return true;
    }
    var prev = [];
    for (j = 0; j <= b.length; j++) prev.push(j);
    for (i = 1; i <= a.length; i++) {
      var cur = [i];
      for (j = 1; j <= b.length; j++) {
        cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
      }
      prev = cur;
    }
    return prev[prev.length - 1] <= 1;
  }

  // anterior ~ anterius, transversus ~ transversarium
  function sameStem(a, b) {
    var n = 0, m = Math.min(a.length, b.length);
    while (n < m && a[n] === b[n]) n++;
    return n === m || n >= Math.max(4, m - 3);
  }

  function wordOk(typed, real) {
    if (real.indexOf(typed) === 0 || close(typed, real)) return true;
    var fulls = ABBR[typed] || [];
    for (var i = 0; i < fulls.length; i++) if (sameStem(fulls[i], real)) return true;
    return false;
  }

  // every typed word fits the next legend word; only filler words may be skipped
  function covers(typed, real) {
    var i = 0;
    for (var k = 0; k < real.length; k++) {
      var w = real[k];
      if (i < typed.length && wordOk(typed[i], w)) i++;
      else if (STOP.indexOf(w) >= 0) continue;
      else return false;
    }
    return i === typed.length;
  }

  function variants(answer) {
    var out = [];
    [answer, answer.replace(/\([^)]*\)/g, " ")].forEach(function (b) {
      out.push(b);
      out = out.concat(b.split(/[,;]| a | et /));
    });
    return out.map(words).filter(function (v) { return v.length; });
  }

  // long legend text: enough when > LONG_PCT % of its Latin words are in your answer
  // and every word you typed belongs to it ("longi" never passes for "brevis")
  function longOk(typed, answer) {
    var raw = answer.replace(/\([^)]*\)/g, " ").toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [];
    var real = raw.filter(function (w) { return /^[\x00-\x7f]+$/.test(w); })
      .map(plain).filter(function (w) { return STOP.indexOf(w) < 0; });
    if (real.length <= LONG_WORDS) return false;
    var hit = real.filter(function (w) { return typed.some(function (t) { return wordOk(t, w); }); }).length;
    var good = typed.filter(function (t) { return real.some(function (w) { return wordOk(t, w); }); }).length;
    return hit / real.length * 100 > LONG_PCT && good === typed.length;
  }

  // genitive attribute optional both ways: "corpus" = "corpus vertebrae"; a different genitive stays wrong
  var GEN_IS = ["ossis", "femoris", "capitis", "pelvis", "corporis", "pectoris", "dentis", "partis",
    "marginis", "tuberis", "foraminis", "cartilaginis", "laminae", "cruris", "pedis", "auris", "oris",
    "nasi", "cordis", "renis", "lienis", "hepatis", "colli", "manus", "cranii", "orbitae", "sellae",
    "processus", "tuberositatis", "arcus", "musculi", "nervi", "arteriae", "venae", "ligamenti",
    "sinus", "canalis", "sulci", "fossae"];
  function genStart(ws) {
    for (var k = 1; k < ws.length; k++) {
      var x = ws[k];
      if (GEN_IS.indexOf(x) >= 0 || /(ae|orum|arum|ium|uum|ei)$/.test(x) || (x.length > 3 && /i$/.test(x))) return k;
    }
    return 0;
  }
  function genOk(w, answer) {
    var aw = words(answer), i = genStart(aw), j = genStart(w), k, vs;
    if (i) {
      vs = variants(aw.slice(0, i).join(" "));
      for (k = 0; k < vs.length; k++) if (covers(w, vs[k])) return true;
    }
    if (j) {
      vs = variants(answer);
      for (k = 0; k < vs.length; k++) if (covers(w.slice(0, j), vs[k])) return true;
    }
    return false;
  }

  // SIAS, SIAI, SIPS, SIPI … from Deep Notes settings (check_abbrev), both in your answer and in the legend
  function expandAbbrev(t) {
    var ab = CFG.check_abbrev || {};
    Object.keys(ab).forEach(function (k) {
      var re = new RegExp("(^|[^\\p{L}\\p{N}])" + k.replace(/[.*+?^$()|[\]\\]/g, "\\$&") + "(?![\\p{L}\\p{N}])", "giu");
      t = t.replace(re, function (m, pre) { return pre + ab[k]; });
    });
    return t;
  }

  function answerOk(typed, answer, label) {
    typed = expandAbbrev(typed); answer = expandAbbrev(answer);
    var w = words(typed);
    if (w.length && label && w[0] === plain(label.replace(/[^\p{L}\p{N}_]/gu, ""))) w = w.slice(1);
    if (!w.length) return false;
    var vs = variants(answer);
    for (var i = 0; i < vs.length; i++) if (covers(w, vs[i])) return true;
    return genOk(w, answer) || longOk(w, answer);
  }

  function isDunno(text) {
    return DUNNO.indexOf(String(text).trim().toLowerCase()) >= 0;
  }

  /* ------------------------------------------------------- skipped points */

  function normLabel(s) {
    return String(s).replace(/\s+/g, "").replace(/\u2019/g, "'").toLowerCase();
  }

  // '1, 3-5, 3 (B), 1b' -> ['1','3','4','5','3(b)','1b']
  function tokens(text) {
    var out = [];
    text.split(/[,;]/).forEach(function (part) {
      part = part.trim();
      if (!part) return;
      var rng = part.match(/^(\d+)\s*[-\u2013\u2014]\s*(\d+)$/);
      if (rng) {
        var a = parseInt(rng[1], 10), b = parseInt(rng[2], 10);
        if (a <= b && b - a < 200) for (var i = a; i <= b; i++) out.push(String(i));
        return;
      }
      out.push(normLabel(part));
    });
    return out;
  }

  function escRe(s) {
    return s.replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/[{]/g, "\\x7b").replace(/[}]/g, "\\x7d");
  }

  function matches(label, token, labelsNorm) {
    var lab = normLabel(label);
    if (lab === token) return true;
    if (/^\d+$/.test(token) && labelsNorm.indexOf(token) < 0 &&
        new RegExp("^" + escRe(token) + "[a-z]'?$").test(lab)) return true;
    return false;
  }

  /* "NIE: 4, 6" -> those get the dash; "NIE: celá karta" -> all; "všetky" -> none;
     "body 1-10" / "1, 3, 7" -> everything NOT listed gets the dash */
  function skipSet(notesText, labels) {
    var low = String(notesText || "").trim().toLowerCase();
    var out = [];
    if (!low) return out;
    var labelsNorm = labels.map(normLabel);
    var hit = function (lab, toks) {
      return toks.some(function (t) { return matches(lab, t, labelsNorm); });
    };
    var m = low.match(/(?<![\p{L}\p{N}_])nie(?![\p{L}\p{N}_])\s*:?\s*([\s\S]*)/u);
    if (m) {
      var rest = m[1].trim();
      if (/^cel[áa]/.test(rest) || rest.indexOf("nic") === 0) return labels.map(function (_, i) { return i; });
      var t1 = tokens(rest);
      labels.forEach(function (lab, i) { if (hit(lab, t1)) out.push(i); });
      return out;
    }
    if (/v[šs]etk/.test(low)) return out;
    var after = low.indexOf(":") >= 0 ? low.slice(low.indexOf(":") + 1) : low;
    after = after.replace(/^\D*?(?=\d)/, "");
    var t2 = tokens(after);
    if (!t2.length) return out;
    labels.forEach(function (lab, i) { if (!hit(lab, t2)) out.push(i); });
    return out;
  }

  /* ---------------------------------------------------------------- tests */

  if (W.DN_TEST_HOOK) {
    W.DN_TEST_HOOK({
      plain: plain, words: words, close: close, sameStem: sameStem, wordOk: wordOk,
      covers: covers, variants: variants, longOk: longOk, answerOk: answerOk, genOk: genOk,
      isDunno: isDunno, tokens: tokens, skipSet: skipSet
    });
    return;
  }

  /* ------------------------------------------------------------------- UI */

  function onMobile() {
    try { if (localStorage.getItem("dn_force") === "1") return true; } catch (e) { /* no storage */ }
    return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "");
  }

  function getFlag(name, def) {
    try { var v = localStorage.getItem(name); return v === null ? def : v === "1"; } catch (e) { return def; }
  }

  function setFlag(name, on) {
    try { localStorage.setItem(name, on ? "1" : "0"); } catch (e) { /* no storage */ }
  }

  function loadState(key) {
    var mem = W.__dnStore || (W.__dnStore = {});
    if (mem[key]) return mem[key];
    try { var s = sessionStorage.getItem(key); return s ? JSON.parse(s) : null; } catch (e) { return null; }
  }

  function saveState(key, st) {
    (W.__dnStore || (W.__dnStore = {}))[key] = st;
    try { sessionStorage.setItem(key, JSON.stringify(st)); } catch (e) { /* no storage */ }
  }

  function fieldText(id) {
    var el = document.getElementById(id);
    if (!el) return "";
    var tmp = document.createElement("textarea");
    tmp.innerHTML = el.innerHTML.replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ");
    return tmp.value;
  }

  function css() {
    return [
      "#dn-root{margin:14px auto 6px;max-width:680px;text-align:left;font-family:inherit;color:#eee}",
      "#dn-root .dn-bar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px}",
      "#dn-root .dn-title{font-weight:bold;color:#aaa;margin-right:auto;font-size:14px}",
      "#dn-root .dn-score{font-size:14px;color:#aaa}",
      "#dn-root .dn-btn{background:#333;color:#ddd;border:1px solid #555;border-radius:6px;padding:6px 12px;font-size:14px}",
      "#dn-root .dn-btn.on{border-color:" + C_OK + ";color:#fff}",
      "#dn-root table{width:100%;border-collapse:collapse;background:#222}",
      "#dn-root td{border:1px solid #444;padding:2px 6px;vertical-align:middle}",
      "#dn-root td.dn-l{width:3.5em;white-space:nowrap;color:#aaa;font-size:15px}",
      "#dn-root input{width:100%;box-sizing:border-box;background:transparent;border:0;color:#eee;font-size:16px;padding:7px 2px;outline:none;font-family:inherit}",
      "#dn-root tr.dn-focus td{background:#2b2b2b}",
      "#dn-root input.dn-ok{color:" + C_OK + "}",
      "#dn-root input.dn-bad{color:" + C_BAD + "}",
      "#dn-root input.dn-dunno{color:" + C_DUNNO + "}",
      "#dn-root input.dn-dash{color:#777}",
      "#dn-root tr.dn-tip td{font-size:13px;color:#999;white-space:pre-wrap;border-top:0}",
      "#dn-root .dn-done{color:#aaa;font-size:14px;margin-top:6px}"
    ].join("\n");
  }

  function init() {
    var root = document.getElementById("dn-root");
    if (!root || root.getAttribute("data-dn") === "1") return;
    if (!onMobile()) return;
    var data;
    try { data = JSON.parse(fieldText("dn-legend").trim()); } catch (e) { return; }
    if (!data || !data.labels || !data.labels.length) return;
    root.setAttribute("data-dn", "1");

    var labels = data.labels;
    var answers = data.answers || {};
    var full = data.full || {};
    var notes = fieldText("dn-pnotes");
    var isBack = !!document.getElementById("dn-back");
    var key = "dn:" + (data.img || labels.join("|"));

    var st = loadState(key);
    // front of a new card = clean table (like the add-on after rating);
    // a reload of the same front (rotation) or the back side keeps what you typed
    if (!st || st.labels !== labels.join("|") || (!isBack && st.flipped)) {
      st = { labels: labels.join("|"), rows: labels.map(function () {
        return { v: "", c: "", tip: "", wrong: "" };
      }) };
    }
    if (isBack) st.flipped = true;
    saveState(key, st);

    var style = document.createElement("style");
    style.textContent = css();
    root.appendChild(style);

    var bar = document.createElement("div");
    bar.className = "dn-bar";
    bar.innerHTML = '<span class="dn-title">Deep Notes</span><span class="dn-score"></span>' +
      '<button type="button" class="dn-btn" data-b="auto">Auto</button>' +
      '<button type="button" class="dn-btn" data-b="check">Check</button>' +
      '<button type="button" class="dn-btn" data-b="clear" title="Clear">\u21ba</button>';
    root.appendChild(bar);
    var table = document.createElement("table");
    root.appendChild(table);
    var doneLine = document.createElement("div");
    doneLine.className = "dn-done";
    root.appendChild(doneLine);

    var inputs = [];
    var prevVal = [];

    function autoOn() { return getFlag("dn_auto", true); }
    function checkOn() { return getFlag("dn_check", true); }

    function dashes() {
      return autoOn() ? skipSet(notes, labels) : [];
    }

    function save() { saveState(key, st); }

    function paintButtons() {
      bar.querySelector('[data-b="auto"]').className = "dn-btn" + (autoOn() ? " on" : "");
      bar.querySelector('[data-b="auto"]').textContent = autoOn() ? "Auto \u2713" : "Auto";
      bar.querySelector('[data-b="check"]').className = "dn-btn" + (checkOn() ? " on" : "");
      bar.querySelector('[data-b="check"]').textContent = checkOn() ? "Check \u2713" : "Check";
    }

    function score() {
      var ok = 0, dunno = 0, total = 0;
      st.rows.forEach(function (r) {
        if (r.c === "dash") return;
        total++;
        if (r.c === "ok") ok++;
        if (r.c === "dunno") dunno++;
      });
      bar.querySelector(".dn-score").innerHTML = checkOn()
        ? '<span style="color:' + C_OK + '">' + ok + "</span> / " +
          '<span style="color:' + C_DUNNO + '">' + dunno + "</span> / " + total
        : "";
      doneLine.textContent = checkOn() && total && ok + dunno === total
        ? "Hotovo: " + ok + " z " + total + " spr\u00e1vne" : "";
    }

    function setRow(i, c, value, tip) {
      var r = st.rows[i], inp = inputs[i];
      r.c = c;
      if (value != null) { r.v = value; inp.value = value; prevVal[i] = value; }
      if (tip != null) r.tip = tip;
      inp.className = c ? "dn-" + c : "";
      inp.readOnly = c === "ok" || c === "dunno" || c === "dash";
      inp.title = r.tip || "";
      save();
      score();
    }

    function nextRow(i) {
      for (var j = i + 1; j < inputs.length; j++) {
        var c = st.rows[j].c;
        if (c !== "dash" && c !== "ok" && c !== "dunno") { inputs[j].focus(); return; }
      }
      if (inputs[i]) inputs[i].blur();
    }

    function firstOpen() {
      for (var j = 0; j < inputs.length; j++) {
        var c = st.rows[j].c;
        if (c !== "dash" && c !== "ok" && c !== "dunno") { inputs[j].focus(); return; }
      }
    }

    function reveal(i, tried) {
      var answer = answers[labels[i]];
      if (!answer) return false;
      var f = full[labels[i]] || "";
      var tip = f && f !== answer ? f : "";
      if (tried) tip = (tip ? tip + "\n" : "") + "you wrote: " + tried;
      st.rows[i].wrong = "";
      setRow(i, "dunno", answer, tip || answer);
      nextRow(i);
      return true;
    }

    // true = handled (this row has an answer to check against)
    function check(i, viaEnter) {
      var label = labels[i];
      var answer = answers[label];
      if (!answer) return false;
      var r = st.rows[i];
      var text = inputs[i].value.trim();
      if (!text) return false;  // empty row + Enter = skip to the next one
      if (isDunno(text)) return reveal(i, "");
      if (viaEnter && text && r.wrong === text) return reveal(i, text);
      var f = full[label] || "";
      if (answerOk(text, answer, label) || (f && f !== answer && answerOk(text, f, label))) {
        r.wrong = "";
        setRow(i, "ok", text, f || answer);
        nextRow(i);
        return true;
      }
      if (text) {
        r.wrong = text;  // Enter again (or two spaces) = "I don't know"
        setRow(i, "bad", inputs[i].value);
      }
      return true;
    }

    function toggleTip(i) {
      var tr = inputs[i].closest("tr");
      var nx = tr.nextSibling;
      if (nx && nx.className === "dn-tip") { nx.parentNode.removeChild(nx); return; }
      if (!st.rows[i].tip) return;
      var t = document.createElement("tr");
      t.className = "dn-tip";
      t.innerHTML = "<td></td><td></td>";
      t.lastChild.textContent = st.rows[i].tip;
      tr.parentNode.insertBefore(t, tr.nextSibling);
    }

    function render() {
      var skip = dashes();
      st.rows.forEach(function (r, i) {
        if (skip.indexOf(i) >= 0) { r.c = "dash"; r.v = DASH; }
        else if (r.c === "dash") { r.c = ""; r.v = ""; }
      });
      table.innerHTML = "";
      inputs = [];
      prevVal = [];
      labels.forEach(function (lab, i) {
        var tr = document.createElement("tr");
        var td1 = document.createElement("td");
        td1.className = "dn-l";
        td1.textContent = lab;
        var td2 = document.createElement("td");
        var inp = document.createElement("input");
        inp.type = "text";
        inp.setAttribute("autocomplete", "off");
        inp.setAttribute("autocorrect", "off");
        inp.setAttribute("autocapitalize", "off");
        inp.setAttribute("spellcheck", "false");
        inp.setAttribute("enterkeyhint", "next");
        td2.appendChild(inp);
        tr.appendChild(td1);
        tr.appendChild(td2);
        table.appendChild(tr);
        inputs.push(inp);
        prevVal.push(st.rows[i].v);
        inp.value = st.rows[i].v;
        inp.className = st.rows[i].c ? "dn-" + st.rows[i].c : "";
        inp.readOnly = ["ok", "dunno", "dash"].indexOf(st.rows[i].c) >= 0;
        inp.title = st.rows[i].tip || "";

        inp.addEventListener("focus", function () { tr.className = "dn-focus"; });
        inp.addEventListener("blur", function () { tr.className = ""; });
        inp.addEventListener("click", function () { if (inp.readOnly) toggleTip(i); });
        inp.addEventListener("keydown", function (ev) {
          if (ev.altKey) return;
          if (ev.key === "Enter" || ev.keyCode === 13) {
            ev.preventDefault();
            ev.stopPropagation();
            if (inp.readOnly || !checkOn() || !check(i, true)) nextRow(i);
          } else if (ev.key === "Escape" || ev.keyCode === 27) {
            ev.preventDefault();
            ev.stopPropagation();
            inp.blur();
          } else {
            ev.stopPropagation();  // typing never flips or rates the card
          }
        });
        inp.addEventListener("input", function () {
          if (inp.readOnly) return;
          var v = inp.value, before = prevVal[i] || "";
          prevVal[i] = v;
          st.rows[i].v = v;
          var added = v.length > before.length;
          var atEnd = inp.selectionEnd == null || inp.selectionEnd === v.length;
          if (checkOn() && answers[lab]) {
            if (isDunno(v)) { reveal(i, ""); return; }
            if (added && atEnd && /\s$/.test(v) && v.trim()) {
              if (/\s\s$/.test(v)) { reveal(i, v.trim()); return; }  // two spaces = show it
              check(i, false);
              return;
            }
          }
          if (st.rows[i].c === "bad") setRow(i, "");  // typing again: normal colour
          else save();
        });
      });
      paintButtons();
      score();
    }

    bar.addEventListener("click", function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-b]");
      if (!b) return;
      ev.preventDefault();
      ev.stopPropagation();
      var what = b.getAttribute("data-b");
      if (what === "auto") setFlag("dn_auto", !autoOn());
      if (what === "check") setFlag("dn_check", !checkOn());
      if (what === "clear") {
        st.rows.forEach(function (r) { r.v = ""; r.c = ""; r.tip = ""; r.wrong = ""; });
      }
      save();
      render();
    });

    if (!W.__dnKeys) {
      W.__dnKeys = true;
      document.addEventListener("keydown", function (ev) {
        if (!ev.altKey || ev.ctrlKey || ev.metaKey) return;
        var k = (ev.key || "").toLowerCase();
        var btn = null;
        if (k === "k" || ev.keyCode === 75) btn = "auto";
        else if (k === "j" || ev.keyCode === 74) btn = "check";
        else if (k === "p" || ev.keyCode === 80) btn = "focus";
        if (!btn) return;
        var r = document.getElementById("dn-root");
        if (!r || r.getAttribute("data-dn") !== "1") return;
        ev.preventDefault();
        ev.stopPropagation();
        if (btn === "focus") { W.__dnFocus && W.__dnFocus(); return; }
        var el = r.querySelector('[data-b="' + btn + '"]');
        if (el) el.click();
      }, true);
    }
    W.__dnFocus = firstOpen;

    render();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else setTimeout(init, 0);
})();
