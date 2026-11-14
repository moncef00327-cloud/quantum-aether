# File: run_ghz_relay.py
# دائرة GHZ: كيوبت السطح (Q0) + كيوبت الترحيل الوسيط (Q2) + كيوبت الباطن (Q1)
# نفس ترتيب real_quantum.py وghz_fidelity.py؛ الأسماء تسمية رمزية من إطار المشروع.
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

# 1. بناء الدائرة: 3 كيوبت و3 بت كلاسيكي
# Q0 = مستشعر السطح | Q2 = محطة الترحيل الوسيطة | Q1 = أثير باطن الأرض
qc = QuantumCircuit(3, 3)

# 2. بوابة هادامارد على كيوبت السطح لفتح التراكب
qc.h(0)

# 3. CNOT من السطح إلى محطة الترحيل (نشر التشابك إلى الطبقة الوسيطة)
qc.cx(0, 2)

# 4. CNOT من محطة الترحيل إلى الباطن (إكمال سلسلة التشابك)
qc.cx(2, 1)

# 5. قياس الكيوبتات الثلاثة وتحويلها لبتات كلاسيكية
qc.measure([0, 1, 2], [0, 1, 2])

print("شكل دائرة الترحيل الكمومية (GHZ):")
print(qc.draw())

# 6. إعداد المحاكي وتشغيله لـ 1024 لقطة
simulator = AerSimulator()
compiled_circuit = transpile(qc, simulator)
job = simulator.run(compiled_circuit, shots=1024)
result = job.result()
counts = result.get_counts()

print("\nنتائج القياس (السطح + الترحيل + الباطن):")
print(counts)

# 7. حفظ الرسم البياني للنتائج
fig = plot_histogram(counts)
fig.savefig("ghz_relay_histogram.png", dpi=150, bbox_inches="tight")
print("\nتم حفظ المخطط البياني في: ghz_relay_histogram.png")
