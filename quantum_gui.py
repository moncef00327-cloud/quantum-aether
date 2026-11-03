# File: quantum_gui.py
# لوحة تحكم الأثير الكمومي المستقلة - تقرأ من quantum_data.csv (أنشئه بـ export_quantum_data.py)
# أسماء الطبقات (السطح، محطة الترحيل، الباطن) تسمية رمزية للكيوبتات Q0 وQ2 وQ1 في دائرة GHZ.
import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os

# ترتيب أعمدة quantum_data.csv
COLUMNS = ("state", "ideal", "ideal_pct", "noise", "noise_pct", "real", "real_pct")
HEADINGS = ("الحالة الكمية", "المحاكي المثالي (عدد)", "المحاكي %", "نموذج ضوضاء 2% (عدد)",
            "نموذج الضوضاء %", "العتاد الحقيقي (عدد)", "العتاد الحقيقي %")


def qubit_one_probability(state_counts, qubit):
    """احتمال أن يُقاس الكيوبت = 1. مفاتيح Qiskit: أقصى اليمين هو Q0."""
    total = sum(state_counts.values())
    if not total:
        return None
    ones = sum(n for state, n in state_counts.items() if state[len(state) - 1 - qubit] == "1")
    return ones / total


class QuantumAetherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("لوحة تحكم الأثير الكمومي المستقلة")
        self.root.geometry("1020x660")
        self.root.configure(bg="#0f172a")

        self.file_path = "quantum_data.csv"

        self.create_header()
        self.create_population_widget()
        self.create_layers_view()
        self.create_data_table()
        self.create_footer_buttons()

        self.load_data()

    def create_header(self):
        header_frame = tk.Frame(self.root, bg="#1e293b", pady=15)
        header_frame.pack(fill="x")

        title = tk.Label(header_frame,
                         text="📡 نظام الأثير الكمومي: حالة GHZ على ثلاثة كيوبتات",
                         font=("Arial", 16, "bold"), fg="#38bdf8", bg="#1e293b")
        title.pack()

        subtitle = tk.Label(header_frame,
                            text="السطح (Q0) ← محطة الترحيل (Q2) ← الباطن (Q1) — تسمية رمزية؛ القياسات من شريحة IBM والمحاكي",
                            font=("Arial", 10), fg="#94a3b8", bg="#1e293b")
        subtitle.pack(pady=2)

    def create_population_widget(self):
        self.pop_frame = tk.LabelFrame(self.root,
                                       text=" نسبة الإشغال P(000)+P(111) على العتاد الحقيقي ",
                                       font=("Arial", 11, "bold"), fg="#a855f7",
                                       bg="#0f172a", bd=2, padx=10, pady=10)
        self.pop_frame.pack(fill="x", padx=20, pady=10)

        self.pop_label = tk.Label(self.pop_frame, text="جاري الحساب...",
                                  font=("Arial", 24, "bold"), fg="#4ade80", bg="#0f172a")
        self.pop_label.pack(side="left", padx=20)

        desc = tk.Label(self.pop_frame,
                        text="حد أعلى لدقة حالة التشابك (fidelity) وليس الدقة نفسها؛\n"
                             "الدقة الفعلية تحتاج قياسات X وY: python ghz_fidelity.py",
                        font=("Arial", 9), fg="#94a3b8", bg="#0f172a", justify="left")
        desc.pack(side="left", padx=10)

    def create_layers_view(self):
        layers_frame = tk.Frame(self.root, bg="#0f172a")
        layers_frame.pack(fill="x", padx=20, pady=10)

        self.lbl_q0 = tk.Label(layers_frame, text="🌐 السطح (Q0)\n--",
                               font=("Arial", 11, "bold"), bg="#0284c7", fg="white",
                               width=22, height=3)
        self.lbl_q0.grid(row=0, column=0, padx=10)

        tk.Label(layers_frame, text="══ CNOT ══►",
                 font=("Arial", 12, "bold"), fg="#64748b", bg="#0f172a").grid(row=0, column=1)

        self.lbl_q2 = tk.Label(layers_frame, text="⚡ محطة الترحيل (Q2)\n--",
                               font=("Arial", 11, "bold"), bg="#b45309", fg="white",
                               width=22, height=3)
        self.lbl_q2.grid(row=0, column=2, padx=10)

        tk.Label(layers_frame, text="══ CNOT ══►",
                 font=("Arial", 12, "bold"), fg="#64748b", bg="#0f172a").grid(row=0, column=3)

        self.lbl_q1 = tk.Label(layers_frame, text="🌋 الباطن (Q1)\n--",
                               font=("Arial", 11, "bold"), bg="#15803d", fg="white",
                               width=22, height=3)
        self.lbl_q1.grid(row=0, column=4, padx=10)

    def create_data_table(self):
        table_frame = tk.Frame(self.root, bg="#0f172a")
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#1e293b", fieldbackground="#1e293b",
                        foreground="white", rowheight=25)
        style.configure("Treeview.Heading", background="#334155", foreground="white",
                        font=("Arial", 10, "bold"))

        self.tree = ttk.Treeview(table_frame, columns=COLUMNS, show="headings", height=8)
        for col, heading in zip(COLUMNS, HEADINGS):
            self.tree.heading(col, text=heading)
            self.tree.column(col, anchor="center", width=130)

        self.tree.pack(fill="both", expand=True)

    def create_footer_buttons(self):
        footer_frame = tk.Frame(self.root, bg="#0f172a", pady=15)
        footer_frame.pack(fill="x")

        btn_refresh = tk.Button(footer_frame, text="🔄 تحديث قراءات الملف",
                                font=("Arial", 10, "bold"),
                                bg="#38bdf8", fg="#0f172a",
                                activebackground="#0284c7", command=self.load_data)
        btn_refresh.pack(side="right", padx=20)

        btn_info = tk.Button(footer_frame, text="ℹ️ دليل القراءة",
                             font=("Arial", 10),
                             bg="#475569", fg="white",
                             activebackground="#334155", command=self.show_help)
        btn_info.pack(side="left", padx=20)

    def load_data(self):
        if not os.path.exists(self.file_path):
            messagebox.showerror("خطأ في النظام",
                                 f"لم يتم العثور على ملف البيانات الأساسي: {self.file_path}\n"
                                 "شغّل أولاً: python export_quantum_data.py")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            hardware_counts, noise_counts = {}, {}
            population = None
            with open(self.file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # تخطي رأس الجدول
                for row in reader:
                    if not row:  # تخطي الأسطر الفارغة
                        continue
                    if len(row) == len(COLUMNS):  # صفوف الحالات
                        self.tree.insert("", "end", values=row)
                        noise_counts[row[0]] = int(row[3])
                        if row[5]:
                            hardware_counts[row[0]] = int(row[5])
                    elif len(row) == 2 and "العتاد الحقيقي" in row[0]:
                        population = row[1]

            # كل طبقة تعرض احتمال قياس الكيوبت الخاص بها = 1 (في GHZ المثالية 50% لكل كيوبت).
            counts, source = (hardware_counts, "العتاد") if hardware_counts else (noise_counts, "نموذج الضوضاء")
            for label, name, qubit in ((self.lbl_q0, "🌐 السطح", 0), (self.lbl_q2, "⚡ محطة الترحيل", 2),
                                       (self.lbl_q1, "🌋 الباطن", 1)):
                p_one = qubit_one_probability(counts, qubit)
                value = "--" if p_one is None else f"P(1) = {p_one * 100:.1f}% ({source})"
                label.config(text=f"{name} (Q{qubit})\n{value}")

            self.pop_label.config(text=population or "لا توجد بيانات عتاد")

        except Exception as e:
            messagebox.showerror("خطأ في القراءة",
                                 f"حدث خطأ أثناء قراءة الملف: {str(e)}")

    def show_help(self):
        help_text = (
            "دليل قراءة لوحة الحالات الكمومية:\n\n"
            "1. الحالتان (000) و(111): الكيوبتات الثلاثة تُقاس متطابقة، وهذا ما تَعِد به حالة GHZ؛ "
            "مجموعهما هو نسبة الإشغال المعروضة في الأعلى.\n\n"
            "2. الحالات الأخرى (مثل 001 أو 110): أخطاء في الشريحة الكمومية نفسها — أخطاء البوابات، "
            "وأخطاء القراءة، وفقدان الترابط (T1/T2) داخل المبرّد. لا علاقة لها بطبقات الأرض.\n\n"
            "3. زر التحديث: يعيد قراءة quantum_data.csv. لتحديث عمود العتاد شغّل "
            "python real_quantum.py ثم python export_quantum_data.py."
        )
        messagebox.showinfo("دليل القراءة", help_text)


if __name__ == "__main__":
    root = tk.Tk()
    app = QuantumAetherGUI(root)
    root.mainloop()
