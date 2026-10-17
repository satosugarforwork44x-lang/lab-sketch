// lab/ui/panel.js — ラボスケッチ。論文のカードの一覧（絞り込み）と、1 枚のカード（書誌・タグ・状態）。
// ・データは「Lab Sketch\papers」の <名前>.md。外（Claude・フォルダ窓）で変わったら読み直す
// ・PDF を落とす → 書誌を推定して名前を提案 → 利用者が直して取り込む
// ・カードの本文（要約など）は Claude が書く。ここでは読むだけ
import { selectBox } from "/ui/js/hub.js";
import { icons } from "/ui/js/icons.js";
import { LE, drawEngineList, engineView, statusBadge } from "./engines.js";

const EN = (document.documentElement.lang || navigator.language || "ja").startsWith("en");
const L = EN ? {
  search: "Search title, author, tag", all: "All", status: { unread: "Unread", read: "Read", cite: "To cite" },
  anyTag: "All tags", anyYear: "All years", add: "Add PDFs…", folder: "Show the folder", more: "More",
  empty: "No papers yet. Drop PDFs here, or into the “Lab Sketch” folder in Hub.", noMatch: "Nothing matches",
  bib: (n) => `Export ${n} shown paper${n > 1 ? "s" : ""} as BibTeX`, refs: (n) => `Export ${n} shown paper${n > 1 ? "s" : ""} as a reference list (.md)`,
  exported: (f) => `Saved ${f} and copied it`,
  pending: (n) => `${n} PDF${n > 1 ? "s" : ""} without a card`, pendingGo: "Make cards",
  noPdf: "PyMuPDF is not installed, so titles and authors can't be read from PDFs (cards are still made from the file name). To install:",
  copy: "Copy", copied: "Copied", back: "All papers", openPdf: "Open the PDF", openCard: "Open the card", reveal: "Show in Explorer",
  rename: "Rename", ask: "Ask Claude", askTip: "Copy a request for Claude Desktop (share the “Lab Sketch” folder with Claude as read & write)",
  askText: (n) => `In Hub's “Lab Sketch” folder, read papers/${n}.pdf and fill in the sections of papers/${n}.md following LAB_FORMAT.md. Leave “My notes” empty.`,
  title: "Title", authors: "Authors (one per line)", year: "Year", doi: "DOI", tags: "Tags (comma separated)", state: "Status",
  body: "Card (written by Claude)", bodyEmpty: "Not summarized yet. Use “Ask Claude”.", missingPdf: "The PDF is missing",
  importTitle: "Add papers", importNote: "Titles and authors are guessed from the first page — fix them here or later on the card.",
  name: "File name", modeCopy: "Copy (keep the original)", modeMove: "Move", inside: "Already in the folder — it will be moved into papers.",
  dup: (n) => `Same PDF as “${n}”`, go: "Add", cancel: "Cancel", made: (n) => `Added ${n} card${n > 1 ? "s" : ""}`,
  skipped: (s) => `Not added: ${s}`, newName: "New name", renamed: "Renamed", saved: "Saved", reloaded: "Updated (changed outside)",
  filled: (n) => `${n}/5 written`, skills: (n) => `${n} engine${n > 1 ? "s" : ""}`, broken: "Can't read the card",
} : {
  search: "題名・著者・タグでさがす", all: "すべて", status: { unread: "未読", read: "読んだ", cite: "引用する" },
  anyTag: "すべてのタグ", anyYear: "すべての年", add: "PDF を取り込む…", folder: "フォルダを見る", more: "その他",
  empty: "まだありません。PDF をここに落とすか、Hub のフォルダ窓「Lab Sketch」に入れてください。", noMatch: "当てはまる論文がありません",
  bib: (n) => `表示中の ${n} 件を BibTeX に書き出す`, refs: (n) => `表示中の ${n} 件を参考文献の一覧（md）に書き出す`,
  exported: (f) => `${f} に書き出して、コピーしました`,
  pending: (n) => `カードの無い PDF が ${n} 件あります`, pendingGo: "カードを作る",
  noPdf: "PyMuPDF が入っていないので、PDF から題名・著者を読めません（カードはファイル名で作れます）。入れるには:",
  copy: "コピー", copied: "コピーしました", back: "一覧に戻る", openPdf: "PDF を開く", openCard: "カードを開く", reveal: "エクスプローラーで見る",
  rename: "名前を変える", ask: "Claude に頼む", askTip: "Claude Desktop に頼む文をコピー（フォルダ窓「Lab Sketch」を Claude に「読み書き」で見せておく）",
  askText: (n) => `Hub のフォルダ窓「Lab Sketch」の papers/${n}.pdf を読んで、LAB_FORMAT.md に従って papers/${n}.md の各節を書いてください。「自分のメモ」は空のままにしてください。`,
  title: "題名", authors: "著者（1 行に 1 人）", year: "年", doi: "DOI", tags: "タグ（カンマ区切り）", state: "状態",
  body: "カード（Claude が書く所）", bodyEmpty: "まだまとめていません。「Claude に頼む」から頼めます。", missingPdf: "PDF が見つかりません",
  importTitle: "論文を取り込む", importNote: "題名・著者は 1 ページ目からの推定です。ここか、あとでカードの上で直せます。",
  name: "ファイル名", modeCopy: "コピー（元を残す）", modeMove: "移動", inside: "フォルダの中の PDF なので papers へ移します",
  dup: (n) => `「${n}」と同じ PDF です`, go: "取り込む", cancel: "やめる", made: (n) => `${n} 件のカードを作りました`,
  skipped: (s) => `取り込めなかったもの: ${s}`, newName: "新しい名前", renamed: "名前を変えました", saved: "保存しました", reloaded: "外で書き換えられたので読み直しました",
  filled: (n) => `${n}/5 節`, skills: (n) => `エンジン ${n}`, broken: "カードが読めません",
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ico = (n) => icons[n] || "";
const on = (b, v) => b.setAttribute("aria-checked", v ? "true" : "false");   // .seg の選ばれた見た目

export async function mount(el, ctx) {
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = new URL("./lab.css", import.meta.url).href;
  document.head.append(css);

  el.innerHTML = `<div class="lab">
    <section class="lab-home">
      <div class="lab-bar">
        <div class="lab-mode seg" role="tablist"></div>
        <input class="lab-q" type="search">
        <button class="btn primary lab-add"></button>
        <button class="icon-btn lab-more"></button>
      </div>
      <div class="lab-bar lab-filter">
        <div class="lab-seg seg" role="group"></div>
        <span class="lab-tag"></span><span class="lab-year"></span>
      </div>
      <div class="lab-notes"></div>
      <div class="lab-list" role="list"></div>
    </section>
    <section class="lab-card" hidden></section>
  </div>`;
  const $ = (s, r = el) => r.querySelector(s);
  const home = $(".lab-home"), cardView = $(".lab-card"), list = $(".lab-list"), notes = $(".lab-notes");
  let st = null, sig = "", cur = null, saveTimer = 0, mode = "papers", eng = null, engFrom = "";
  const f = { q: "", status: "", tag: "", year: "" };

  // ---------- 論文 / エンジン ----------
  for (const [v, label] of [["papers", LE.tabPapers], ["engines", LE.tabEngines]]) {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.dataset.v = v;
    b.innerHTML = `${ico(v === "papers" ? "bookOpen" : "sigma")}<span>${esc(label)}</span>`;
    b.addEventListener("click", () => { mode = v; refresh(); });
    $(".lab-mode").append(b);
  }

  // ---------- 一覧 ----------
  $(".lab-q").placeholder = L.search;
  $(".lab-q").addEventListener("input", (e) => { f.q = e.target.value.trim().toLowerCase(); drawList(); });
  const seg = $(".lab-seg");
  for (const [v, label] of [["", L.all], ...Object.entries(L.status)]) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.dataset.v = v;
    b.addEventListener("click", () => { f.status = v; drawList(); });
    seg.append(b);
  }
  $(".lab-add").innerHTML = `${ico("bookOpen")}<span>${esc(L.add)}</span>`;
  $(".lab-add").addEventListener("click", async () => {
    const picked = await ctx.host.pickFiles(ctx.id).catch(() => null);
    if (picked?.length) startImport(picked);
  });
  $(".lab-more").innerHTML = ico("more") || "⋯";
  $(".lab-more").title = L.more;
  $(".lab-more").addEventListener("click", (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const shown = st.cards.filter(match).map((c) => c.name);
    ctx.contextMenu([
      { label: L.folder, icon: ico("folder"), onClick: () => ctx.host.openPath(st.folder) },
      "-",
      { label: L.bib(shown.length), icon: ico("bookOpen"), disabled: !shown.length || mode !== "papers", onClick: () => exportRefs(shown, "bib") },
      { label: L.refs(shown.length), icon: ico("text"), disabled: !shown.length || mode !== "papers", onClick: () => exportRefs(shown, "md") },
      "-",
      { label: (st.mode === "copy" ? "✓ " : "　") + L.modeCopy, onClick: () => setMode("copy") },
      { label: (st.mode === "move" ? "✓ " : "　") + L.modeMove, onClick: () => setMode("move") },
    ], r.left, r.bottom + 4);
  });
  async function exportRefs(names, kind) {
    try {
      const r = await ctx.call("export_refs", { names, kind, lang: EN ? "en" : "ja" });
      try { await navigator.clipboard.writeText(r.text); } catch { /* コピーできなくてもファイルはある */ }
      ctx.toast(L.exported(r.file));
    } catch (e) { ctx.toast(e.message, "error"); }
  }
  async function setMode(m) { st.mode = (await ctx.call("set_mode", { mode: m })).mode; }

  function filters() {
    const tags = [...new Set(st.cards.flatMap((c) => c.tags))].sort((a, b) => a.localeCompare(b));
    const years = [...new Set(st.cards.map((c) => c.year).filter(Boolean))].sort((a, b) => b - a);
    if (f.tag && !tags.includes(f.tag)) f.tag = "";
    if (f.year && !years.includes(+f.year)) f.year = "";
    $(".lab-tag").replaceChildren(selectBox({ options: [{ value: "", label: L.anyTag }, ...tags.map((t) => ({ value: t, label: t }))],
      value: f.tag, onChange: (v) => { f.tag = v; drawList(); } }));
    $(".lab-year").replaceChildren(selectBox({ options: [{ value: "", label: L.anyYear }, ...years.map((y) => ({ value: String(y), label: String(y) }))],
      value: f.year, onChange: (v) => { f.year = v; drawList(); } }));
  }

  function drawNotes() {
    notes.replaceChildren();
    if (!st.pymupdf) {
      const d = document.createElement("div");
      d.className = "lab-note";
      d.innerHTML = `<span>${esc(L.noPdf)}</span><code></code><button class="btn">${esc(L.copy)}</button>`;
      d.querySelector("code").textContent = st.pip;
      d.querySelector("button").addEventListener("click", () => copy(st.pip));
      notes.append(d);
    }
    if (st.pending.length) {
      const d = document.createElement("div");
      d.className = "lab-note";
      d.innerHTML = `<span>${esc(L.pending(st.pending.length))}</span><span class="sm"></span><button class="btn primary">${esc(L.pendingGo)}</button>`;
      d.querySelector(".sm").textContent = st.pending.slice(0, 3).map((p) => p.file).join("、") + (st.pending.length > 3 ? " …" : "");
      d.querySelector("button").addEventListener("click", () => startImport(st.pending.map((p) => p.path)));
      notes.append(d);
    }
  }

  function match(c) {
    if (f.status && c.status !== f.status) return false;
    if (f.tag && !c.tags.includes(f.tag)) return false;
    if (f.year && String(c.year) !== f.year) return false;
    if (f.q) {
      const hay = [c.title, c.name, ...c.authors, ...c.tags, c.doi].join(" ").toLowerCase();
      return f.q.split(/\s+/).every((w) => hay.includes(w));
    }
    return true;
  }

  function drawList() {
    for (const b of seg.children) on(b, b.dataset.v === f.status);
    const rows = st.cards.filter(match);
    list.replaceChildren();
    if (!rows.length) {
      list.innerHTML = `<p class="lab-none">${esc(st.cards.length ? L.noMatch : L.empty)}</p>`;
      return;
    }
    for (const c of rows) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "lab-row";
      b.setAttribute("role", "listitem");
      const who = c.authors.length > 2 ? c.authors[0] + (EN ? " et al." : " ほか") : c.authors.join(EN ? ", " : "、");
      b.innerHTML = `<span class="st st-${c.status}">${esc(L.status[c.status])}</span>
        <span class="main"><span class="t"></span><span class="m"></span></span>
        <span class="side"><span class="tags"></span><span class="info"></span></span>`;
      b.querySelector(".t").textContent = c.error ? `${c.name} — ${L.broken}` : c.title;
      b.querySelector(".m").textContent = [who, c.year].filter(Boolean).join(" · ");
      for (const t of c.tags.slice(0, 4)) {
        const s = document.createElement("span");
        s.className = "chip";
        s.textContent = t;
        b.querySelector(".tags").append(s);
      }
      const info = [];
      if (c.filled.length) info.push(`${ico("bookOpen")}${esc(L.filled(Math.min(c.filled.length, 5)))}`);
      if (c.skills.length) info.push(`${ico("sigma")}${esc(L.skills(c.skills.length))}`);
      if (!c.hasPdf) info.push(`<span class="warn">${esc(L.missingPdf)}</span>`);
      b.querySelector(".info").innerHTML = info.join("");
      b.addEventListener("click", () => openCard(c.name));
      list.append(b);
    }
  }

  async function refresh() {
    st = await ctx.call("state");
    sig = (await ctx.call("poll")).sig;
    for (const b of $(".lab-mode").children) on(b, b.dataset.v === mode);
    const eng_ = mode === "engines";
    $(".lab-q").hidden = eng_;
    $(".lab-filter").hidden = eng_;
    notes.hidden = eng_;
    if (eng_) {
      const r = await drawEngineList(ctx, list, (n) => openEngine(n));
      ctx.setStatus(`${r.skills.length} · ${r.folder}`);
      return;
    }
    filters();
    drawNotes();
    drawList();
    ctx.setStatus(`${st.cards.length} · ${st.folder}`);
  }

  // ---------- 取り込み ----------
  async function startImport(paths) {
    let r;
    try { r = await ctx.call("inspect", { paths }); } catch (e) { return ctx.toast(e.message, "error"); }
    if (r.skipped.length) ctx.toast(L.skipped(r.skipped.join(", ")), "error", 6000);
    if (!r.items.length) return;
    const items = await importDialog(r.items);
    if (!items) return;
    try {
      const m = await ctx.call("import_pdfs", { items, mode: st.mode, lang: EN ? "en" : "ja" });
      if (m.skipped.length) ctx.toast(L.skipped(m.skipped.join(", ")), "error", 8000);
      if (m.made.length) ctx.toast(L.made(m.made.length));
      await refresh();
      if (m.made.length === 1) openCard(m.made[0]);
    } catch (e) { ctx.toast(e.message, "error"); }
  }

  function importDialog(items) {
    return new Promise((resolve) => {
      const dlg = document.createElement("div");
      dlg.className = "lab-dlg";
      dlg.innerHTML = `<div class="lab-dlg-box" role="dialog" aria-modal="true"><h3>${esc(L.importTitle)}</h3><p class="note">${esc(L.importNote)}</p>
        <div class="lab-imp"></div>
        <div class="btn-row"><div class="seg mode"></div><span class="sp"></span><button class="btn cancel">${esc(L.cancel)}</button><button class="btn primary go">${esc(L.go)}</button></div></div>`;
      const box = dlg.querySelector(".lab-imp");
      const anyOutside = items.some((it) => !it.inside);
      let mode = st.mode;
      const modeSeg = dlg.querySelector(".mode");
      if (anyOutside) {
        for (const [v, label] of [["copy", L.modeCopy], ["move", L.modeMove]]) {
          const b = document.createElement("button");
          b.type = "button";
          b.textContent = label;
          on(b, v === mode);
          b.addEventListener("click", () => { mode = v; for (const x of modeSeg.children) on(x, x === b); });
          modeSeg.append(b);
        }
      }
      const fields = items.map((it) => {
        const row = document.createElement("div");
        row.className = "lab-imp-row";
        row.innerHTML = `<div class="file"></div>
          <label class="wide"><span>${esc(L.name)}</span><input class="nm"><span class="ext">.pdf / .md</span></label>
          <label class="wide"><span>${esc(L.title)}</span><input class="ti"></label>
          <label><span>${esc(L.authors)}</span><textarea class="au" rows="2"></textarea></label>
          <div class="pair"><label><span>${esc(L.year)}</span><input class="yr" inputmode="numeric"></label>
          <label><span>${esc(L.doi)}</span><input class="doi"></label></div>
          <div class="msg"></div>`;
        row.querySelector(".file").textContent = it.file;
        row.querySelector(".nm").value = it.name;
        row.querySelector(".ti").value = it.title;
        row.querySelector(".au").value = it.authors.join("\n");
        row.querySelector(".yr").value = it.year || "";
        row.querySelector(".doi").value = it.doi;
        const msg = [it.dup && L.dup(it.dup), it.inside && L.inside, it.warn].filter(Boolean);
        row.querySelector(".msg").textContent = msg.join(" / ");
        box.append(row);
        return { it, row };
      });
      const done = (v) => { dlg.remove(); resolve(v); };
      dlg.querySelector(".cancel").addEventListener("click", () => done(null));
      dlg.querySelector(".go").addEventListener("click", () => {
        if (anyOutside && mode !== st.mode) setMode(mode);
        st.mode = mode;
        done(fields.map(({ it, row }) => ({
          path: it.path, file: it.file, name: row.querySelector(".nm").value.trim(), title: row.querySelector(".ti").value.trim(),
          authors: row.querySelector(".au").value.split("\n").map((s) => s.trim()).filter(Boolean),
          year: row.querySelector(".yr").value.trim(), doi: row.querySelector(".doi").value.trim(),
        })));
      });
      dlg.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); done(null); } });
      dlg.addEventListener("pointerdown", (e) => { if (e.target === dlg) done(null); });
      document.body.append(dlg);
      dlg.querySelector(".nm").focus();
    });
  }

  ctx.onNativeDrop((paths) => {
    const pdfs = (paths || []).filter((p) => /\.pdf$/i.test(p));
    if (pdfs.length) startImport(pdfs);
  });

  // ---------- 1 枚のカード ----------
  function openEngine(name, from = "") {
    cur = null;
    engFrom = from;
    home.hidden = true;
    cardView.hidden = false;
    eng = engineView(ctx, cardView, name, {
      back: () => { eng = null; engFrom ? openCard(engFrom) : showHome(); },
      copy, openCard: (n) => { eng = null; openCard(n); },
    });
  }

  async function openCard(name, quiet = false) {
    eng = null;
    try { cur = await ctx.call("card", { name }); } catch (e) { ctx.toast(e.message, "error"); return showHome(); }
    home.hidden = true;
    cardView.hidden = false;
    drawCard(quiet);
  }

  function showHome() {
    cur = null;
    eng = null;
    cardView.hidden = true;
    home.hidden = false;
    refresh();
  }

  function drawCard(quiet) {
    const m = cur.meta;
    const focused = quiet ? document.activeElement?.dataset?.k : null;
    if (focused) return drawBody();             // 打っている途中は書誌の欄を作り直さない
    cardView.innerHTML = `<div class="lab-cbar">
        <button class="btn back">‹ ${esc(L.back)}</button><span class="sp"></span>
        <button class="btn pdf">${ico("bookOpen")}<span>${esc(L.openPdf)}</span></button>
        <button class="btn ask" title="${esc(L.askTip)}">${esc(L.ask)}</button>
        <button class="icon-btn more" title="${esc(L.more)}">${ico("more") || "⋯"}</button>
      </div>
      <div class="lab-cbody">
        <div class="lab-meta">
          <p class="err" hidden></p>
          <label class="wide"><span>${esc(L.title)}</span><textarea data-k="title" rows="2"></textarea></label>
          <label><span>${esc(L.authors)}</span><textarea data-k="authors" rows="3"></textarea></label>
          <div class="pair"><label><span>${esc(L.year)}</span><input data-k="year" inputmode="numeric"></label>
            <label><span>${esc(L.doi)}</span><input data-k="doi"></label></div>
          <label><span>${esc(L.tags)}</span><input data-k="tags"></label>
          <div class="field"><span>${esc(L.state)}</span><div class="seg st"></div></div>
          <div class="field lab-cengines"><span>${esc(LE.engines)}</span><div class="list"></div>
            <div class="row"><button class="btn newe">${ico("sigma")}<span>${esc(LE.newEngine)}</span></button><button class="btn linke">${esc(LE.link)}</button></div></div>
          <p class="fname"></p>
        </div>
        <div class="lab-text"><h4>${esc(L.body)}</h4><div class="md"></div></div>
      </div>`;
    const q = (s) => cardView.querySelector(s);
    q(".err").hidden = !cur.error;
    q(".err").textContent = cur.error;
    q("[data-k=title]").value = m.title;
    q("[data-k=authors]").value = m.authors.join("\n");
    q("[data-k=year]").value = m.year || "";
    q("[data-k=doi]").value = m.doi;
    q("[data-k=tags]").value = m.tags.join(", ");
    q(".fname").textContent = `${cur.name}.md · ${m.pdf || "—"}${m.source && m.source !== m.pdf ? ` (${m.source})` : ""}`;
    for (const [v, label] of Object.entries(L.status)) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      on(b, v === m.status);
      b.addEventListener("click", () => { for (const x of q(".st").children) on(x, x === b); saveNow({ status: v }); });
      q(".st").append(b);
    }
    for (const inp of cardView.querySelectorAll("[data-k]")) {
      inp.addEventListener("input", () => { clearTimeout(saveTimer); saveTimer = setTimeout(() => saveNow(collect()), 700); });
      inp.addEventListener("change", () => saveNow(collect()));
    }
    q(".back").addEventListener("click", async () => { await flushSave(); showHome(); });
    q(".pdf").disabled = !cur.pdfPath;
    q(".pdf").title = cur.pdfPath ? "" : L.missingPdf;
    q(".pdf").addEventListener("click", () => ctx.host.openFile(cur.pdfPath).catch((e) => ctx.toast(e.message, "error")));
    q(".ask").addEventListener("click", () => copy(L.askText(cur.name)));
    q(".more").addEventListener("click", (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      ctx.contextMenu([
        { label: L.openCard, icon: ico("open"), onClick: () => ctx.host.openFile(cur.path).catch((er) => ctx.toast(er.message, "error")) },
        { label: L.rename, icon: ico("rename"), onClick: renameCard },
        { label: L.reveal, icon: ico("reveal"), onClick: () => ctx.host.revealPath(cur.path) },
      ], r.right - 200, r.bottom + 4);
    });
    drawEngines();
    drawBody();
  }

  async function drawEngines() {
    const box = cardView.querySelector(".lab-cengines");
    if (!box) return;
    const all = (await ctx.call("skills")).skills;
    const list_ = box.querySelector(".list");
    list_.replaceChildren();
    for (const n of cur.meta.skills) {
      const s = all.find((x) => x.name === n);
      const row = document.createElement("div");
      row.className = "erow";
      row.innerHTML = `<button class="ename" type="button">${ico("sigma")}<span></span></button>${s ? statusBadge(s.status) : ""}<button class="icon-btn x" type="button" title="${esc(LE.unlink)}">${ico("close")}</button>`;
      row.querySelector(".ename span").textContent = n;
      row.querySelector(".ename").disabled = !s;
      row.querySelector(".ename").addEventListener("click", async () => { await flushSave(); openEngine(n, cur.name); });
      row.querySelector(".x").addEventListener("click", async () => {
        try { cur = await ctx.call("skill_link", { name: n, card: cur.name, on: false }); drawEngines(); } catch (e) { ctx.toast(e.message, "error"); }
      });
      list_.append(row);
    }
    box.querySelector(".newe").onclick = async () => {
      const v = await ask(LE.newName, "", LE.newNote);
      if (!v) return;
      try {
        await flushSave();
        await ctx.call("skill_new", { name: v, card: cur.name });
        copy(LE.askText(v, [cur.name]));
        openEngine(v, cur.name);
      } catch (e) { ctx.toast(e.message, "error"); }
    };
    const others = all.filter((s) => !cur.meta.skills.includes(s.name));
    box.querySelector(".linke").hidden = !others.length;
    box.querySelector(".linke").onclick = (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      ctx.contextMenu(others.map((s) => ({ label: s.name, icon: ico("sigma"), onClick: async () => {
        try { cur = await ctx.call("skill_link", { name: s.name, card: cur.name, on: true }); drawEngines(); } catch (er) { ctx.toast(er.message, "error"); }
      } })), r.left, r.bottom + 4);
    };
  }

  function drawBody() {
    const md = cardView.querySelector(".md");
    const body = cur.body.trim();
    const hasText = /^##[^\n]*\n+(?!##)\S/m.test(body + "\n");
    if (!hasText) { md.innerHTML = `<p class="lab-none">${esc(L.bodyEmpty)}</p>`; return; }
    // 見出し（##）と段落だけを素直に見せる。式などはそのまま（きちんと読むときは「カードを開く」でビューアへ）
    md.innerHTML = body.split(/\n(?=##\s)/).map((sec) => {
      const [h, ...rest] = sec.split("\n");
      const t = rest.join("\n").trim();
      return /^##\s/.test(h) ? `<h5>${esc(h.replace(/^##\s+/, ""))}</h5>${t ? `<p>${esc(t)}</p>` : ""}` : `<p>${esc(sec)}</p>`;
    }).join("");
  }

  function collect() {
    const v = (k) => cardView.querySelector(`[data-k=${k}]`).value;
    return { title: v("title").trim(), authors: v("authors").split("\n").map((s) => s.trim()).filter(Boolean),
      year: v("year").trim(), doi: v("doi").trim(), tags: v("tags").split(/[,，、]/).map((s) => s.trim()).filter(Boolean) };
  }
  let saving = null;
  async function saveNow(meta) {
    clearTimeout(saveTimer);
    if (!cur) return;
    const name = cur.name;
    saving = ctx.call("save_meta", { name, meta })
      .then(async (r) => { if (cur?.name === name) { cur = r; sig = (await ctx.call("poll")).sig; } })
      .catch((e) => ctx.toast(e.message, "error"))
      .finally(() => { saving = null; });
    return saving;
  }
  async function flushSave() {
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = 0; if (cur) await saveNow(collect()); }
    if (saving) await saving;
  }

  async function renameCard() {
    const v = await ask(L.newName, cur.name);
    if (!v || v === cur.name) return;
    try {
      await flushSave();
      cur = await ctx.call("rename", { name: cur.name, new: v });
      drawCard();
      ctx.toast(L.renamed);
    } catch (e) { ctx.toast(e.message, "error"); }
  }

  function ask(title, value, note = "") {
    return new Promise((resolve) => {
      const dlg = document.createElement("div");
      dlg.className = "lab-dlg";
      dlg.innerHTML = `<div class="lab-dlg-box small" role="dialog" aria-modal="true"><h3></h3><input type="text">
        <div class="btn-row"><span class="sp"></span><button class="btn cancel">${esc(L.cancel)}</button><button class="btn primary go">OK</button></div></div>`;
      dlg.querySelector("h3").textContent = title;
      if (note) dlg.querySelector("h3").insertAdjacentHTML("afterend", `<p class="note">${esc(note)}</p>`);
      const inp = dlg.querySelector("input");
      inp.value = value;
      const done = (v) => { dlg.remove(); resolve(v); };
      dlg.querySelector(".cancel").addEventListener("click", () => done(null));
      dlg.querySelector(".go").addEventListener("click", () => done(inp.value.trim()));
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.isComposing) done(inp.value.trim());
        if (e.key === "Escape") done(null);
      });
      document.body.append(dlg);
      inp.focus();
      inp.select();
    });
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); ctx.toast(L.copied); } catch { ctx.toast(text, "info", 10000); }
  }

  // 外（Claude・フォルダ窓）で変わったら読み直す
  setInterval(async () => {
    if (document.hidden || saving || saveTimer) return;
    try {
      const r = await ctx.call("poll");
      if (r.sig === sig) return;
      sig = r.sig;
      if (eng) {
        eng.reload();
      } else if (cur) {
        const before = cur.mtime;
        try { cur = await ctx.call("card", { name: cur.name }); } catch { return showHome(); }
        if (cur.mtime !== before) { drawCard(true); ctx.toast(L.reloaded); } else drawEngines();
      } else {
        await refresh();
      }
    } catch { /* 次の回にまた見る */ }
  }, 2000);

  await refresh();
}
