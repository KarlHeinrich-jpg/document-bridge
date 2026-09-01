from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from app.core import ConversionError, DocumentFormat, detect_format, find_main_file, safe_extract_zip


class CoreTests(unittest.TestCase):
    def test_detects_supported_extensions(self) -> None:
        self.assertEqual(detect_format(Path("paper.docx")), DocumentFormat.DOCX)
        self.assertEqual(detect_format(Path("paper.md")), DocumentFormat.MARKDOWN)
        self.assertEqual(detect_format(Path("paper.tex")), DocumentFormat.LATEX)

    def test_rejects_zip_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive_path = root / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "nope")
            with self.assertRaises(ConversionError):
                safe_extract_zip(archive_path, root / "output")

    def test_prefers_complete_latex_main_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "chapter.tex").write_text("\\section{Only a chapter}", encoding="utf-8")
            (root / "paper.tex").write_text(
                "\\documentclass{article}\\begin{document}Hello\\end{document}",
                encoding="utf-8",
            )
            main, warnings = find_main_file(root, DocumentFormat.LATEX)
            self.assertEqual(main.name, "paper.tex")
            self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()

