"""حفظ اعتماد IBM Quantum محلياً دون إظهار الرمز أو تسجيله.

الاستخدام:
    .\.venv\Scripts\python.exe save_ibm_account.py

يطلب الرمز عبر getpass (لا يظهر على الشاشة، لا يدخل سجل الطرفية)،
ثم يكتب الحساب في ~/.qiskit/qiskit-ibm.json ويتحقق من نجاح الحفظ.
"""

import sys
from getpass import getpass

from qiskit_ibm_runtime import QiskitRuntimeService


def main() -> int:
    print("حفظ اعتماد IBM Quantum محلياً.")
    print("ألصق رمز API ثم اضغط Enter (لن يظهر شيء أثناء اللصق).")
    print("اتركه فارغاً للخروج.\n")

    token = getpass("IBM API token: ").strip()
    if not token:
        print("لم يُدخل أي رمز. تم الإلغاء.")
        return 1

    if token in {"YOUR_API_TOKEN", "invalid-test-token-000"}:
        print("هذا ليس رمزاً حقيقياً.")
        return 1

    QiskitRuntimeService.save_account(
        token=token,
        channel="ibm_quantum_platform",
        overwrite=True,
        set_as_default=True,
    )

    accounts = QiskitRuntimeService.saved_accounts()
    if not accounts:
        print("\nفشل الحفظ: لم يُعثر على أي حساب محفوظ.")
        return 2

    print("\nتم الحفظ بنجاح.")
    for name, data in accounts.items():
        print(f"  الحساب: {name}")
        print(f"  القناة: {data.get('channel', 'غير محددة')}")
        print(f"  رمز محفوظ: {'نعم' if data.get('token') else 'لا'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
