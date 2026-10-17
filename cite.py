"""lab/cite.py — 選んだカードから BibTeX と参考文献の一覧（md）を作る。標準ライブラリだけ。

・引用キーは英数字だけ（第一著者の名字 + 年 + 題名の最初の語。例: smith2024baffle）。日本語の名前・題名では ref2021 など
・同じキーは a, b … を付けて分ける
"""
from __future__ import annotations

import re
import unicodedata

STOP = {"a", "an", "the", "of", "on", "in", "for", "and", "to", "with", "by", "at", "from"}


def _ascii(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isascii() and c.isalnum()).lower()


def _family(name: str) -> str:
    n = name.strip()
    if "," in n:
        return n.split(",")[0].strip()
    return n.split()[-1] if n.split() else ""


def key_for(meta: dict) -> str:
    fam = _ascii(_family((meta.get("authors") or [""])[0]))
    year = str(meta.get("year") or "")
    words = [w for w in re.findall(r"[A-Za-z]+", meta.get("title", "")) if w.lower() not in STOP]
    first = _ascii(words[0]) if words else ""
    return (fam or "ref") + year + first


def unique_keys(metas: list[dict]) -> list[str]:
    keys, seen = [], {}
    base = [key_for(m) for m in metas]
    dup = {k for k in base if base.count(k) > 1}
    for k in base:
        if k in dup:
            seen[k] = seen.get(k, 0) + 1
            k = k + "abcdefghijklmnopqrstuvwxyz"[(seen[k] - 1) % 26]
        keys.append(k)
    return keys


def _tex(s: str) -> str:
    """BibTeX の値の中で意味を持つ文字を逃がす。"""
    s = str(s).replace("\\", r"\textbackslash{}")
    s = re.sub(r"([&%$#_])", r"\\\1", s)
    return s.replace("{", r"\{").replace("}", r"\}").replace(r"\textbackslash\{\}", r"\textbackslash{}")


def bibtex(metas: list[dict]) -> str:
    out = []
    for key, m in zip(unique_keys(metas), metas):
        fields = [("title", "{" + _tex(m.get("title", "")) + "}")]       # 大文字を保つため二重の {}
        if m.get("authors"):
            fields.append(("author", " and ".join(_tex(a) for a in m["authors"])))
        if m.get("year"):
            fields.append(("year", str(m["year"])))
        if m.get("doi"):
            fields.append(("doi", m["doi"]))
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
        out.append(f"@article{{{key},\n{body}\n}}")
    return "\n\n".join(out) + "\n"


def reference_list(metas: list[dict], lang: str = "ja") -> str:
    """著者 (年). 題名. doi — 年・著者の順に並べる。"""
    def line(m):
        a = m.get("authors") or []
        who = ("、" if lang == "ja" else ", ").join(a) if a else ("（著者不明）" if lang == "ja" else "(unknown)")
        y = f" ({m['year']})" if m.get("year") else ""
        doi = f" https://doi.org/{m['doi']}" if m.get("doi") else ""
        return f"- {who}{y}. {m.get('title', '')}.{doi}"
    ms = sorted(metas, key=lambda m: ((m.get("authors") or [""])[0].lower(), str(m.get("year") or "")))
    head = "# 参考文献\n\n" if lang == "ja" else "# References\n\n"
    return head + "\n".join(line(m) for m in ms) + "\n"
