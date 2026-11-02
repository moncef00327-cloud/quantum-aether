# File: run_ghz_relay.py
# دائرة GHZ: كيوبرت السطح (Q0) + كيوبرت الترحيل الوسيط (Q1) + كيوبرت الباطن (Q2)
# الكيوبرت الوسيط يعمل كمحطة ترحيل: تُقاس كيوبرتات الطرفين من خلال ترابطها به
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

# 1. بناء الدائرة: 3 كيوبرت و3 بت كلاسيكي
# Q0 = مستشعر السطح | Q1 = محطة الترحيل الأرضية الوسيطة | Q2 = أثير باطن الأرض
qc = QuantumCircuit(3, 3)

# 2. بوابة هادامارد على كيوبرت السطح لفتح التراكب
qc.h(0)

# 3. CNOT من السطح إلى محطة الترحيل (نشر التشابك إلى الطبقة الوسيطة)
qc.cx(0, 1)

# 4. CNOT من محطة الترحيل إلى الباطن (إكمال سلسلة الرنين حتى العمق)
qc.cx(1, 2)

# 5. قياس الكيوبرتات الثلاثة وتحويلها لبتات كلاسيكية
qc.measure([0, 1, 2], [0, 1, 2])

print("شكل دائرة الترحيل الكمومية (GHZ):")
print(qc.draw())

# 6. إعداد المحاكي وتشغيله لـ 1024 لقطة
simulator = AerSimulator()
compiled_circuit = transpile(qc, simulator)
job = simulator.run(compiled_circuit, shots=1024)
result = job.result()
counts = result.get_counts()

print("\nنتائج قياس التردد المشتبك (السطح + الترحيل + الباطن):")
print(counts)

# 7. حفظ الرسم البياني للنتائج
fig = plot_histogram(counts)
fig.savefig("ghz_relay_histogram.png", dpi=150, bbox_inches="tight")
print("\nتم حفظ المخطط البياني في: ghz_relay_histogram.png")
