"""test_lab.py — ラボスケッチの api.py を、Hub を起動せずに確かめる（py -3.14 -m unittest discover -s tests）。
PDF を作る・読むテストは PyMuPDF が入っているときだけ動く。
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(f"hubmod_lab_test_{name}", ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    import pymupdf
except ImportError:
    pymupdf = None


class _Store:
    def __init__(self):
        self.d = {}

    def get(self, scope, key, default=None):
        return self.d.get((scope, key), default)

    def set(self, scope, key, value):
        self.d[(scope, key)] = json.loads(json.dumps(value))


class _Ctx:
    pass


def make_pdf(path, lines, meta=None):
    """lines: [(文字, 大きさ, y)]。日本語は内蔵の CJK 書体で書く。"""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for text, size, y in lines:
        page.insert_text((60, y), text, fontsize=size, fontname="japan" if any(ord(c) > 0x2fff for c in text) else "helv")
    if meta:
        doc.set_metadata(meta)
    doc.save(str(path))
    doc.close()


class CardsTest(unittest.TestCase):
    def setUp(self):
        self.c = _load("cards")

    def test_round_trip_keeps_body_and_unknown_keys(self):
        meta = {"title": "A \"quoted\" title: yes", "authors": ["山田 太郎", "John Smith"], "year": 2024, "doi": "10.1/x",
                "pdf": "a.pdf", "tags": ["スピーカー"], "status": "read", "skills": [], "added": "2026-10-17", "mine": "keep"}
        body = "\n## 要約\n本文 --- そのまま\n"
        m, b = self.c.parse(self.c.dump(meta, body))
        self.assertEqual(m, meta)
        self.assertEqual(b, body.lstrip("\n"))

    def test_reads_what_claude_might_write(self):
        text = ("---\ntitle: Plain title without quotes  # comment\nauthors:\n  - Smith, J.\n  - 'Lee, K.'\n"
                "tags: [a, \"b, c\", 'd']\nyear: 2021\nstatus: CITE\n---\n## Summary\nhi\n")
        m, b = self.c.parse(text)
        self.assertEqual(m["title"], "Plain title without quotes")
        self.assertEqual(m["authors"], ["Smith, J.", "Lee, K."])
        self.assertEqual(m["tags"], ["a", "b, c", "d"])
        self.assertEqual(self.c.normalize(m)["status"], "cite")
        self.assertEqual(self.c.filled(b), ["Summary"])

    def test_bad_line_says_where(self):
        with self.assertRaisesRegex(self.c.CardError, "3 行目"):
            self.c.parse("---\ntitle: \"x\"\n  nested: oops\n---\n")

    def test_no_front_matter(self):
        m, b = self.c.parse("# just markdown\n")
        self.assertEqual((m, b), ({}, "# just markdown\n"))


class BiblioTest(unittest.TestCase):
    def setUp(self):
        self.b = _load("biblio")

    def test_guess_english(self):
        lines = [{"text": "Journal of the Acoustical Society 155 (2024)", "size": 8, "y": .03},
                 {"text": "Diffraction Loss at the Edge", "size": 18, "y": .12},
                 {"text": "of Loudspeaker Baffles", "size": 18, "y": .15},
                 {"text": "John A. Smith1,2, Akiko Tanaka2 and K. Lee*", "size": 11, "y": .2},
                 {"text": "1 Department of Physics, Some University", "size": 9, "y": .23},
                 {"text": "Received 3 May 2023; published 1 Feb 2024", "size": 8, "y": .9},
                 {"text": "https://doi.org/10.1121/10.0024567.", "size": 8, "y": .92}]
        g = self.b.guess(lines, {"title": "Microsoft Word - draft.docx", "creationDate": "D:20230101"})
        self.assertEqual(g["title"], "Diffraction Loss at the Edge of Loudspeaker Baffles")
        self.assertEqual(g["authors"], ["John A. Smith", "Akiko Tanaka", "K. Lee"])
        self.assertEqual(g["year"], 2024)
        self.assertEqual(g["doi"], "10.1121/10.0024567")
        self.assertEqual(self.b.propose_name(g, "x"), "2024_Smith_DiffractionLossEdge")

    def test_guess_japanese(self):
        lines = [{"text": "スピーカーの バッフルステップ補正", "size": 16, "y": .1},
                 {"text": "山田 太郎・鈴木 花子", "size": 10.5, "y": .15},
                 {"text": "日本音響学会誌 2022", "size": 8, "y": .95}]
        g = self.b.guess(lines, {})
        self.assertEqual(g["title"], "スピーカーのバッフルステップ補正")
        self.assertEqual(g["authors"], ["山田 太郎", "鈴木 花子"])
        self.assertEqual(g["year"], 2022)
        self.assertEqual(self.b.propose_name(g, "x"), "2022_山田_スピーカーのバッフルステ")

    def test_unknown_falls_back_to_file_name(self):
        self.assertEqual(self.b.propose_name({"title": "", "authors": [], "year": ""}, "scan001"), "scan001")


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.api = _load("api")
        self.tmp = Path(tempfile.mkdtemp())
        ctx = _Ctx()
        ctx.store, ctx.data_dir, ctx.config = _Store(), self.tmp / "data", {}
        ctx.host = _Ctx()
        ctx.host.config = {"modules": {"folders": {"root": str(self.tmp / "registries")}}}
        self.api.setup(ctx)
        self.out = self.tmp / "downloads"
        self.out.mkdir()

    def _fake_pdf(self, name, data=b"%PDF-1.4\n%fake\n"):
        p = self.out / name
        p.write_bytes(data)
        return p

    def test_folder_and_guide(self):
        st = self.api.state()
        f = Path(st["folder"])
        self.assertEqual(f, self.tmp / "registries" / "Lab Sketch")
        self.assertTrue((f / "LAB_FORMAT.md").is_file())
        self.assertTrue((f / "papers").is_dir())
        self.assertEqual((st["cards"], st["pending"], st["mode"]), ([], [], "copy"))

    def test_import_copy_never_overwrites_and_keeps_body(self):
        src = self._fake_pdf("smith.pdf")
        it = {"path": str(src), "name": "2024_Smith_X", "title": "X", "authors": "Smith, J.; Lee, K.", "year": "2024", "tags": "a, b"}
        r1 = self.api.import_pdfs([it], "copy", "en")
        r2 = self.api.import_pdfs([it], "copy", "ja")
        self.assertEqual(r1["made"] + r2["made"], ["2024_Smith_X", "2024_Smith_X (2)"])
        self.assertTrue(src.exists())                                  # コピーなので元は残る
        c = self.api.card("2024_Smith_X")
        self.assertEqual((c["meta"]["authors"], c["meta"]["tags"]), (["Smith, J.", "Lee, K."], ["a", "b"]))
        self.assertEqual(c["meta"]["year"], 2024)
        self.assertEqual(c["meta"]["pdf"], "2024_Smith_X.pdf")
        self.assertEqual(c["meta"]["source"], "smith.pdf")
        self.assertIn("## Summary", c["body"])
        self.assertIn("## 要約", self.api.card("2024_Smith_X (2)")["body"])
        # 本文を Claude が書いた後に、画面から状態を変えても本文は残る
        p = Path(c["path"])
        p.write_text(p.read_text(encoding="utf-8").replace("## Summary\n", "## Summary\nIt works.\n"), encoding="utf-8")
        c = self.api.save_meta("2024_Smith_X", {"status": "cite", "tags": ["x"], "pdf": "evil.pdf"})
        self.assertIn("It works.", c["body"])
        self.assertEqual((c["meta"]["status"], c["meta"]["tags"], c["meta"]["pdf"]), ("cite", ["x"], "2024_Smith_X.pdf"))
        rows = {r["name"]: r for r in self.api.state()["cards"]}
        self.assertEqual(rows["2024_Smith_X"]["filled"], ["Summary"])

    def test_move_and_pending_inside_folder(self):
        src = self._fake_pdf("m.pdf")
        self.api.import_pdfs([{"path": str(src), "name": "moved"}], "move")
        self.assertFalse(src.exists())
        # フォルダ窓に直接落とした PDF はカード無しとして出て、取り込むと papers へ移る
        dropped = Path(self.api.state()["folder"]) / "dropped.pdf"
        dropped.write_bytes(b"%PDF-1.4\n%other\n")
        st = self.api.state()
        self.assertEqual([p["file"] for p in st["pending"]], ["dropped.pdf"])
        self.api.import_pdfs([{"path": str(dropped), "name": "dropped"}], "copy")
        self.assertFalse(dropped.exists())
        self.assertEqual(self.api.state()["pending"], [])

    def test_export_refs_never_overwrites(self):
        src = self._fake_pdf("r.pdf")
        self.api.import_pdfs([{"path": str(src), "name": "a", "title": "Edge Effects", "authors": ["J. Smith"], "year": "2020"}], "copy")
        r1 = self.api.export_refs(["a"], "bib")
        r2 = self.api.export_refs(["a"], "bib")
        self.assertEqual((r1["file"], r2["file"]), ("references.bib", "references (2).bib"))
        self.assertIn("@article{smith2020edge,", r1["text"])
        self.assertTrue(self.api.export_refs(["a"], "md", "en")["text"].startswith("# References"))
        with self.assertRaises(self.api.LabError):
            self.api.export_refs([], "bib")

    def test_japanese_names(self):
        src = self._fake_pdf("山田の論文.pdf")
        self.api.import_pdfs([{"path": str(src), "name": "2022_山田_バッフル段差"}], "copy")
        c = self.api.card("2022_山田_バッフル段差")
        self.assertTrue(c["pdfPath"].endswith("2022_山田_バッフル段差.pdf"))
        self.assertEqual(c["meta"]["source"], "山田の論文.pdf")
        r = self.api.rename("2022_山田_バッフル段差", "2022_山田_段差")
        self.assertEqual(r["meta"]["pdf"], "2022_山田_段差.pdf")
        self.assertTrue(Path(r["pdfPath"]).is_file())
        self.assertEqual([x["name"] for x in self.api.state()["cards"]], ["2022_山田_段差"])

    def test_rejects_bad_input(self):
        txt = self.out / "a.txt"
        txt.write_text("x")
        self.assertEqual(self.api.inspect([str(txt)])["items"], [])
        notpdf = self.out / "b.pdf"
        notpdf.write_bytes(b"hello")
        self.assertIn("PDF として読めません", self.api.inspect([str(notpdf)])["skipped"][0])
        src = self._fake_pdf("c.pdf")
        r = self.api.import_pdfs([{"path": str(src), "name": "..\\evil"}], "copy")
        self.assertEqual(r["made"], [])
        with self.assertRaises(self.api.LabError):
            self.api.card("../x")

    def test_duplicate_detected(self):
        src = self._fake_pdf("d.pdf")
        self.api.import_pdfs([{"path": str(src), "name": "first"}], "copy")
        self.assertEqual(self.api.inspect([str(src)])["items"][0]["dup"], "first")

    def test_poll_changes_when_card_changes(self):
        src = self._fake_pdf("e.pdf")
        self.api.import_pdfs([{"path": str(src), "name": "e"}], "copy")
        a = self.api.poll()["sig"]
        p = Path(self.api.card("e")["path"])
        import os, time
        os.utime(p, (time.time() + 5, time.time() + 5))
        self.assertNotEqual(a, self.api.poll()["sig"])

    @unittest.skipIf(pymupdf is None, "PyMuPDF が無い")
    def test_inspect_real_pdfs(self):
        en = self.out / "download (3).pdf"
        make_pdf(en, [("J. Audio Eng. Soc. Vol. 72", 8, 30), ("Baffle Step Compensation", 20, 110),
                      ("for Small Loudspeakers", 20, 136), ("John Smith, Akiko Tanaka", 11, 170),
                      ("(c) 2024 AES. doi:10.17743/jaes.2024.0001", 8, 800)])
        ja = self.out / "論文.pdf"
        make_pdf(ja, [("小型スピーカーのバッフルステップ補正", 18, 110), ("山田 太郎、鈴木 花子", 11, 150),
                      ("2021年 日本音響学会 受付 2021年3月", 8, 800)])
        items = {i["file"]: i for i in self.api.inspect([str(en), str(ja)])["items"]}
        e, j = items["download (3).pdf"], items["論文.pdf"]
        self.assertEqual(e["title"], "Baffle Step Compensation for Small Loudspeakers")
        self.assertEqual(e["authors"], ["John Smith", "Akiko Tanaka"])
        self.assertEqual((e["year"], e["doi"]), (2024, "10.17743/jaes.2024.0001"))
        self.assertEqual(e["name"], "2024_Smith_BaffleStepCompensation")
        self.assertEqual(j["title"], "小型スピーカーのバッフルステップ補正")
        self.assertEqual(j["authors"], ["山田 太郎", "鈴木 花子"])
        self.assertEqual(j["year"], 2021)
        r = self.api.import_pdfs([e, j], "copy", "ja")
        self.assertEqual(sorted(r["made"]), sorted([e["name"], j["name"]]))


class SkillTest(ApiTest.__bases__[0]):
    """skill: ひな形 → 検査 → 検算 → zip。"""

    def setUp(self):
        ApiTest.setUp(self)
        src = self.out / "p.pdf"
        src.write_bytes(b"%PDF-1.4\n%x\n")
        self.api.import_pdfs([{"path": str(src), "name": "2024_Smith_X"}], "copy")

    def _fill(self, d):
        p = d / "SKILL.md"
        p.write_text(p.read_text(encoding="utf-8").replace('"（いつ使うか。例: 〇〇の値を、著者 年 の式で計算・検査するとき）"',
                                                          '"閉じた管の共鳴周波数を計算・検査するとき"'), encoding="utf-8")

    def test_template_to_zip(self):
        v = self.api.skill_new("pipe-res", "2024_Smith_X")
        d = Path(v["path"])
        self.assertEqual(self.api.card("2024_Smith_X")["meta"]["skills"], ["pipe-res"])
        self.assertTrue(any("description" in e for e in v["lint"]["errors"]))       # ひな形のままでは検算しない
        self.assertEqual(self.api.skill_verify("pipe-res")["stage"], "lint")
        self._fill(d)
        r = self.api.skill_verify("pipe-res")
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["status"]["verified"])
        self.assertEqual(self.api.skills()["skills"][0]["papers"][0]["name"], "2024_Smith_X")
        z = Path(self.api.skill_zip("pipe-res")["path"])
        import zipfile
        names = zipfile.ZipFile(z).namelist()
        self.assertIn("pipe-res/SKILL.md", names)
        self.assertIn("pipe-res/scripts/calc.py", names)
        self.assertFalse(any(".verified" in n or "__pycache__" in n for n in names))
        self.assertEqual(z.parent.name, "export")
        self.assertEqual(Path(self.api.skill_zip("pipe-res")["path"]).name, "pipe-res (2).zip")   # 上書きしない
        # 検算の後に中身が変わったら zip は作れない
        calc = d / "scripts" / "calc.py"
        calc.write_text(calc.read_text(encoding="utf-8").replace("4.0 * v", "2.0 * v"), encoding="utf-8")
        self.assertFalse(self.api.skill_view("pipe-res")["status"]["verified"])
        with self.assertRaises(self.api.LabError):
            self.api.skill_zip("pipe-res")
        r = self.api.skill_verify("pipe-res")                                        # 式を壊したので合わない
        self.assertFalse(r["ok"])
        self.assertEqual(r["check"]["data"]["summary"]["ng"], 2)
        self.assertTrue(any("2 倍" in c for c in r["check"]["data"]["causes"]))

    def test_dangerous_code_is_not_run(self):
        d = Path(self.api.skill_new("bad-one")["path"])
        self._fill(d)
        calc = d / "scripts" / "calc.py"
        base = calc.read_text(encoding="utf-8")
        for snippet, word in (("import socket\n", "socket"), ("import urllib.request\n", "urllib"),
                              ("import subprocess\n", "subprocess"), ("open('x.txt', 'w')\n", "open()"),
                              ("eval('1')\n", "eval"), ("from pathlib import Path\nPath('x').unlink()\n", "unlink")):
            calc.write_text(snippet + base, encoding="utf-8")
            r = self.api.skill_verify("bad-one")
            self.assertEqual(r["stage"], "lint", snippet)
            self.assertTrue(any(word in e for e in r["errors"]), (snippet, r["errors"]))
        self.assertFalse((d / "x.txt").exists())

    def test_timeout(self):
        d = Path(self.api.skill_new("slow-one")["path"])
        self._fill(d)
        calc = d / "scripts" / "calc.py"
        calc.write_text(calc.read_text(encoding="utf-8").replace("    v, warnings = _read(inputs)", "    while True:\n        pass"), encoding="utf-8")
        self.api.verify.TIMEOUT = 2
        r = self.api.skill_verify("slow-one")
        self.assertFalse(r["ok"])
        self.assertIn("秒", r["calc"]["error"])

    def test_bad_names(self):
        for n in ("Baffle", "baffle_step", "../x", "-a", "a" * 65):
            with self.assertRaises(self.api.LabError):
                self.api.skill_new(n)


class CiteTest(unittest.TestCase):
    def setUp(self):
        self.c = _load("cite")

    def test_keys_and_escape(self):
        ms = [{"title": "Baffle Step & 50% Loss", "authors": ["John Smith", "Akiko Tanaka"], "year": 2024, "doi": "10.1/x_y"},
              {"title": "Baffle Steps Again", "authors": ["Smith, J."], "year": 2024},
              {"title": "小型スピーカーの補正", "authors": ["山田 太郎"], "year": 2021},
              {"title": "", "authors": ["Müller, K."], "year": ""}]
        self.assertEqual(self.c.unique_keys(ms), ["smith2024bafflea", "smith2024baffleb", "ref2021", "muller"])
        b = self.c.bibtex(ms)
        self.assertIn("@article{smith2024bafflea,", b)
        self.assertIn(r"title = {{Baffle Step \& 50\% Loss}}", b)
        self.assertIn("author = {John Smith and Akiko Tanaka}", b)
        self.assertIn("doi = {10.1/x_y}", b)
        self.assertEqual(b.count("{") , b.count("}"))
        md = self.c.reference_list(ms, "ja")
        self.assertIn("- John Smith、Akiko Tanaka (2024). Baffle Step & 50% Loss. https://doi.org/10.1/x_y", md)


if __name__ == "__main__":
    unittest.main()
