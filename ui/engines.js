// lab/ui/engines.js — エンジン（skill）の一覧と 1 つの skill の画面（中身を見る → 検算 → zip）。
// ・Claude が書いたコードを PC で動かすので、検算は利用者が中身を見てから押す（初回は確かめる）
// ・検算の後に中身が変わったら、zip はもう一度検算するまで作れない（api 側でも止める）
import { icons } from "/ui/js/icons.js";

const EN = (document.documentElement.lang || navigator.language || "ja").startsWith("en");
export const LE = EN ? {
  tabPapers: "Papers", tabEngines: "Engines", none: "No engines yet. Open a paper and use “New engine…”.",
  papers: (n) => `${n} paper${n > 1 ? "s" : ""}`, noPaper: "No paper linked",
  verified: (at) => `Checked ${at}`, changed: "Changed since the check", unverified: "Not checked yet",
  errors: (n) => `${n} problem${n > 1 ? "s" : ""}`, back: "Back", run: "Run the check", zip: "Make the zip",
  zipTip: "Only after the check passes. Upload the zip in Claude: Customize > Skills", ask: "Ask Claude",
  askText: (s, papers) => `In Hub's “Lab Sketch” folder, write the engine skills/${s}/ following the skill rules in LAB_FORMAT.md: SKILL.md, scripts/calc.py and examples.json (scripts/check.py can stay as it is). Use the equations and values in ${papers.length ? papers.map((p) => `papers/${p}.md and its PDF`).join(", ") : "the paper"}. Take examples.json values from the paper's tables or figures.`,
  folder: "Show in Explorer", lint: "Checks before running", noProblems: "No problems found", warns: "Notes",
  confirmTitle: "Run code written by Claude on this PC?", confirm: "The check runs scripts/calc.py and scripts/check.py in a separate Python process inside the skill folder, for at most 10 seconds. Network, files and commands are blocked by a code scan before running — this prevents accidents, it is not a full sandbox. Run it after reading the code.",
  ok: "Run", cancel: "Cancel", result: "Result", pass: "All values match", fail: "Some values don't match",
  case: "Case", out: "Output", exp: "Paper", act: "Engine", diff: "Diff", causes: "Possible causes", stderr: "Messages",
  stage: { lint: "Stopped before running (see the checks)", calc: "calc.py failed", check: "check.py failed" },
  zipped: (f) => `Made ${f}`, zipNote: "Upload it in claude.ai or the desktop app: Customize > Skills, then turn it on.",
  newEngine: "New engine…", newName: "Engine name (lowercase letters, digits, hyphens — e.g. baffle-step)", newNote: "One engine per topic. It can cite several papers.",
  engines: "Engines (calculate & check)", link: "Use an existing engine…", unlink: "Remove from this paper", copied: "Copied", ms: (n) => `${n} ms`,
} : {
  tabPapers: "論文", tabEngines: "エンジン", none: "まだありません。論文のカードを開いて「エンジンを作る…」から作れます。",
  papers: (n) => `論文 ${n}`, noPaper: "論文につながっていません",
  verified: (at) => `検算済み ${at}`, changed: "検算の後に変わりました", unverified: "まだ検算していません",
  errors: (n) => `問題 ${n}`, back: "戻る", run: "検算する", zip: "zip を作る",
  zipTip: "検算が通ってから。zip は Claude の Customize > Skills でアップロード", ask: "Claude に頼む",
  askText: (s, papers) => `Hub のフォルダ窓「Lab Sketch」で、LAB_FORMAT.md の skill の決まりに従って skills/${s}/ のエンジンを書いてください（SKILL.md・scripts/calc.py・examples.json。scripts/check.py はそのまま使えます）。式と値は ${papers.length ? papers.map((p) => `papers/${p}.md とその PDF`).join("、") : "論文"} から。examples.json の値は論文の表・図から取ってください。`,
  folder: "エクスプローラーで見る", lint: "動かす前の検査", noProblems: "問題は見つかりませんでした", warns: "気をつけること",
  confirmTitle: "Claude が書いたコードを、この PC で動かします", confirm: "検算は scripts/calc.py と scripts/check.py を、skill のフォルダの中で別の Python として最大 10 秒動かします。ネット・ファイルの書き換え・外部コマンドは、動かす前にコードを調べて止めます。ただしこれは「うっかり」を防ぐ物で、完全な隔離ではありません。中身を読んでから動かしてください。",
  ok: "動かす", cancel: "やめる", result: "結果", pass: "すべて合いました", fail: "合わない値があります",
  case: "条件", out: "出力", exp: "論文", act: "エンジン", diff: "差", causes: "考えられる原因", stderr: "メッセージ",
  stage: { lint: "動かす前に止めました（検査を見てください）", calc: "calc.py が動きませんでした", check: "check.py が動きませんでした" },
  zipped: (f) => `${f} を作りました`, zipNote: "claude.ai かデスクトップアプリの Customize > Skills でアップロードして、オンにしてください。",
  newEngine: "エンジンを作る…", newName: "エンジンの名前（英小文字・数字・ハイフン。例: baffle-step）", newNote: "テーマごとに 1 つ。複数の論文を出典にできます。",
  engines: "エンジン（計算・検査）", link: "作ってあるエンジンをつなぐ…", unlink: "この論文から外す", copied: "コピーしました", ms: (n) => `${n} ms`,
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ico = (n) => icons[n] || "";
const fmt = (v) => (v == null ? "—" : Math.abs(v) >= 1e5 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(3) : +v.toPrecision(5));

export function statusBadge(st) {
  if (st.verified) return `<span class="lab-badge ok">${ico("verify")}${esc(LE.verified(st.at))}</span>`;
  if (st.changed) return `<span class="lab-badge warn">${esc(LE.changed)}</span>`;
  return `<span class="lab-badge">${esc(LE.unverified)}</span>`;
}

/** 一覧（container に描く）。open(name) で 1 つの skill を開く */
export async function drawEngineList(ctx, container, open) {
  const r = await ctx.call("skills");
  container.replaceChildren();
  if (!r.skills.length) { container.innerHTML = `<p class="lab-none">${esc(LE.none)}</p>`; return r; }
  for (const s of r.skills) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "lab-row lab-erow";
    b.innerHTML = `<span class="eico">${ico("sigma")}</span><span class="main"><span class="t"></span><span class="m"></span></span><span class="side"></span>`;
    b.querySelector(".t").textContent = s.name;
    b.querySelector(".m").textContent = s.description || "—";
    b.querySelector(".side").innerHTML = `${statusBadge(s.status)}<span class="info">${s.errors ? `<span class="warn">${esc(LE.errors(s.errors))}</span>` : ""}${esc(s.papers.length ? LE.papers(s.papers.length) : LE.noPaper)}</span>`;
    b.addEventListener("click", () => open(s.name));
    container.append(b);
  }
  return r;
}

