# File: dna_encode.py
# تشفير نص/بيانات رقمية إلى سلسلة DNA (A,T,C,G) والفك.
# الترميز: 00->A, 01->C, 10->G, 11->T

BITS_TO_BASE = {"00": "A", "01": "C", "10": "G", "11": "T"}
BASE_TO_BITS = {v: k for k, v in BITS_TO_BASE.items()}

def text_to_bits(text):
    return "".join(f"{ord(ch):08b}" for ch in text)

def bits_to_text(bits):
    chars = [chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8)]
    return "".join(chars)

def encode(text):
    bits = text_to_bits(text)
    if len(bits) % 2:
        bits += "0"
    return "".join(BITS_TO_BASE[bits[i:i+2]] for i in range(0, len(bits), 2))

def decode(dna):
    bits = "".join(BASE_TO_BITS[b] for b in dna.upper() if b in BASE_TO_BITS)
    if len(bits) % 8:
        bits = bits[:-(len(bits) % 8)]
    return bits_to_text(bits)

if __name__ == "__main__":
    msg = "Hello Quantum World"
    dna = encode(msg)
    back = decode(dna)
    print("النص الأصلي:", msg)
    print("سلسلة DNA:", dna)
    print("الطول (قواعد):", len(dna))
    print("فك التشفير:", back)
    print("تطابق:", back == msg)
