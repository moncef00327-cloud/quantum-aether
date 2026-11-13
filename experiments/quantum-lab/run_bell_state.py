from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

print("شكل الدائرة الكمومية المحاكة:")
print(qc.draw())

simulator = AerSimulator()
compiled_circuit = transpile(qc, simulator)
job = simulator.run(compiled_circuit, shots=1024)
result = job.result()
counts = result.get_counts()

print("\nنتائج قياس التردد المشتبك بين السطح والباطن:")
print(counts)

from qiskit.visualization import plot_histogram
fig = plot_histogram(counts)
fig.savefig("bell_state_histogram.png", dpi=150, bbox_inches="tight")
print("\nتم حفظ المخطط البياني في: bell_state_histogram.png")
