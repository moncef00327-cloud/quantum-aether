# ghz_fidelity.py
# قياس دقة حالة GHZ الفعلية (fidelity)، لا مجرد نسبة 000+111.
#
# مُسقِط حالة GHZ يساوي متوسط عناصر مجموعة مُثبِّتاتها الثمانية، لذلك:
#   F = (1/8) * (1 + <ZZI> + <IZZ> + <ZIZ> + <XXX> - <XYY> - <YXY> - <YYX>)
# نسبة P(000)+P(111) تعطي حداً أعلى فقط: خليط كلاسيكي 50/50 من 000 و111 يحقق 100% فيها
# بينما دقته الفعلية 50%، لأن التماسك بين الحالتين لا يظهر إلا في القياس بالأساسين X وY.
#
# الاستخدام:
#   python ghz_fidelity.py                 # محاكاة مثالية
#   python ghz_fidelity.py --noisy         # محاكاة بنموذج ضوضاء ibm_marrakesh (FakeMarrakesh)
#   python ghz_fidelity.py --hardware      # معالج IBM حقيقي (يستهلك من حصتك)
import argparse
import datetime as dt
import json
import os

from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

STABILIZERS = [("III", 1), ("ZZI", 1), ("IZZ", 1), ("ZIZ", 1), ("XXX", 1), ("XYY", -1), ("YXY", -1), ("YYX", -1)]


def ghz_circuit():
    # نفس دائرة real_quantum.py: السطح Q0 -> محطة الترحيل Q2 -> الباطن Q1
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 2)
    qc.cx(2, 1)
    return qc


def fidelity_from_expectations(values):
    return sum(sign * value for (_, sign), value in zip(STABILIZERS, values)) / 8


def _estimate(estimator, backend=None):
    circuit = ghz_circuit()
    observables = [SparsePauliOp(label) for label, _ in STABILIZERS]
    if backend is not None:
        circuit = generate_preset_pass_manager(backend=backend, optimization_level=1).run(circuit)
        observables = [obs.apply_layout(circuit.layout) for obs in observables]
    job = estimator.run([(circuit, observables)])
    return [float(v) for v in job.result()[0].data.evs], job


def run(mode):
    job_id = None
    note = None
    if mode == "ideal":
        from qiskit.primitives import StatevectorEstimator
        values, _ = _estimate(StatevectorEstimator())
        backend_name = "statevector (ideal)"
    elif mode == "noisy":
        from qiskit_aer import AerSimulator
        from qiskit_aer.primitives import EstimatorV2 as AerEstimator
        from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
        backend = AerSimulator.from_backend(FakeMarrakesh())
        values, _ = _estimate(AerEstimator.from_backend(backend), backend)
        backend_name = "AerSimulator + FakeMarrakesh noise model"
        note = ("gate and decoherence noise only: the Estimator computes expectation values directly, "
                "so readout errors are not included")
    else:
        from qiskit_ibm_runtime import EstimatorV2, QiskitRuntimeService
        service = QiskitRuntimeService()
        backend = service.least_busy(operational=True, simulator=False, min_num_qubits=3)
        print(f"المعالج: {backend.name}")
        values, job = _estimate(EstimatorV2(mode=backend), backend)
        backend_name, job_id = backend.name, job.job_id()

    fidelity = fidelity_from_expectations(values)
    print(f"\nالخلفية: {backend_name}")
    for (label, sign), value in zip(STABILIZERS, values):
        print(f"  {'-' if sign < 0 else '+'}<{label}> = {value:+.4f}")
    print(f"\nدقة حالة GHZ (fidelity) = {fidelity * 100:.2f}%")
    print("(أكبر من 50% يثبت تشابكاً حقيقياً بين الكيوبتات الثلاثة)")
    if note:
        print(f"تنبيه: {note}")

    os.makedirs("results", exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join("results", f"fidelity_ghz_{mode}_{job_id or stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"mode": mode, "backend": backend_name, "job_id": job_id, "date": stamp, "note": note,
                   "expectations": dict(zip([s[0] for s in STABILIZERS], values)), "fidelity": fidelity}, f, indent=2)
    print(f"حُفظت النتيجة في {path}")
    return fidelity


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GHZ state fidelity via stabilizer expectation values")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--noisy", action="store_true", help="simulate with the ibm_marrakesh noise model")
    group.add_argument("--hardware", action="store_true", help="run on a real IBM backend (uses your quota)")
    args = parser.parse_args()
    run("noisy" if args.noisy else "hardware" if args.hardware else "ideal")
