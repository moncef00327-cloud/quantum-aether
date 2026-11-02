# File: quantum_gui.py
# لوحة تحكم الأثير الكمومي المستقلة - تقرأ من quantum_data.csv
import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os


class QuantumAetherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("لوحة تحكم الأثير الكمومي المستقلة")
        self.root.geometry("900x640")
        self.root.configure(bg="#0f172a")

        self.file_path = "quantum_data.csv"

        self.create_header()
        self.create_fidelity_widget()
        self.create_layers_view()
        self.create_data_table()
        self.create_footer_buttons()

        self.load_data()

    def create_header(self):
        header_frame = tk.Frame(self.root, bg="#1e293b", pady=15)
        header_frame.pack(fill="x")

        title = tk.Label(header_frame,
                         text="📡 نظام استشعار الأثير الباطني والربط الكمومي عبر الـ 6G",
                         font=("Arial", 16, "bold"), fg="#38bdf8", bg="#1e293b")
        title.pack()

        subtitle = tk.Label(header_frame,
                            text="محاكاة حية لعزل ترددات السطح (Q0) عن الباطن (Q1) عبر محطة الترحيل (Q2)",
                            font=("Arial", 10), fg="#94a3b8", bg="#1e293b")
        subtitle.pack(pady=2)

    def create_fidelity_widget(self):
        self.fid_frame = tk.LabelFrame(self.root,
                                       text=" مقياس إخلاص التشابك الكوني (Fidelity) ",
                                       font=("Arial", 11, "bold"), fg="#a855f7",
                                       bg="#0f172a", bd=2, padx=10, pady=10)
        self.fid_frame.pack(fill="x", padx=20, pady=10)

        self.fid_label = tk.Label(self.fid_frame, text="جاري الحساب...",
                                  font=("Arial", 24, "bold"), fg="#4ade80", bg="#0f172a")
        self.fid_label.pack(side="left", padx=20)

        desc = tk.Label(self.fid_frame,
                        text="مؤشر النقاء: يوضح مدى صمود موجات التشابك أمام تفكك الجسيمات (Decoherence)\nوالضوضاء الحرارية في أعماق الوشاح الأرضي الباطني.",
                        font=("Arial", 9), fg="#94a3b8", bg="#0f172a", justify="left")
        desc.pack(side="left", padx=10)

    def create_layers_view(self):
        layers_frame = tk.Frame(self.root, bg="#0f172a")
        layers_frame.pack(fill="x", padx=20, pady=10)

        self.lbl_q0 = tk.Label(layers_frame, text="🌐 السطح (Q0)\n--",
                               font=("Arial", 11, "bold"), bg="#0284c7", fg="white",
                               width=20, height=3)
        self.lbl_q0.grid(row=0, column=0, padx=10)

        arrow1 = tk.Label(layers_frame, text="══ 6G ══►",
                          font=("Arial", 12, "bold"), fg="#64748b", bg="#0f172a")
        arrow1.grid(row=0, column=1)

        self.lbl_q2 = tk.Label(layers_frame, text="⚡ محطة الترحيل (Q2)\n--",
                               font=("Arial", 11, "bold"), bg="#b45309", fg="white",
                               width=20, height=3)
        self.lbl_q2.grid(row=0, column=2, padx=10)

        arrow2 = tk.Label(layers_frame, text="══ أثير ══►",
                          font=("Arial", 12, "bold"), fg="#64748b", bg="#0f172a")
        arrow2.grid(row=0, column=3)

        self.lbl_q1 = tk.Label(layers_frame, text="🌋 الباطن (Q1)\n--",
                               font=("Arial", 11, "bold"), bg="#15803d", fg="white",
                               width=20, height=3)
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

        columns = ("state", "ideal", "ideal_pct", "real", "real_pct")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        self.tree.heading("state", text="الحالة الكمية")
        self.tree.heading("ideal", text="المحاكي المثالي (عدد)")
        self.tree.heading("ideal_pct", text="المحاكي %")
        self.tree.heading("real", text="العتاد الحقيقي (عدد)")
        self.tree.heading("real_pct", text="العتاد %")

        for col in columns:
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

        btn_info = tk.Button(footer_frame, text="ℹ️ دليل فك الشفرة",
                             font=("Arial", 10),
                             bg="#475569", fg="white",
                             activebackground="#334155", command=self.show_help)
        btn_info.pack(side="left", padx=20)

    def load_data(self):
        if not os.path.exists(self.file_path):
            messagebox.showerror("خطأ في النظام",
                                 f"لم يتم العثور على ملف البيانات الأساسي: {self.file_path}\n"
                                 "تأكد من تشغيل سكربت التوليد أولاً.")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            with open(self.file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader)

                real_000_pct = 0
                real_111_pct = 0
                fidelity_pct = None

                for row in reader:
                    if not row:  # تخطي الأسطر الفارغة
                        continue
                    if len(row) == 5:  # صفوف الحالات
                        self.tree.insert("", "end", values=row)
                        if row[0] == "000":
                            real_000_pct = row[4]
                        elif row[0] == "111":
                            real_111_pct = row[4]
                    elif len(row) == 2:  # صفوف الملخص
                        if "إخلاص" in row[0]:
                            fidelity_pct = row[1]

            # تحديث شاشات الطبقات المنفصلة بصرياً بناءً على أعلى تردد مهتز
            self.lbl_q0.config(text=f"🌐 السطح (Q0)\nنشط بـ: {real_111_pct}")
            self.lbl_q2.config(text=f"⚡ محطة الترحيل (Q2)\nممرر بـ: {real_111_pct}")
            self.lbl_q1.config(text=f"🌋 الباطن (Q1)\nمستقبل بـ: {real_111_pct}")

            # قراءة الإخلاص من الملف ديناميكياً بدلاً من تثبيته
            if fidelity_pct:
                self.fid_label.config(text=fidelity_pct)
            else:
                self.fid_label.config(text="غير متوفر")

        except Exception as e:
            messagebox.showerror("خطأ في القراءة",
                                 f"حدث خطأ أثناء محاولة تفريغ قنوات الأثير: {str(e)}")

    def show_help(self):
        help_text = (
            "دليل قراءة لوحة الترددات الكمومية:\n\n"
            "1. الحالات (000) و(111): تمثل النجاح المطلق للربط؛ حيث ينهار مستشعر السطح "
            "وأثير باطن الأرض في نفس اللحظة الكونية وبشكل متناظر تماماً عبر المحطة الوسيطة.\n\n"
            "2. حالات الارتشاح والضوضاء (مثل 001 أو 010): هي مؤشر على مقاومة الصخور وبقايا كوكب "
            "ثيا القديم للموجات، مما يتسبب في تفكك تشابك كيوبرتات IBM بفعل الحرارة العالية.\n\n"
            "3. زر التحديث: عند حقن مفتاح الـ API الفعلي وتشغيل المعالج الكمومي في نيويورك، "
            "اضغط على تحديث لتنتقل المؤشرات تلقائياً من الوضع التقديري إلى الواقع الفيزيائي الحي."
        )
        messagebox.showinfo("دليل الاستكشاف وفك الشفرة", help_text)


if __name__ == "__main__":
    root = tk.Tk()
    app = QuantumAetherGUI(root)
    root.mainloop()
