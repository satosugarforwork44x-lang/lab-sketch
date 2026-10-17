"""lab/api.py — ラボスケッチ（Lab Sketch）。論文 1 本 = md のカード 1 枚。

・置き場所: フォルダ窓の置き場所の下の「Lab Sketch」（フォルダ窓として Claude と共有できる）
    LAB_FORMAT.md   … Claude 向けの説明書（同梱の版と違えば置き直す）
    papers/         … <名前>.pdf と <名前>.md（カード）
    skills/         … 計算・検査エンジンの skill（次の段階）
    export/         … 登録用の zip・BibTeX（次の段階）
・書誌情報はオフラインで推定（biblio.py）。カードの上で直せる
・カードの本文（要約・手法…）は Claude が書く。ここは front matter だけを書き換える。本文はそのまま残す
・上書きしない: 同じ名前があれば 'name (2)'
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

_ctx = None

FOLDER_NAME = "Lab Sketch"
GUIDE = "LAB_FORMAT.md"
PAPERS, SKILLS, EXPORT = "papers", "skills", "export"
MODES = ("copy", "move")
NAME_RE = re.compile(r"^[^\\/:*?\"<>|\x00-\x1f]{1,80}$")
EDITABLE = ("title", "authors", "year", "doi", "tags", "status")
PDF_MAX = 500 * 1024 * 1024


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"hubmod_lab_{name}", Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cards = _load("cards")
biblio = _load("biblio")
verify = _load("verify")
TEMPLATE = Path(__file__).with_name("skill_template")
TEXT_EXTS = {".md", ".py", ".json", ".csv", ".txt"}


class LabError(Exception):
    pass


def setup(ctx):
    global _ctx
    _ctx = ctx


# ---------- 置き場所 ----------
def _folder() -> Path:
    """既定は フォルダ窓の置き場所\\Lab Sketch。設定 modules.lab.folder で変えられる。"""
    p = (_ctx.config or {}).get("folder")
    if not p:
        root = ((getattr(_ctx.host, "config", None) or {}).get("modules") or {}).get("folders", {}).get("root") or "~/Hub"
        p = Path(root).expanduser() / FOLDER_NAME
    f = Path(p).expanduser()
    (f / PAPERS).mkdir(parents=True, exist_ok=True)
    guide, ours = f / GUIDE, Path(__file__).with_name(GUIDE)
    try:
        if ours.is_file() and (not guide.is_file() or guide.read_bytes() != ours.read_bytes()):
            _write_atomic(guide, ours.read_text(encoding="utf-8"))
    except OSError:
        pass
    return f


def _papers() -> Path:
    return _folder() / PAPERS


def _check_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.match(name) or name.strip() != name or name in (".", "..") or name.endswith("."):
        raise LabError(f"名前に使えない文字があります: {name}")
    return name


def _card_path(name: str) -> Path:
    p = _papers() / f"{_check_name(name)}.md"
    if not p.is_file():
        raise LabError(f"カードが見つかりません: {name}")
    return p


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".lab-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _free_stem(stem: str) -> str:
    """papers/ に <stem>.md も <stem>.pdf も無い名前。あれば 'stem (2)'。"""
    stem = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", stem).strip(" .")[:76] or "paper"
    d = _papers()
    taken = lambda s: (d / f"{s}.md").exists() or (d / f"{s}.pdf").exists()
    if not taken(stem):
        return stem
    for i in range(2, 1000):
        if not taken(f"{stem} ({i})"):
            return f"{stem} ({i})"
    raise LabError("同じ名前のファイルが多すぎます")


def _pip() -> str:
    exe = sys.executable.replace("pythonw.exe", "python.exe")
    return f'"{exe}" -m pip install --user pymupdf'


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- 一覧 ----------
def _parse(p: Path) -> tuple[dict, str]:
    try:
        return cards.parse(p.read_text(encoding="utf-8"))
    except cards.CardError as e:
        raise LabError(f"{p.name}: {e}")
    except UnicodeDecodeError:
        raise LabError(f"{p.name}: UTF-8 で読めません")


def _row(p: Path) -> dict:
    st = p.stat()
    try:
        meta, body = cards.parse(p.read_text(encoding="utf-8"))
        err = ""
    except (cards.CardError, UnicodeDecodeError) as e:
        meta, body, err = {}, "", str(e)
    m = cards.normalize(meta)
    pdf = (p.parent / m["pdf"]) if m["pdf"] else None
    return {"name": p.stem, "title": m["title"] or p.stem, "authors": m["authors"], "year": m["year"], "doi": m["doi"],
            "tags": m["tags"], "status": m["status"], "skills": m["skills"], "added": m["added"],
            "pdf": m["pdf"], "hasPdf": bool(pdf and pdf.is_file()), "filled": cards.filled(body),
            "mtime": int(st.st_mtime * 1000), "error": err}


def _cards() -> list[dict]:
    rows = [_row(p) for p in _papers().glob("*.md") if not p.name.startswith(".")]
    rows.sort(key=lambda r: (r["added"], r["mtime"]), reverse=True)
    return rows


def _pending(rows: list[dict]) -> list[dict]:
    """カードの無い PDF（フォルダ窓に落とした物・papers に手で入れた物）。"""
    used = {r["pdf"].lower() for r in rows if r["pdf"]}
    out = []
    for d, inside in ((_folder(), False), (_papers(), True)):
        for p in sorted(d.glob("*.pdf")):
            if inside and p.name.lower() in used:
                continue
            out.append({"path": str(p), "file": p.name, "inside": inside})
    return out


def state() -> dict:
    rows = _cards()
    return {"folder": str(_folder()), "papers": str(_papers()), "cards": rows, "pending": _pending(rows),
            "pymupdf": biblio.has_pymupdf(), "pip": _pip(), "mode": _mode(), "statuses": list(cards.STATUSES)}


def poll() -> dict:
    """外（Claude・フォルダ窓）で変わったか。名前と更新時刻の要約を返す。"""
    h = hashlib.sha1()
    f = _folder()
    for d in (f, f / PAPERS):
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in (".md", ".pdf") and p.is_file():
                h.update(f"{p.name}:{p.stat().st_mtime_ns};".encode("utf-8", "surrogatepass"))
    sk = f / SKILLS
    if sk.is_dir():                                   # Claude が skill を書いた・直した
        for p in sorted(sk.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                h.update(f"{p.relative_to(sk).as_posix()}:{p.stat().st_mtime_ns};".encode("utf-8", "surrogatepass"))
    return {"sig": h.hexdigest()}


def _mode() -> str:
    m = _ctx.store.get("lab", "mode", "copy")
    return m if m in MODES else "copy"


def set_mode(mode: str) -> dict:
    if mode not in MODES:
        raise LabError("copy か move")
    _ctx.store.set("lab", "mode", mode)
    return {"mode": mode}


# ---------- 取り込み ----------
def _pdf_arg(path: str) -> Path:
    p = Path(path)
    if p.suffix.lower() != ".pdf":
        raise LabError(f"PDF ではありません: {p.name}")
    if not p.is_file():
        raise LabError(f"見つかりません: {path}")
    if p.stat().st_size > PDF_MAX:
        raise LabError(f"大きすぎます（500MB まで）: {p.name}")
    with open(p, "rb") as f:
        if b"%PDF" not in f.read(1024):
            raise LabError(f"PDF として読めません: {p.name}")
    return p


def _dup_of(p: Path) -> str:
    """同じ中身の PDF がもう papers にあれば、そのカードの名前。"""
    size = p.stat().st_size
    same = [q for q in _papers().glob("*.pdf") if q.stat().st_size == size and q.resolve() != p.resolve()]
    if not same:
        return ""
    h = _sha(p)
    for q in same:
        if _sha(q) == h:
            return q.stem
    return ""


def inspect(paths: list) -> dict:
    """落とした PDF の書誌を推定し、名前を提案する（まだ何も書かない）。"""
    items, skipped = [], []
    has = biblio.has_pymupdf()
    for path in (paths or [])[:200]:
        try:
            p = _pdf_arg(str(path))
        except LabError as e:
            skipped.append(str(e))
            continue
        g, warn = {"title": "", "authors": [], "year": "", "doi": ""}, ""
        if has:
            try:
                g = biblio.guess(*biblio.read_pdf(p))
            except Exception as e:                       # 壊れた PDF・暗号化など。ファイル名だけで進める
                warn = f"PDF の中が読めませんでした（{type(e).__name__}）"
        name = biblio.propose_name(g, p.stem)
        items.append({"path": str(p), "file": p.name, "name": name, **g,
                      "inside": p.parent.resolve() in (_papers().resolve(), _folder().resolve()),
                      "dup": _dup_of(p), "warn": warn})
    return {"items": items, "skipped": skipped, "pymupdf": has, "pip": _pip()}


def import_pdfs(items: list, mode: str = "", lang: str = "ja") -> dict:
    """inspect の結果（利用者が直した後）からカードを作る。フォルダの中の PDF は移す、外の PDF は mode に従う。"""
    mode = mode if mode in MODES else _mode()
    made, skipped = [], []
    for it in items or []:
        try:
            src = _pdf_arg(str(it.get("path", "")))
            stem = _free_stem(_check_name(str(it.get("name") or src.stem).strip()))
            dst = _papers() / f"{stem}.pdf"
            inside = src.parent.resolve() in (_papers().resolve(), _folder().resolve())
            if inside or mode == "move":
                shutil.move(str(src), dst)
            else:
                shutil.copy2(src, dst)
            meta = {"title": str(it.get("title") or "").strip() or src.stem,
                    "authors": cards.normalize({"authors": it.get("authors", [])})["authors"],
                    "year": cards.normalize({"year": it.get("year", "")})["year"],
                    "doi": str(it.get("doi") or "").strip(), "pdf": dst.name, "source": src.name,
                    "tags": cards.normalize({"tags": it.get("tags", [])})["tags"], "status": "unread", "skills": [],
                    "added": date.today().isoformat()}
            _write_atomic(_papers() / f"{stem}.md", cards.dump(meta, cards.new_body(lang if lang in cards.SECTIONS else "ja")))
            made.append(stem)
        except (LabError, OSError) as e:
            skipped.append(f"{it.get('file') or it.get('path')}: {e}")
    return {"made": made, "skipped": skipped}


# ---------- 1 枚のカード ----------
def card(name: str) -> dict:
    return card_(name)


def card_(name: str) -> dict:
    p = _card_path(name)
    text = p.read_text(encoding="utf-8")
    try:
        meta, body = cards.parse(text)
        err = ""
    except cards.CardError as e:
        meta, body, err = {}, cards.split(text)[1], str(e)
    m = cards.normalize(meta)
    pdf = p.parent / m["pdf"] if m["pdf"] else None
    return {"name": p.stem, "meta": m, "body": body, "error": err, "path": str(p),
            "pdfPath": str(pdf) if pdf and pdf.is_file() else "", "mtime": int(p.stat().st_mtime * 1000)}


def save_meta(name: str, meta: dict) -> dict:
    """front matter の EDITABLE だけを書き換える。本文・知らないキーはそのまま。"""
    p = _card_path(name)
    old, body = _parse(p)
    new = dict(old)
    m = cards.normalize({k: v for k, v in (meta or {}).items() if k in EDITABLE})
    for k in EDITABLE:
        if k in (meta or {}):
            new[k] = m[k]
    _write_atomic(p, cards.dump(new, body))
    return card(name)


def rename(name: str, new: str) -> dict:
    """カードと PDF の名前を一緒に変える（pdf: も直す）。"""
    p = _card_path(name)
    new = _check_name(str(new).strip())
    if new == name:
        return card(name)
    if (p.parent / f"{new}.md").exists() or (p.parent / f"{new}.pdf").exists():
        raise LabError(f"同じ名前があります: {new}")
    meta, body = _parse(p)
    pdf = p.parent / str(meta.get("pdf") or "")
    if meta.get("pdf") and pdf.is_file() and pdf.parent == p.parent:
        pdf.rename(p.parent / f"{new}.pdf")
        meta["pdf"] = f"{new}.pdf"
    _write_atomic(p.parent / f"{new}.md", cards.dump(meta, body))
    p.unlink()
    return card(new)


def reveal(name: str = "") -> dict:
    return {"path": str(_card_path(name)) if name else str(_folder())}


# ---------- skill（計算・検査エンジン） ----------
def _skills_dir() -> Path:
    d = _folder() / SKILLS
    d.mkdir(exist_ok=True)
    return d


def _check_skill(name: str) -> str:
    if not isinstance(name, str) or not verify.NAME_RE.match(name) or len(name) > 64:
        raise LabError(f"skill の名前は英小文字・数字・ハイフンで（例: baffle-step）: {name}")
    return name


def _skill_dir(name: str) -> Path:
    d = _skills_dir() / _check_skill(name)
    if not (d.is_dir() and (d / "SKILL.md").is_file()):
        raise LabError(f"skill が見つかりません: {name}")
    return d


def _users() -> dict[str, list[dict]]:
    """skill 名 → それを使うカード（出典の論文）。"""
    out: dict[str, list[dict]] = {}
    for r in _cards():
        for s in r["skills"]:
            out.setdefault(s, []).append({"name": r["name"], "title": r["title"]})
    return out


def skills() -> dict:
    users = _users()
    rows = []
    for d in sorted(_skills_dir().iterdir()):
        if not (d.is_dir() and (d / "SKILL.md").is_file()):
            continue
        fm = verify._front((d / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        li = verify.lint(d)
        rows.append({"name": d.name, "description": fm.get("description", ""), "papers": users.get(d.name, []),
                     "status": verify.status(d), "errors": len(li["errors"]), "warnings": len(li["warnings"])})
    return {"skills": rows, "folder": str(_skills_dir()), "export": str(_folder() / EXPORT)}


def _link(card: str, skill: str, on: bool = True) -> None:
    p = _card_path(card)
    meta, body = _parse(p)
    have = cards.normalize(meta)["skills"]
    new = (have + [skill]) if on and skill not in have else [s for s in have if s != skill or on]
    if new != have:
        meta["skills"] = new
        _write_atomic(p, cards.dump(meta, body))


def skill_new(name: str, card: str = "") -> dict:
    """ひな形から skills/<名前>/ を作る。card を渡すとそのカードの skills に足す。"""
    d = _skills_dir() / _check_skill(name)
    if d.exists():
        raise LabError(f"同じ名前の skill があります: {name}")
    if card:
        _card_path(card)
    shutil.copytree(TEMPLATE, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ("SKILL.md", "README.md"):
        p = d / f
        _write_atomic(p, p.read_text(encoding="utf-8").replace("__NAME__", name))
    if card:
        _link(card, name, True)
    return skill_view(name)


def skill_link(name: str, card: str, on: bool = True) -> dict:
    _skill_dir(name)
    _link(card, name, bool(on))
    return card_(card)


def skill_view(name: str) -> dict:
    """中身（人が読んでから検算する）・検査の結果・検算の状態。"""
    d = _skill_dir(name)
    files = []
    for p in verify._files(d):
        rel = p.relative_to(d).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace") if p.suffix.lower() in TEXT_EXTS and p.stat().st_size < 400_000 else None
        files.append({"path": rel, "text": text, "size": p.stat().st_size})
    order = {"SKILL.md": 0, "scripts/calc.py": 1, "scripts/check.py": 2, "examples.json": 3, "README.md": 4}
    files.sort(key=lambda f: (order.get(f["path"], 9), f["path"]))
    fm = verify._front((d / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
    return {"name": name, "path": str(d), "description": fm.get("description", ""), "files": files,
            "lint": verify.lint(d), "status": verify.status(d), "papers": _users().get(name, [])}


def skill_verify(name: str) -> dict:
    """検算（利用者が中身を見て押す）。別プロセス・10 秒・skill のフォルダの中で。"""
    d = _skill_dir(name)
    r = verify.run(d)
    r["status"] = verify.status(d)
    return r


def skill_zip(name: str) -> dict:
    d = _skill_dir(name)
    try:
        z = verify.make_zip(d, _folder() / EXPORT)
    except ValueError as e:
        raise LabError(str(e))
    return {"path": str(z), "file": z.name}