/** 1 つの skill の画面。back() で戻る。返り値の reload() で読み直す */
export function engineView(ctx, view, name, { back, copy, openCard }) {
  let data = null, tab = "SKILL.md", last = null, zipped = null;
  const askedOk = new Set();          // この窓で「動かす」を了承した中身（ハッシュの代わりに中身の文字）

  async function load() {
    data = await ctx.call("skill_view", { name });
    if (!data.files.some((f) => f.path === tab)) tab = data.files[0]?.path || "";
    draw();
  }

  function draw() {
    const st = data.status, li = data.lint;
    view.innerHTML = `<div class="lab-cbar">
        <button class="btn back">‹ ${esc(LE.back)}</button>
        <span class="lab-ename">${ico("sigma")}<b></b></span>${statusBadge(st)}<span class="sp"></span>
        <button class="btn ask">${esc(LE.ask)}</button>
        <button class="btn primary run">${ico("verify")}<span>${esc(LE.run)}</span></button>
        <button class="btn zip" title="${esc(LE.zipTip)}">${esc(LE.zip)}</button>
        <button class="icon-btn more" title="${esc(LE.folder)}">${ico("reveal")}</button>
      </div>
      <div class="lab-ebody">
        <div class="lab-eside">
          <p class="desc"></p>
          <div class="papers"></div>
          <h4>${esc(LE.lint)}</h4><div class="lint"></div>
          <div class="res"></div>
        </div>
        <div class="lab-code">
          <div class="tabs" role="tablist"></div>
          <pre class="code"><code></code></pre>
        </div>
      </div>`;
    const q = (s) => view.querySelector(s);
    q(".lab-ename b").textContent = data.name;
    q(".desc").textContent = data.description || "—";
    for (const p of data.papers) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = p.title;
      b.title = p.name;
      b.addEventListener("click", () => openCard(p.name));
      q(".papers").append(b);
    }
    q(".lint").innerHTML = (li.errors.length || li.warnings.length)
      ? li.errors.map((e) => `<p class="err">${esc(e)}</p>`).join("") + li.warnings.map((w) => `<p class="wn">${esc(w)}</p>`).join("")
      : `<p class="okl">${esc(LE.noProblems)}</p>`;
    for (const f of data.files) {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(f.path === tab));
      b.textContent = f.path;
      b.addEventListener("click", () => { tab = f.path; draw(); });
      q(".tabs").append(b);
    }
    const f = data.files.find((x) => x.path === tab);
    q(".code code").textContent = f?.text ?? "";
    q(".back").addEventListener("click", back);
    q(".ask").addEventListener("click", () => copy(LE.askText(data.name, data.papers.map((p) => p.name))));
    q(".run").disabled = li.errors.length > 0;
    q(".run").addEventListener("click", run);
    q(".zip").disabled = !st.verified;
    q(".zip").addEventListener("click", makeZip);
    q(".more").addEventListener("click", () => ctx.host.revealPath(data.path).catch((e) => ctx.toast(e.message, "error")));
    drawResult();
  }

  function drawResult() {
    const box = view.querySelector(".res");
    if (!box) return;
    let h = "";
    if (last) {
      const c = last.check?.data;
      h += `<h4>${esc(LE.result)}</h4>`;
      if (last.stage !== "done") h += `<p class="err">${esc(LE.stage[last.stage] || last.stage)}</p>`;
      const errRun = last.check?.error || last.calc?.error || last.calc?.data?.error || last.check?.data?.error;
      if (errRun) h += `<p class="err">${esc(errRun)}</p>`;
      if (c && c.results) {
        h += `<p class="${c.pass ? "okl" : "err"}">${esc(c.pass ? LE.pass : LE.fail)}（${c.summary.ok}/${c.summary.total}）${last.check.ms != null ? ` · ${esc(LE.ms(last.check.ms))}` : ""}</p>`;
        h += `<table class="lab-tab"><thead><tr><th>${esc(LE.case)}</th><th>${esc(LE.out)}</th><th>${esc(LE.exp)}</th><th>${esc(LE.act)}</th><th>${esc(LE.diff)}</th><th></th></tr></thead><tbody>`;
        for (const r of c.results) {
          h += r.error
            ? `<tr class="ng"><td>${esc(r.case)}</td><td colspan="4">${esc(r.error)}</td><td>✕</td></tr>`
            : `<tr class="${r.ok ? "" : "ng"}"><td>${esc(r.case)}</td><td>${esc(r.output)}<small> ${esc(r.unit)}</small></td><td>${fmt(r.expected)}</td><td>${fmt(r.actual)}</td><td>${r.diff_pct == null ? fmt(r.diff) : `${r.diff_pct >= 0 ? "+" : ""}${r.diff_pct.toFixed(2)}%`}</td><td>${r.ok ? "✓" : "✕"}</td></tr>`;
        }
        h += "</tbody></table>";
        if (c.causes?.length) h += `<h5>${esc(LE.causes)}</h5>${c.causes.map((x) => `<p class="wn">${esc(x)}</p>`).join("")}`;
      }
      const se = [last.calc?.stderr, last.check?.stderr, last.calc?.stdout, last.check?.stdout].filter(Boolean).join("\n").trim();
      if (se) h += `<h5>${esc(LE.stderr)}</h5><pre class="se">${esc(se)}</pre>`;
    }
    if (zipped) h += `<p class="okl">${esc(LE.zipped(zipped.file))}</p><p class="note">${esc(LE.zipNote)}</p><button class="btn showzip">${esc(LE.folder)}</button>`;
    box.innerHTML = h;
    box.querySelector(".showzip")?.addEventListener("click", () => ctx.host.revealPath(zipped.path));
  }

  async function run() {
    const key = data.files.map((f) => f.path + "\0" + (f.text ?? f.size)).join("\0");
    if (!askedOk.has(key) && !(await confirmRun())) return;
    askedOk.add(key);
    const btn = view.querySelector(".run");
    btn.disabled = true;
    try {
      last = await ctx.call("skill_verify", { name });
      zipped = null;
      await load();
    } catch (e) { ctx.toast(e.message, "error"); btn.disabled = false; }
  }

  async function makeZip() {
    try {
      zipped = await ctx.call("skill_zip", { name });
      ctx.toast(LE.zipped(zipped.file));
      drawResult();
    } catch (e) { ctx.toast(e.message, "error"); }
  }

  function confirmRun() {
    return new Promise((resolve) => {
      const dlg = document.createElement("div");
      dlg.className = "lab-dlg";
      dlg.innerHTML = `<div class="lab-dlg-box small" role="alertdialog" aria-modal="true"><h3>${esc(LE.confirmTitle)}</h3><p class="note">${esc(LE.confirm)}</p>
        <div class="btn-row"><span class="sp"></span><button class="btn cancel">${esc(LE.cancel)}</button><button class="btn primary go">${esc(LE.ok)}</button></div></div>`;
      const done = (v) => { dlg.remove(); resolve(v); };
      dlg.querySelector(".cancel").addEventListener("click", () => done(false));
      dlg.querySelector(".go").addEventListener("click", () => done(true));
      dlg.addEventListener("keydown", (e) => { if (e.key === "Escape") done(false); });
      document.body.append(dlg);
      dlg.querySelector(".cancel").focus();
    });
  }

  load().catch((e) => { ctx.toast(e.message, "error"); back(); });
  return { reload: () => load().catch(() => back()), name };
}
