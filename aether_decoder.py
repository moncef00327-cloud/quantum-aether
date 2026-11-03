# Quantum Aether Decoder Utility
# يفك ترتيب البتات في نتائج Qiskit ويقارن نتيجة نقل الحالة (teleportation) بالقيمة النظرية.
#
# Qiskit يكتب نتيجة القياس نصاً يكون فيه البت الكلاسيكي 0 في أقصى اليمين:
#   المفتاح "101" يعني c2=1, c1=0, c0=1  (والمسافات بين السجلات تُتجاهل)
import math


class AetherDecoder:
    @staticmethod
    def clbit_value(bitstring, clbit):
        bits = bitstring.replace(" ", "")
        return bits[len(bits) - 1 - clbit]

    @staticmethod
    def marginal(counts, clbit):
        zeros = sum(n for bits, n in counts.items() if AetherDecoder.clbit_value(bits, clbit) == "0")
        return zeros, sum(counts.values()) - zeros

    @staticmethod
    def analyze_teleportation_counts(counts, secret_angle, hardware_name="AerSimulator", target_clbit=2,
                                     z_threshold=3.0, verbose=True):
        """يقارن احتمال |0> المقاس على الكيوبت الهدف بـ cos^2(theta/2) باختبار ثنائي الحد (z-test).

        عتبة 3 انحرافات معيارية: عند 1 انحراف فقط يُرفض نحو ثلث التشغيلات السليمة بالصدفة.
        """
        zeros, ones = AetherDecoder.marginal(counts, target_clbit)
        total = zeros + ones
        if total == 0:
            raise ValueError("لا توجد لقطات في counts")
        p_theory = math.cos(secret_angle / 2) ** 2
        p_measured = zeros / total
        sigma = math.sqrt(p_theory * (1 - p_theory) / total)
        if sigma == 0:
            z = 0.0 if p_measured == p_theory else math.inf
        else:
            z = abs(p_measured - p_theory) / sigma
        result = {
            "hardware": hardware_name,
            "shots": total,
            "zeros": zeros,
            "ones": ones,
            "measured_zero_pct": round(p_measured * 100, 2),
            "theoretical_zero_pct": round(p_theory * 100, 2),
            "deviation_pp": round(abs(p_measured - p_theory) * 100, 2),
            "standard_error_pp": round(sigma * 100, 2),
            "z_score": round(z, 2),
            "consistent": z <= z_threshold,
        }
        if verbose:
            print("=" * 56)
            print(f"[Quantum Aether Decoder] - {hardware_name}")
            print("=" * 56)
            print(f"Shots: {total}")
            print(f"Q{target_clbit}=|0>: {zeros} ({result['measured_zero_pct']}%)")
            print(f"Q{target_clbit}=|1>: {ones} ({round(ones / total * 100, 2)}%)")
            print(f"Theoretical |0>: {result['theoretical_zero_pct']}%")
            print(f"Absolute deviation: {result['deviation_pp']} pp (z = {result['z_score']})")
            print(f"Standard error: {result['standard_error_pp']} pp")
            if result["consistent"]:
                print(f"[SUCCESS] within statistical fluctuation (|z| <= {z_threshold}).")
            else:
                print(f"[WARNING] deviation beyond {z_threshold} sigma: noise or a circuit error.")
            print("=" * 56)
        return result


if __name__ == "__main__":
    # مثال توضيحي مصطنع (ليس من عتاد حقيقي): نقل الزاوية pi/3، والكيوبت الهدف هو c2 (الحرف الأول).
    example_counts = {"000": 190, "001": 196, "010": 189, "011": 193, "100": 64, "101": 62, "110": 66, "111": 64}
    AetherDecoder.analyze_teleportation_counts(example_counts, math.pi / 3, "example data")
