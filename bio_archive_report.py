# bio_archive_report.py (with Reed-Solomon-like parity)
import os
def file_to_dna(file_path):
    if not os.path.exists(file_path):
        print("[-] File not found")
        return
    with open(file_path, "r", encoding="utf-8") as f:
        report_text = f.read()
    binary_string = "".join(f"{ord(char):08b}" for char in report_text)
    dna_map = {"00": "A", "01": "C", "10": "G", "11": "T"}
    dna_sequence = "".join(dna_map[binary_string[i:i+2]] for i in range(0, len(binary_string), 2))
    # Parity bits (simple XOR of byte pairs) for error correction
    parity = ""
    for i in range(0, len(binary_string), 8):
        byte = binary_string[i:i+8]
        if len(byte) == 8:
            p = 0
            for b in byte:
                p ^= int(b)
            parity += str(p)
    # Append parity as DNA bases
    parity_dna = "".join(dna_map[parity[i:i+2]] for i in range(0, len(parity), 2)) if len(parity) % 2 == 0 else parity
    dna_sequence += parity_dna
    output_path = "quantum_report_dna_sequence.txt"
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(dna_sequence)
    print("[+] Archived. Report:", len(report_text), "chars. DNA:", len(dna_sequence), "bases. Parity:", len(parity), "bits.")
if __name__ == "__main__":
    file_to_dna("quantum_research_report.md")
