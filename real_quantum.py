# File: real_quantum.py
# تشغيل دائرة GHZ (السطح + محطة الترحيل + الباطن) على معالج IBM كمومي حقيقي وحفظ النتائج.
# ------------------------------------------------------------------
# قبل التشغيل، عيّن متغير البيئة IBM_API_KEY أو احفظ اعتماد حساب IBM محلياً (save_ibm_account.py).
#   python real_quantum.py                 # مهمة جديدة على أقل معالج ازدحاماً (يستهلك من حصتك)
#   python real_quantum.py --fetch JOB_ID  # جلب نتائج مهمة سابقة دون أي تشغيل جديد
# النتائج تُحفظ في results/ghz_<backend>_<job>.json وتعرضها صفحة /research في الموقع.
# ------------------------------------------------------------------
import argparse
import json
import os
import sys

from qiskit import QuantumCircuit, transpile
from qiskit.visualization import plot_histogram


def connect():
    from qiskit_ibm_runtime import QiskitRuntimeService

    # 1. استخدم متغير البيئة IBM_API_KEY إن وُجد، وإلا الحساب المحفوظ محلياً.
    token = os.environ.get("IBM_API_KEY", "").strip().strip("\"'{}").strip()
    try:
        if token:
            return QiskitRuntimeService(token=token, channel="ibm_quantum_platform")
        if QiskitRuntimeService.saved_accounts():
            return QiskitRuntimeService()
    except ValueError as exc:
        sys.exit(f"اعتماد IBM غير صالح: {exc}\nأعد حفظ الرمز بـ: python save_ibm_account.py")
    sys.exit("لا يوجد مفتاح IBM. عيّن متغير البيئة IBM_API_KEY أو احفظ الاعتماد عبر save_ibm_account.py")


def ghz_circuit():
    # 2. دائرة بـ 3 كيوبت و3 بت كلاسيكي
    # Q0: مستشعر السطح | Q1: أثير باطن الأرض | Q2: محطة الترحيل الأرضية الوسيطة (تسمية رمزية)
    qc = QuantumCircuit(3, 3)
    qc.h(0)        # 3. تراكب على Q0
    qc.cx(0, 2)    # 4. تشابك Q0 مع محطة الترحيل Q2
    qc.cx(2, 1)    # 5. تشابك Q2 مع Q1
    qc.measure([0, 1, 2], [0, 1, 2])
    return qc


def save_results(backend_name, job_id, counts, date, source):
    os.makedirs("results", exist_ok=True)
    path = os.path.join("results", f"ghz_{backend_name}_{job_id}.json")
    record = {
        "experiment": "GHZ, 3 qubits: h(0), cx(0,2), cx(2,1), measure all",
        "backend": backend_name,
        "job_id": job_id,
        "date": date,
        "shots": sum(counts.values()),
        "counts": dict(sorted(counts.items())),
        "fidelity": None,
        "source": source,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    fig = plot_histogram(counts)
    fig.savefig("real_quantum_histogram.png", dpi=150, bbox_inches="tight")
    print(f"\nحُفظت النتائج في {path} والمخطط في real_quantum_histogram.png")
    population = (counts.get("000", 0) + counts.get("111", 0)) / sum(counts.values())
    print(f"نسبة الإشغال P(000)+P(111) = {population * 100:.2f}% (حد أعلى للدقة؛ للدقة الفعلية: python ghz_fidelity.py --hardware)")


def run_new_job(service):
    # 7. اختيار أقل الحواسيب الكمومية الحقيقية ازدحاماً
    from qiskit_ibm_runtime import SamplerV2

    backend = service.least_busy(operational=True, simulator=False, min_num_qubits=3)
    print(f"تم حجز الاتصال على الحاسوب الكمومي الحقيقي: {backend.name}")
    job = SamplerV2(mode=backend).run([transpile(ghz_circuit(), backend=backend)], shots=1024)
    print(f"تم إرسال الدائرة. معرف المهمة: {job.job_id()} (بانتظار النتائج...)")
    counts = job.result()[0].data.c.get_counts()
    print("\nنتائج القياس:", counts)
    save_results(backend.name, job.job_id(), counts, job.creation_date.date().isoformat(),
                 f"Fetched from IBM Quantum, job {job.job_id()}")


def fetch_job(service, job_id):
    job = service.job(job_id)
    counts = job.result()[0].data.c.get_counts()
    backend_name = job.backend().name
    print(f"المهمة {job_id} على {backend_name}: {counts}")
    save_results(backend_name, job_id, counts, job.creation_date.date().isoformat(),
                 f"Fetched from IBM Quantum, job {job_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run (or fetch) the GHZ circuit on IBM Quantum hardware")
    parser.add_argument("--fetch", metavar="JOB_ID", help="download the results of an existing job instead of running")
    args = parser.parse_args()
    service = connect()
    try:
        fetch_job(service, args.fetch) if args.fetch else run_new_job(service)
    except ValueError as exc:
        sys.exit(f"اعتماد IBM غير صالح: {exc}\nأعد حفظ الرمز بـ: python save_ibm_account.py")
