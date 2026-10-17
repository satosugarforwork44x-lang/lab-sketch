"""lab/biblio.py — PDF の 1 ページ目と埋め込み情報から、題名・著者・年・DOI を推定する（オフライン）。

・ネットには問い合わせない。推定は外れることがあるので、カードの上で直せる前提
・PDF を開くのは PyMuPDF（AGPL-3.0。同梱しない）。無いときは何も推定しない（ファイル名だけ）
・推定そのもの（guess）は、PDF を開かずに「行の一覧」から行う → テストしやすい
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>{}|\\^`]+)", re.I)
YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20\d\d)(?!\d)")
YEAR_HINT_RE = re.compile(r"(©|\(c\)|copyright|published|received|accepted|available online|発行|受付|受理|掲載)", re.I)
CJK_RE = re.compile(r"[぀-ヿ㐀-鿿]")
BAD_META_TITLE = re.compile(r"(^microsoft\s+word|\.docx?$|\.pdf$|\.tex$|^untitled$|^title$|^layout\s*1$)", re.I)
NOT_TITLE = re.compile(r"(journal|proceedings|vol\.|volume|issn|doi|http|www\.|©|copyright|arxiv|preprint|論文集|学会誌|巻|号|受付|原稿)", re.I)
STOP = {"a", "an", "the", "of", "on", "in", "for", "and", "to", "with", "by", "at", "from", "via", "using", "toward", "towards", "its"}


def has_pymupdf() -> bool:
    try:
        import pymupdf  # noqa: F401
        return True
    except ImportError:
        return False


def read_pdf(path) -> tuple[list[dict], dict]:
    """PDF → (1 ページ目の行 [{text, size, y}], 埋め込み情報)。PyMuPDF が無ければ ImportError。"""
    import pymupdf
    with pymupdf.open(str(path)) as doc:
        meta = dict(doc.metadata or {})
        if doc.page_count == 0:
            return [], meta
        page = doc[0]
        h = page.rect.height or 1
        lines = []
        for block in page.get_text("dict").get("blocks", []):
            for ln in block.get("lines", []):
                spans = [s for s in ln.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                size = max(s.get("size", 0) for s in spans)
                lines.append({"text": text, "size": round(size, 1), "y": ln["bbox"][1] / h})
        return lines, meta


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "")).strip()


def _meta_title(meta: dict) -> str:
    t = _clean(meta.get("title", ""))
    return t if len(t) >= 8 and not BAD_META_TITLE.search(t) else ""


def _meta_authors(meta: dict) -> list[str]:
    a = _clean(meta.get("author", ""))
    if not a or len(a) > 300 or re.search(r"(^user$|^admin|^owner$|microsoft|adobe)", a, re.I):
        return []
    return split_authors(a)


def split_authors(s: str) -> list[str]:
    """'A. Smith, B. Jones and C. Lee' / '山田太郎・鈴木花子' → 名前の一覧。上付きの印やメールは外す。"""
    s = _clean(s)
    s = re.sub(r"\S+@\S+", " ", s)
    s = re.sub(r"[*†‡§¶#]+|\(\d+(,\d+)*\)", " ", s)
    s = re.sub(r"(?<=[A-Za-z぀-鿿])\d+(,\d+)*", "", s)      # 名前の後ろの所属番号（Smith1,2）
    parts = re.split(r",|;|、|・|，|\band\b|&|\s{2,}", s)
    out = []
    for p in parts:
        p = p.strip(" .,-")
        if not p or len(p) > 60 or re.search(r"\d", p):
            continue
        if CJK_RE.search(p) or 1 <= len(p.split()) <= 5:
            out.append(p)
    return out[:30]


def _looks_like_authors(text: str) -> bool:
    if NOT_TITLE.search(text) or re.search(r"(university|institute|department|大学|研究所|株式会社|学部|研究科)", text, re.I):
        return False
    names = split_authors(text)
    return bool(names) and all(len(n) <= 40 for n in names)


def guess(lines: list[dict], meta: dict | None = None) -> dict:
    """1 ページ目の行と埋め込み情報 → {title, authors, year, doi}（分からない所は空）。"""
    meta = meta or {}
    text = "\n".join(_clean(l["text"]) for l in lines)

    # 題名: ページの上 6 割で、いちばん大きい字の行（続く同じ大きさの行もつなぐ）
    title, title_end = "", -1
    cand = [(i, l) for i, l in enumerate(lines) if l.get("y", 0) < 0.6 and len(_clean(l["text"])) >= 4
            and not NOT_TITLE.search(l["text"]) and not re.fullmatch(r"[\d\s.\-]+", l["text"])]
    if cand:
        big = max(l["size"] for _, l in cand)
        idx = [i for i, l in cand if abs(l["size"] - big) <= 0.6]
        start = idx[0]
        parts, j = [], start
        while j < len(lines) and abs(lines[j]["size"] - big) <= 0.6 and len(parts) < 4:
            parts.append(_clean(lines[j]["text"]))
            j += 1
        title, title_end = " ".join(parts), j
        if CJK_RE.search(title):
            title = re.sub(r"(?<=[぀-鿿]) (?=[぀-鿿])", "", title)
    mt = _meta_title(meta)
    if mt and (not title or len(title) < 8):
        title = mt

    # 著者: 題名のすぐ後の 1〜3 行
    authors: list[str] = []
    if title_end >= 0:
        for l in lines[title_end:title_end + 3]:
            t = _clean(l["text"])
            if _looks_like_authors(t):
                authors += split_authors(t)
            elif authors:
                break
    if not authors:
        authors = _meta_authors(meta)

    # DOI: 本文 → 埋め込み情報
    doi = ""
    for src in (text, " ".join(str(meta.get(k, "")) for k in ("subject", "keywords", "title"))):
        m = DOI_RE.search(src.replace("doi.org/", " ").replace("DOI:", " ").replace("doi:", " "))
        if m:
            doi = m.group(1).rstrip(".,;)]")
            break

    # 年: 「©」「Published」などの近く → 埋め込みの作成日 → 本文に多い年
    this = date.today().year + 1
    year = ""
    for ln in text.splitlines():
        if YEAR_HINT_RE.search(ln):
            ys = [int(y) for y in YEAR_RE.findall(ln) if int(y) <= this]
            if ys:
                year = max(ys)
                break
    if not year:
        m = re.match(r"D:(\d{4})", str(meta.get("creationDate", "")))
        if m and 1950 <= int(m.group(1)) <= this:
            year = int(m.group(1))
    if not year:
        ys = [int(y) for y in YEAR_RE.findall(text) if int(y) <= this]
        if ys:
            year = max(set(ys), key=ys.count)
    return {"title": title, "authors": authors, "year": year, "doi": doi}


def family(name: str) -> str:
    """第一著者の名字。'John A. Smith' → Smith、'Smith, J.' → Smith、'山田 太郎' → 山田。"""
    n = _clean(name)
    if not n:
        return ""
    if "," in n:
        return n.split(",")[0].strip()
    if CJK_RE.search(n):
        return n.split(" ")[0][:4] if " " in n else n[:2]
    return n.split(" ")[-1].strip(".")


def short_title(title: str, n_words: int = 3) -> str:
    t = _clean(title)
    if not t:
        return ""
    if CJK_RE.search(t):
        t = re.sub(r"[\s　「」『』（）()【】:：,，、。・\-—―~〜!?！？]", "", t)
        return t[:12]
    words = [w for w in re.findall(r"[A-Za-z0-9]+", t) if w.lower() not in STOP]
    return "".join(w[:1].upper() + w[1:] for w in words[:n_words])


def propose_name(g: dict, fallback: str) -> str:
    """年_第一著者_短い題名。分からない所は飛ばす。何も無ければ元の名前。"""
    parts = [str(g.get("year") or ""), family((g.get("authors") or [""])[0]), short_title(g.get("title", ""))]
    name = "_".join(p for p in parts if p)
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "", name).strip(" .")
    return name[:70] if len([p for p in parts if p]) >= 2 else fallback
