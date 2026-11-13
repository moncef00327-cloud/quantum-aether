# بروتوكول نقل حالة كيوبت باستخدام التشابك والاتصال الكلاسيكي
#
# الاستخدام:
#   python quantum_teleportation.py              # المحاكي، بدوائر ديناميكية (if_test)
#   python quantum_teleportation.py --deferred   # المحاكي، بالقياس المؤجل
#   python quantum_teleportation.py --hardware   # معالج IBM حقيقي (يستهلك من حصتك)
import argparse
import json
import os

import numpy as np
from qiskit import QuantumCircuit, transpile

from aether_decoder import AetherDecoder

TEST_ANGLES = [(np.pi / 3, "pi/3"), (np.pi / 4, "pi/4"), (2 * np.pi / 5, "2pi/5")]


def build_teleportation_circuit(angle_value, deferred=False):
    # Q0 يحمل الحالة المراد نقلها، وQ1 وQ2 يشكلان زوج بيل.
    qc = QuantumCircuit(3, 3)

    # جهّز الحالة |psi> = cos(theta/2)|0> + sin(theta/2)|1>.
    qc.ry(angle_value, 0)
    qc.barrier()

    # أنشئ زوج بيل بين Q1 وQ2.
    qc.h(1)
    qc.cx(1, 2)
    qc.barrier()

    # نفّذ قياس بيل بين الحالة وزوج التشابك.
    qc.cx(0, 1)
    qc.h(0)
    qc.barrier()

    if deferred:
        # مبدأ القياس المؤجل: بوابات تحكم كمومية بدل التحكم الكلاسيكي، بنفس الإحصاءات،
        # وتعمل على أي معالج دون الحاجة إلى دوائر ديناميكية.
        qc.cx(1, 2)
        qc.cz(0, 2)
        qc.measure([0, 1, 2], [0, 1, 2])
        return qc

    # نتائج القياس تُستخدم كبتات تحكم كلاسيكية للتصحيح.
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.barrier()
    with qc.if_test((qc.clbits[1], 1)):
        qc.x(2)
    with qc.if_test((qc.clbits[0], 1)):
        qc.z(2)
    qc.barrier()

    # قياس Q2 في الأساس Z؛ هذا يتحقق من الاحتمالات فقط وليس من الحالة كاملة.
    qc.measure(2, 2)
    return qc


def run_on_simulator(circuits, shots):
    from qiskit_aer import AerSimulator

    simulator = AerSimulator()
    compiled = transpile(circuits, simulator)
    result = simulator.run(compiled, shots=shots).result()
    return [result.get_counts(i) for i in range(len(circuits))], "AerSimulator", None


def run_on_hardware(circuits, shots):
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    service = QiskitRuntimeService()
    backend = service.least_busy(operational=True, simulator=False, min_num_qubits=3)
    print(f"المعالج: {backend.name}")
    job = SamplerV2(mode=backend).run(transpile(circuits, backend=backend), shots=shots)
    print(f"معرّف المهمة: {job.job_id()} (بانتظار النتائج...)")
    return [pub.data.c.get_counts() for pub in job.result()], backend.name, job.job_id()


def run_teleportation_protocol(shots=1024, deferred=False, hardware=False):
    if hardware:
        deferred = True
    circuits = [build_teleportation_circuit(angle, deferred) for angle, _ in TEST_ANGLES]
    mode = "قياس مؤجل" if deferred else "دوائر ديناميكية"
    print(f"اختبار نقل الحالة ({mode}) باستخدام {shots} لقطة لكل زاوية.")
    runner = run_on_hardware if hardware else run_on_simulator
    all_counts, backend_name, job_id = runner(circuits, shots)

    analyses = []
    for (angle, name), counts in zip(TEST_ANGLES, all_counts):
        print(f"\nالزاوية {name} ({angle:.6f} rad) — القياسات الخام (c2 c1 c0): {counts}")
        analysis = AetherDecoder.analyze_teleportation_counts(counts, angle, backend_name)
        analyses.append({"angle": name, "counts": counts, **analysis})

    if hardware:
        os.makedirs("results", exist_ok=True)
        path = os.path.join("results", f"teleportation_{backend_name}_{job_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"backend": backend_name, "job_id": job_id, "shots": shots, "analyses": analyses}, f, indent=2)
        print(f"\nحُفظت النتائج في {path}")

    print("\nملاحظة: هذه المقارنة تقيس احتمالات أساس Z فقط؛ لا تكفي وحدها لإثبات نقل حالة كمومية عامة أو قياس الوفاء الكامل.")
    return analyses


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantum teleportation test")
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--deferred", action="store_true", help="use deferred measurement instead of if_test")
    parser.add_argument("--hardware", action="store_true", help="run on a real IBM backend (uses your quota)")
    args = parser.parse_args()
    run_teleportation_protocol(args.shots, args.deferred, args.hardware)
