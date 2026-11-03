# File: dna_encode.py
# ترميز نص/بيانات رقمية إلى سلسلة DNA (A,C,G,T) وفك الترميز، مع تصحيح أخطاء Reed-Solomon.
# الترميز: كل بايت UTF-8 = 4 قواعد، 00->A, 01->C, 10->G, 11->T (البت الأعلى أولاً).
#
# ملاحظة علمية: هذا ترميز رقمي يحاكي تخزين البيانات في DNA؛ السلسلة الناتجة نص
# ولم تُصنَّع جزيئياً. استبدال قاعدة واحدة يُتلف بايتاً واحداً فيصححه Reed-Solomon،
# أما الإدراج/الحذف (indels) فيُفسد المحاذاة ولا يُصحَّح بهذه الطريقة.
import struct
import zlib

from reedsolo import ReedSolomonError, RSCodec

BITS_TO_BASE = {"00": "A", "01": "C", "10": "G", "11": "T"}
BASE_TO_BITS = {v: k for k, v in BITS_TO_BASE.items()}

_BYTE_TO_BASES = ["".join(BITS_TO_BASE[f"{i:08b}"[j:j + 2]] for j in range(0, 8, 2)) for i in range(256)]
_BASES_TO_BYTE = {bases: i for i, bases in enumerate(_BYTE_TO_BASES)}

# صيغة الأرشيف v1: ترويسة (MAGIC, الإصدار, طول البيانات, CRC32) + البيانات،
# والكل محمي بـ RS(255,223): يصحح حتى 16 بايتاً تالفاً في كل كتلة من 255 بايت.
MAGIC = b"QDNA"
FORMAT_VERSION = 1
RS_NSYM = 32
_HEADER = struct.Struct(">4sBII")


def bytes_to_dna(data: bytes) -> str:
    return "".join(_BYTE_TO_BASES[b] for b in data)


def dna_to_bytes(dna: str) -> bytes:
    bases = "".join(dna.split()).upper()
    invalid = set(bases) - set(BASE_TO_BITS)
    if invalid:
        raise ValueError(f"محارف ليست قواعد DNA: {''.join(sorted(invalid))}")
    if len(bases) % 4:
        raise ValueError("طول السلسلة ليس من مضاعفات 4 (قاعدة ناقصة أو زائدة)")
    return bytes(_BASES_TO_BYTE[bases[i:i + 4]] for i in range(0, len(bases), 4))


def encode(text: str) -> str:
    return bytes_to_dna(text.encode("utf-8"))


def decode(dna: str) -> str:
    return dna_to_bytes(dna).decode("utf-8")


def archive(data: bytes) -> str:
    header = _HEADER.pack(MAGIC, FORMAT_VERSION, len(data), zlib.crc32(data))
    protected = RSCodec(RS_NSYM).encode(header + data)
    return bytes_to_dna(bytes(protected))


def restore(dna: str) -> bytes:
    raw = dna_to_bytes(dna)
    try:
        decoded, _, _ = RSCodec(RS_NSYM).decode(raw)
    except ReedSolomonError as exc:
        raise ValueError(f"الأخطاء تتجاوز قدرة التصحيح: {exc}") from exc
    magic, version, length, crc = _HEADER.unpack_from(decoded)
    if magic != MAGIC or version != FORMAT_VERSION:
        raise ValueError("ليست أرشيف QDNA v1")
    data = bytes(decoded[_HEADER.size:_HEADER.size + length])
    if len(data) != length or zlib.crc32(data) != crc:
        raise ValueError("فشل التحقق CRC32 بعد التصحيح")
    return data


def sequence_stats(dna: str) -> dict:
    bases = "".join(dna.split()).upper()
    longest = run = 0
    previous = ""
    for base in bases:
        run = run + 1 if base == previous else 1
        longest = max(longest, run)
        previous = base
    gc = sum(1 for b in bases if b in "GC")
    return {
        "bases": len(bases),
        "gc_percent": round(gc * 100 / len(bases), 2) if bases else 0.0,
        "max_homopolymer": longest,
    }


if __name__ == "__main__":
    for msg in ["Hello Quantum World", "مرحبا بالعالم الكمومي"]:
        dna = encode(msg)
        back = decode(dna)
        print("النص الأصلي:", msg)
        print("سلسلة DNA:", dna)
        print("الطول (قواعد):", len(dna))
        print("فك التشفير:", back)
        print("تطابق:", back == msg, "\n")
