# بروتوكول نقل حالة كيوبت باستخدام التشابك والاتصال الكلاسيكي
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
import numpy as np

def teleport_angle(angle_value, angle_name, shots=1024):
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

    simulator = AerSimulator()
    compiled_circuit = transpile(qc, simulator)
    job = simulator.run(compiled_circuit, shots=shots)
    counts = job.result().get_counts()

    # Qiskit يعرض البتات بالترتيب c2 c1 c0، لذا c2 هو الحرف الأول.
    zero_shots = sum(count for bitstring, count in counts.items() if bitstring[0] == "0")
    one_shots = sum(count for bitstring, count in counts.items() if bitstring[0] == "1")
    total_shots = zero_shots + one_shots

    measured_zero = zero_shots / total_shots
    theoretical_zero = np.cos(angle_value / 2) ** 2
    standard_error = np.sqrt(measured_zero * (1 - measured_zero) / total_shots)
    deviation = abs(measured_zero - theoretical_zero)

    print(f"\nنتائج الزاوية {angle_name} ({angle_value:.6f} rad):")
    print(f"القياسات الخام (c2 c1 c0): {counts}")
    print(f"Q2 = |0>: {zero_shots}/{total_shots} ({measured_zero * 100:.2f}%)")
    print(f"Q2 = |1>: {one_shots}/{total_shots} ({one_shots / total_shots * 100:.2f}%)")
    print(f"الاحتمال النظري لـ |0>: {theoretical_zero * 100:.2f}%")
    print(f"الانحراف المطلق: {deviation * 100:.2f} نقطة مئوية")
    print(f"الخطأ المعياري التقديري للقياس: {standard_error * 100:.2f} نقطة مئوية")

    return counts


def run_teleportation_protocol(shots=1024):
    test_angles = [
        (np.pi / 3, "pi/3"),
        (np.pi / 4, "pi/4"),
        (2 * np.pi / 5, "2pi/5"),
    ]

    print(f"اختبار نقل الحالة على المحاكي باستخدام {shots} لقطة لكل زاوية.")
    for angle_value, angle_name in test_angles:
        teleport_angle(angle_value, angle_name, shots=shots)

    print("\nملاحظة: هذه المقارنة تقيس احتمالات أساس Z فقط؛ لا تكفي وحدها لإثبات نقل حالة كمومية عامة أو قياس الوفاء الكامل.")

if __name__ == "__main__":
    run_teleportation_protocol()
