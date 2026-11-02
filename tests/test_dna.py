import pathlib
import unittest

import bio_archive_report
import dna_encode

ROOT = pathlib.Path(__file__).resolve().parent.parent


class EncodeTests(unittest.TestCase):
    def test_known_vector(self):
        # 'A' = 0x41 = 01 00 00 01
        self.assertEqual(dna_encode.encode("A"), "CAAC")

    def test_roundtrip_ascii_arabic_emoji(self):
        for text in ["Hello Quantum World", "مرحبا بالعالم", "café ☕ 📑", ""]:
            with self.subTest(text=text):
                self.assertEqual(dna_encode.decode(dna_encode.encode(text)), text)

    def test_rejects_non_dna_characters(self):
        with self.assertRaises(ValueError):
            dna_encode.dna_to_bytes("ACGT01")

    def test_rejects_truncated_sequence(self):
        with self.assertRaises(ValueError):
            dna_encode.dna_to_bytes("ACG")


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.data = ("تقرير كمومي 📑 GHZ " * 200).encode("utf-8")
        self.dna = dna_encode.archive(self.data)

    def test_restore_exact(self):
        self.assertEqual(dna_encode.restore(self.dna), self.data)

    def test_corrects_base_substitutions(self):
        swap = {"A": "C", "C": "G", "G": "T", "T": "A"}
        damaged = list(self.dna)
        for pos in range(40, 4000, 400):  # 10 substitutions spread across blocks
            damaged[pos] = swap[damaged[pos]]
        self.assertEqual(dna_encode.restore("".join(damaged)), self.data)

    def test_too_many_errors_raise(self):
        damaged = "T" * 1200 + self.dna[1200:]
        with self.assertRaises(ValueError):
            dna_encode.restore(damaged)

    def test_stats(self):
        stats = dna_encode.sequence_stats("AAAGGC")
        self.assertEqual(stats, {"bases": 6, "gc_percent": 50.0, "max_homopolymer": 3})


class ReportArchiveTests(unittest.TestCase):
    def test_project_report_roundtrip(self):
        data = (ROOT / "quantum_research_report.md").read_bytes()
        fasta = bio_archive_report.to_fasta("quantum_research_report.md", data)
        self.assertTrue(fasta.startswith(">quantum_research_report.md"))
        self.assertEqual(bio_archive_report.from_fasta(fasta), data)


if __name__ == "__main__":
    unittest.main()
