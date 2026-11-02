# File: export_quantum_data.py
# توليد وتصدير بيانات توزيع GHZ (المحاكاة المثالية + الأداء الحقيقي المتوقع) إلى CSV
# ---------------------------------------------------------------------------
# البيانات "الحقيقية المتوقعة" هي تقدير إحصائي مبني على معاملات خطأ معالجات
# IBM النموذجية (دقة بوابة CNOT ~99%، تراكب حراري ~1-2%)، وتُستبدل تلقائياً
# بالقراءات الفعلية بعد تشغيل real_quantum.py على العتاد.
# ---------------------------------------------------------------------------
import csv
import math
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

SHOTS = 1024
STATES = ['000', '001', '010', '011', '100', '101', '110', '111']

# ---------- 1) القراءة المرجعية: المحاكي المثالي ----------
qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 2)   # السطح -> محطة الترحيل
qc.cx(2, 1)   # محطة الترحيل -> الباطن
qc.measure([0, 1, 2], [0, 1, 2])

sim = AerSimulator()
counts_ideal = sim.run(transpile(qc, sim), shots=SHOTS).result().get_counts()
# تعبئة الحالات غير الظاهرة بصفر لضمان تساوي طول الجدول
counts_ideal = {s: counts_ideal.get(s, 0) for s in STATES}

# ---------- 2) القراءة المتوقعة: العتاد الحقيقي مع الضوضاء ----------
# نموذج ضوضاء بسيط: احتمال انقلاب بت واحد لكل كيوبرت (Bit-flip) أثناء القياس
import random
random.seed(42)
NOISE_P = 0.02  # ~2% خطأ قياس لكل كيوبرت

counts_real = {s: 0 for s in STATES}
for state, n in counts_ideal.items():
    for _ in range(n):
        bits = list(state)
        for i in range(3):
            if random.random() < NOISE_P:
                bits[i] = '1' if bits[i] == '0' else '0'
        counts_real[''.join(bits)] += 1

# ---------- 3) حساب مقاييس الجودة (Fidelity للـ GHZ) ----------
fidelity = (counts_real['000'] + counts_real['111']) / SHOTS
noise_total = SHOTS - counts_real['000'] - counts_real['111']

# ---------- 4) التصدير إلى CSV ----------
with open('quantum_data.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['الحالة الكمية', 'المحاكي المثالي (عدد)', 'المحاكي %',
                     'العتاد الحقيقي المتوقع (عدد)', 'العتاد %'])
    for s in STATES:
        writer.writerow([
            s,
            counts_ideal[s], f"{counts_ideal[s]/SHOTS*100:.1f}",
            counts_real[s],  f"{counts_real[s]/SHOTS*100:.1f}",
        ])
    writer.writerow([])
    writer.writerow(['عدد اللقطات (Shots)', SHOTS])
    writer.writerow(['إخلاص الحالة GHZ المتوقع', f"{fidelity*100:.1f}%"])
    writer.writerow(['إجمالي الضوضاء المتوقعة', f"{noise_total} لقطة ({noise_total/SHOTS*100:.1f}%)"])

print("تم إنشاء الملف: quantum_data.csv")
print(f"إخلاص الحالة GHZ المتوقع: {fidelity*100:.1f}%")
print(f"إجمالي الضوضاء المتوقعة: {noise_total/SHOTS*100:.1f}%")


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
                "ملخص مقدم من المستخدم؛ counts الخام غير متاحة للتحقق",
            ])

    print(f"تم إنشاء ملف قنوات النقل: {output_path}")


if __name__ == "__main__":
    export_teleportation_channels()
