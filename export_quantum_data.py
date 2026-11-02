# File: export_quantum_data.py
# تصدير توزيع GHZ إلى quantum_data.csv: المحاكي المثالي + نموذج ضوضاء بسيط + نتائج العتاد الحقيقي
# (من results/ghz_*.json إن وُجدت)، وتصدير ملخص قنوات النقل إلى quantum_teleportation_channels.csv.
# ---------------------------------------------------------------------------
# نموذج الضوضاء هنا تقدير مبسط (انقلاب بت 2% لكل كيوبت عند القياس) وليس قياساً.
# "نسبة الإشغال" P(000)+P(111) حد أعلى لدقة حالة GHZ؛ الدقة الفعلية يقيسها ghz_fidelity.py.
# ---------------------------------------------------------------------------
import csv
import glob
import json
import math
import random

from qiskit import QuantumCircuit, transpile

SHOTS = 1024
STATES = ['000', '001', '010', '011', '100', '101', '110', '111']
NOISE_P = 0.02  # ~2% خطأ قياس لكل كيوبت


def ideal_counts():
    from qiskit_aer import AerSimulator

    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 2)   # السطح -> محطة الترحيل
    qc.cx(2, 1)   # محطة الترحيل -> الباطن
    qc.measure([0, 1, 2], [0, 1, 2])
    sim = AerSimulator()
    counts = sim.run(transpile(qc, sim), shots=SHOTS, seed_simulator=42).result().get_counts()
    return {s: counts.get(s, 0) for s in STATES}


def bitflip_noise_counts(ideal, p=NOISE_P, seed=42):
    rng = random.Random(seed)
    noisy = {s: 0 for s in STATES}
    for state, n in ideal.items():
        for _ in range(n):
            bits = ['1' if (b == '0') == (rng.random() < p) else '0' for b in state]
            noisy[''.join(bits)] += 1
    return noisy


def latest_hardware_result():
    records = []
    for path in glob.glob("results/ghz_*.json"):
        with open(path, encoding="utf-8") as f:
            records.append(json.load(f))
    return max(records, key=lambda r: r.get("date", "")) if records else None


def population(counts):
    total = sum(counts.values())
    return (counts.get('000', 0) + counts.get('111', 0)) / total if total else 0.0


def pct(counts, state):
    total = sum(counts.values())
    return f"{counts.get(state, 0) / total * 100:.1f}" if total else ""


def export_ghz_table(output_path="quantum_data.csv"):
    ideal = ideal_counts()
    noisy = bitflip_noise_counts(ideal)
    hardware = latest_hardware_result()
    hw_counts = {s: hardware["counts"].get(s, 0) for s in STATES} if hardware else {}

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['الحالة الكمية', 'المحاكي المثالي (عدد)', 'المحاكي %',
                         'نموذج ضوضاء 2% (عدد)', 'نموذج الضوضاء %',
                         'العتاد الحقيقي (عدد)', 'العتاد الحقيقي %'])
        for s in STATES:
            writer.writerow([s, ideal[s], pct(ideal, s), noisy[s], pct(noisy, s),
                             hw_counts.get(s, ''), pct(hw_counts, s)])
        writer.writerow([])
        writer.writerow(['عدد اللقطات (Shots)', SHOTS])
        writer.writerow(['نسبة الإشغال P(000)+P(111) - المحاكي المثالي', f"{population(ideal) * 100:.2f}%"])
        writer.writerow(['نسبة الإشغال P(000)+P(111) - نموذج الضوضاء', f"{population(noisy) * 100:.2f}%"])
        if hardware:
            writer.writerow(['نسبة الإشغال P(000)+P(111) - العتاد الحقيقي', f"{population(hw_counts) * 100:.2f}%"])
            writer.writerow(['مصدر بيانات العتاد', f"{hardware['backend']} / {hardware['job_id']}"])
        writer.writerow(['ملاحظة', 'نسبة الإشغال حد أعلى لدقة حالة GHZ؛ الدقة الفعلية: python ghz_fidelity.py'])

    print(f"تم إنشاء الملف: {output_path}")
    if hardware:
        print(f"العتاد الحقيقي ({hardware['backend']}): نسبة الإشغال {population(hw_counts) * 100:.2f}%")


def export_teleportation_channels():
    # These summary values were supplied by the user; raw counts were not provided.
    measurements = [
        ("π/3", math.pi / 3, 74.71),
        ("π/4", math.pi / 4, 86.72),
        ("2π/5", 2 * math.pi / 5, 64.94),
    ]
    shots = 1024
    output_path = "quantum_teleportation_channels.csv"

    with open(output_path, "w", newline="", encoding="utf-8-sig") as output_file:
        writer = csv.writer(output_file)
        writer.writerow([
            "القناة",
            "الزاوية (rad)",
            "احتمال Q2=0 المقاس (%)",
            "احتمال Q2=0 النظري (%)",
            "الانحراف المطلق (نقطة مئوية)",
            "الخطأ المعياري (نقطة مئوية)",
            "عدد اللقطات",
            "مصدر البيانات",
        ])

        for label, angle, measured_zero_pct in measurements:
            measured_zero = measured_zero_pct / 100
            theoretical_zero = math.cos(angle / 2) ** 2
            standard_error = math.sqrt(
                measured_zero * (1 - measured_zero) / shots
            )
            deviation = abs(measured_zero - theoretical_zero)

            writer.writerow([
                label,
                f"{angle:.6f}",
                f"{measured_zero_pct:.2f}",
                f"{theoretical_zero * 100:.2f}",
                f"{deviation * 100:.2f}",
                f"{standard_error * 100:.2f}",
                shots,
                "ملخص مقدم من المستخدم (محاكي)؛ counts الخام غير متاحة للتحقق",
            ])

    print(f"تم إنشاء ملف قنوات النقل: {output_path}")


if __name__ == "__main__":
    export_ghz_table()
    export_teleportation_channels()
