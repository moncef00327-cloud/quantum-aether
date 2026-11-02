# File: real_quantum.py
# تشغيل دائرة GHZ (السطح + محطة الترحيل + الباطن) على معالج IBM كمومي حقيقي
# ------------------------------------------------------------------
# قبل التشغيل، عيّن متغير البيئة IBM_API_KEY أو احفظ اعتماد حساب IBM محلياً.
# ------------------------------------------------------------------
import os
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit.visualization import plot_histogram

# 1. استخدم متغير البيئة IBM_API_KEY إن وُجد، وإلا الحساب المحفوظ محلياً.
token = os.environ.get("IBM_API_KEY")
if token:
    service = QiskitRuntimeService(token=token, channel="ibm_quantum_platform")
elif QiskitRuntimeService.saved_accounts():
    service = QiskitRuntimeService()
else:
    raise RuntimeError(
        "لا يوجد مفتاح IBM. عيّن متغير البيئة IBM_API_KEY "
        "أو احفظ بيانات الاعتماد محلياً عبر QiskitRuntimeService.save_account."
    )

# 2. بناء دائرة بـ 3 كيوبرت و3 بت كلاسيكي لقراءة القنوات الثلاث
# Q0: مستشعر السطح | Q1: أثير باطن الأرض | Q2: محطة الترحيل الأرضية الوسيطة
qc = QuantumCircuit(3, 3)

# 3. تفعيل التراكب الموجي على مستشعر السطح (Q0)
qc.h(0)

# 4. تشابك مستشعر السطح (Q0) مع محطة الترحيل الوسيطة (Q2)
qc.cx(0, 2)

# 5. تشابك محطة الترحيل الوسيطة (Q2) مع تردد أثير باطن الأرض (Q1)
qc.cx(2, 1)

# 6. قياس الحالات الثلاث وحفظها في البتات الكلاسيكية المقابلة
qc.measure([0, 1, 2], [0, 1, 2])

# 7. اختيار الحاسوب الكمومي الحقيقي الأقل ازدحاماً (فتعله محاكاة)
backend = service.least_busy(
    operational=True,
    simulator=False,
    min_num_qubits=3,
)
print(f"تم حجز الاتصال على الحاسوب الكمومي الحقيقي: {backend.name}")

# 8. تهيئة الدائرة لتتوافق فيزيائياً مع بنية المعالج المختار
compiled_circuit = transpile(qc, backend=backend)

# 9. إرسال الدائرة السحابية للتشغيل الفعلي على المعالج
sampler = SamplerV2(mode=backend)
job = sampler.run([compiled_circuit], shots=1024)
print(f"تم إرسال الدائرة للمختبر. معرف المهمة: {job.job_id()}")

# 10. انتظار واستخراج النتائج الحقيقية من مختبرات IBM
result = job.result()
pub_result = result[0]
counts = pub_result.data.c.get_counts()

print("\nنتائج قياس التردد الحقيقي عبر المحطة الوسيطة:")
print(counts)

# توليد الرسم البياني النهائي للشبكة الثلاثية
fig = plot_histogram(counts)
fig.savefig("real_quantum_histogram.png", dpi=150, bbox_inches="tight")
print("\nتم حفظ المخطط البياني في: real_quantum_histogram.png")
