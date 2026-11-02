# bio_archive_report.py
# أرشفة تقرير نصي في سلسلة DNA رقمية (صيغة FASTA) مع تصحيح أخطاء Reed-Solomon، واسترجاعه.
#
# الاستخدام:
#   python bio_archive_report.py archive [report.md] [sequence.txt]
#   python bio_archive_report.py restore [sequence.txt] [restored.md]
#   python bio_archive_report.py verify  [report.md] [sequence.txt]
import hashlib
import sys

from dna_encode import RS_NSYM, archive, restore, sequence_stats

DEFAULT_REPORT = "quantum_research_report.md"
DEFAULT_SEQUENCE = "quantum_report_dna_sequence.txt"
LINE_WIDTH = 80


def to_fasta(name: str, data: bytes) -> str:
    dna = archive(data)
    digest = hashlib.sha256(data).hexdigest()
    header = f">{name} | QDNA v1 | RS(255,{255 - RS_NSYM}) | bytes={len(data)} | sha256={digest}"
    lines = [dna[i:i + LINE_WIDTH] for i in range(0, len(dna), LINE_WIDTH)]
    return header + "\n" + "\n".join(lines) + "\n"


def from_fasta(text: str) -> bytes:
    sequence = "".join(line for line in text.splitlines() if not line.startswith(">"))
    return restore(sequence)


def file_to_dna(report_path: str = DEFAULT_REPORT, output_path: str = DEFAULT_SEQUENCE) -> dict:
    with open(report_path, "rb") as f:
        data = f.read()
    fasta = to_fasta(report_path, data)
    with open(output_path, "w", encoding="ascii", newline="\n") as out:
        out.write(fasta)
    stats = sequence_stats("".join(fasta.splitlines()[1:]))
    if from_fasta(fasta) != data:
        raise RuntimeError("فشل التحقق: الأرشيف لا يعيد التقرير الأصلي")
    print(f"[+] أُرشف {report_path}: {len(data.decode('utf-8'))} حرفاً، {len(data)} بايت UTF-8")
    print(f"[+] DNA: {stats['bases']} قاعدة، GC = {stats['gc_percent']}%، أطول تكرار متتالٍ = {stats['max_homopolymer']}")
    print(f"[+] تصحيح الأخطاء: RS(255,{255 - RS_NSYM}) يصحح حتى {RS_NSYM // 2} بايتاً في كل كتلة")
    print(f"[+] تحقق الاسترجاع: مطابق تماماً للأصل -> {output_path}")
    return stats


def dna_to_file(sequence_path: str = DEFAULT_SEQUENCE, output_path: str = "restored_report.md") -> None:
    with open(sequence_path, encoding="ascii") as f:
        data = from_fasta(f.read())
    with open(output_path, "wb") as out:
        out.write(data)
    print(f"[+] استُرجع {len(data)} بايت إلى {output_path}")


def verify(report_path: str = DEFAULT_REPORT, sequence_path: str = DEFAULT_SEQUENCE) -> bool:
    with open(report_path, "rb") as f:
        original = f.read()
    with open(sequence_path, encoding="ascii") as f:
        restored = from_fasta(f.read())
    ok = restored == original
    print("[+] الأرشيف مطابق للتقرير" if ok else "[-] الأرشيف لا يطابق التقرير الحالي")
    return ok


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["archive"]
    if command == "archive":
        file_to_dna(*args)
    elif command == "restore":
        dna_to_file(*args)
    elif command == "verify":
        sys.exit(0 if verify(*args) else 1)
    else:
        sys.exit(__doc__ or "الأوامر: archive | restore | verify")
