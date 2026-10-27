#!/usr/bin/env python3
"""Android Remote Control Center: GUI for a user-authorized Android device."""

import os
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from adb_helper import run_adb_cmd, get_adb_devices
from os_features import OSFeaturesHandler

APP_TITLE = "Android Remote Control Center"


class RemoteControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x720")
        self.root.minsize(820, 600)

        # Inisialisasi Modul OS Features
        self.os_handler = OSFeaturesHandler(self.run_adb)
        self.worker_thread = threading.Thread(
            target=self.os_handler.queue_worker, args=(self.root,), daemon=True
        )
        self.worker_thread.start()

        self.device = tk.StringVar()
        self.status = tk.StringVar(value="Sambungkan HP melalui USB, aktifkan USB Debugging, lalu Refresh.")
        self.minutes = tk.StringVar(value="30")
        self.timer_running = False
        self.timer_start = None
        self.timer_job = None
        self.packages = []

        self._build_ui()
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_dashboard_loop()

    def run_adb(self, device_id, *, args, timeout=15):
        """Menjembatani pemanggilan ADB dari modul OS ke modul pembantu."""
        # Modul OS memanggil dengan device_id sebagai argumen pertama
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def run_adb_local(self, args, timeout=15):
        """Fungsi pembantu lokal untuk perintah ADB yang menggunakan perangkat terpilih."""
        device_id = self.device.get().strip()
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def show_error(self, title, error):
        self.status.set(str(error))
        messagebox.showerror(title, str(error), parent=self.root)

    def submit_to_queue(self, func, args=(), callback=None):
        self.os_handler.submit_to_queue(func, args, callback)
        self.status.set(f"Tugas dimasukkan ke antrean (Total pending: {self.os_handler.cmd_queue.qsize()})")

    def test_concurrency_sync(self):
        def dummy_adb_task(task_id):
            time.sleep(1)
            return f"Task #{task_id} berhasil dieksekusi dengan aman melalui Proteksi Mutex Lock."

        def on_task_finished(success, res):
            if hasattr(self, 'sync_log'):
                self.sync_log.insert(tk.END, f"[SYNC/MUTEX] {res}\n")
                self.sync_log.see(tk.END)

        for i in range(1, 4):
            self.submit_to_queue(dummy_adb_task, args=(i,), callback=on_task_finished)

    def load_memory_info(self):
        try:
            device_id = self.device.get().strip()
            memory_data = self.os_handler.get_memory_info(device_id)

            for item in self.mem_tree.get_children():
                self.mem_tree.delete(item)

            target_keys = [
                "MemTotal", "MemFree", "MemAvailable", "Buffers",
                "Cached", "SwapTotal", "SwapFree", "VmallocTotal", "VmallocUsed"
            ]

            for key in target_keys:
                if key in memory_data:
                    desc = self.os_handler.get_memory_description(key)
                    self.mem_tree.insert("", "end", values=(key, memory_data[key], desc))

            self.status.set("Berhasil memuat data manajemen memori dan swapping Android.")
        except Exception as exc:
            self.show_error("Gagal memuat info memori", exc)

    def load_processes(self):
        try:
            device_id = self.device.get().strip()
            processes = self.os_handler.get_process_table(device_id)

            for item in self.proc_tree.get_children():
                self.proc_tree.delete(item)

            for proc in processes:
                self.proc_tree.insert("", "end", values=proc)

            self.status.set("Berhasil memuat daftar proses dan penggunaan CPU perangkat.")
        except Exception as exc:
            self.show_error("Gagal memuat proses", exc)

    def change_process_priority(self):
        selected_item = self.proc_tree.selection()
        if not selected_item:
            messagebox.showinfo("Pilih Proses", "Pilih salah satu baris proses dari tabel terlebih dahulu.", parent=self.root)
            return

        item_data = self.proc_tree.item(selected_item[0])['values']
        pid = item_data[0]
        name = item_data[5]

        new_nice = simpledialog.askinteger("Ubah Prioritas (Nice)", f"PID {pid} ({name}):\nMasukkan nilai Nice (-20 sampai 19):", minvalue=-20, maxvalue=19, parent=self.root)
        if new_nice is not None:
            try:
                self.run_adb_local(["shell", "renice", str(new_nice), str(pid)], timeout=10)
                self.status.set(f"Prioritas PID {pid} berhasil diubah menjadi {new_nice}.")
                self.load_processes()
            except Exception as exc:
                self.show_error("Gagal mengubah prioritas", exc)

    def refresh_devices(self):
        try:
            devices, unauthorized = get_adb_devices()
            self.device_combo["values"] = devices
            if devices:
                self.device.set(devices[0])
                self.status.set(f"{len(devices)} perangkat terotorisasi.")
            elif unauthorized:
                self.device.set("")
                self.status.set("HP unauthorized: setujui dialog USB Debugging di layar HP.")
            else:
                self.device.set("")
                self.status.set("Belum ada HP terotorisasi. Periksa kabel USB dan USB Debugging.")
        except Exception as exc:
            self.show_error("Gagal mendeteksi perangkat", exc)

    def refresh_dashboard(self):
        if not self.device.get().strip():
            self.dashboard_connection.set("Tidak terhubung")
            self.dashboard_model.set("-")
            self.dashboard_android.set("-")
            self.dashboard_battery.set("-")
            self.dashboard_storage.set("-")
            return

        try:
            model = self.run_adb_local(["shell", "getprop", "ro.product.model"], timeout=8)
            android = self.run_adb_local(["shell", "getprop", "ro.build.version.release"], timeout=8)
            battery_output = self.run_adb_local(["shell", "dumpsys", "battery"], timeout=8)
            battery_level = next(
                (line.split(":", 1)[1].strip() for line in battery_output.splitlines() if line.strip().startswith("level:")),
                None
            )
            storage_output = self.run_adb_local(["shell", "df", "-h", "/data"], timeout=8)
            storage_lines = storage_output.splitlines()
            storage = "Tidak tersedia"
            if len(storage_lines) >= 2:
                columns = storage_lines[-1].split()
                if len(columns) >= 5:
                    storage = f"Terpakai {columns[2]} dari {columns[1]} ({columns[4]})"

            self.dashboard_connection.set("Terhubung melalui ADB")
            self.dashboard_model.set(model or "Tidak diketahui")
            self.dashboard_android.set(android or "Tidak diketahui")
            self.dashboard_battery.set(f"{battery_level}%" if battery_level else "Tidak tersedia")
            self.dashboard_storage.set(storage)
        except Exception as exc:
            self.dashboard_connection.set("Gagal membaca perangkat")
            self.dashboard_model.set("-")
            self.dashboard_android.set("-")
            self.dashboard_battery.set("-")
            self.dashboard_storage.set("-")
            self.status.set(str(exc))

    def refresh_dashboard_loop(self):
        self.refresh_dashboard()
        self.root.after(10000, self.refresh_dashboard_loop)

    def device_info(self):
        try:
            model = self.run_adb_local(["shell", "getprop", "ro.product.model"])
            android = self.run_adb_local(["shell", "getprop", "ro.build.version.release"])
            serial = self.device.get()
            messagebox.showinfo("Info perangkat", f"Model: {model}\nAndroid: {android}\nADB ID: {serial}", parent=self.root)
        except Exception as exc:
            self.show_error("Gagal membaca perangkat", exc)

    def start_mirroring(self):
        self._start_scrcpy(screen_off=False)

    def start_mirroring_screen_off(self):
        if not messagebox.askyesno("Konfirmasi", "Coba matikan layar fisik HP saat mirroring berjalan?", parent=self.root):
            return
        self._start_scrcpy(screen_off=True)

    def _start_scrcpy(self, screen_off):
        if not self.device.get():
            messagebox.showwarning("Pilih perangkat", "Pilih HP yang terotorisasi terlebih dahulu.", parent=self.root)
            return
        try:
            args = ["scrcpy", "-s", self.device.get()]
            if screen_off:
                args.append("--turn-screen-off")
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.status.set("scrcpy dijalankan di jendela terpisah.")
        except FileNotFoundError:
            self.show_error("scrcpy tidak ditemukan", "Pasang scrcpy dengan: sudo apt install scrcpy")
        except Exception as exc:
            self.show_error("Gagal memulai mirroring", exc)

    def lock_screen(self):
        try:
            self.run_adb_local(["shell", "input", "keyevent", "26"])
            self.status.set("Perintah tombol daya dikirim.")
        except Exception as exc:
            self.show_error("Gagal mengunci layar", exc)

    def wake_screen(self):
        try:
            self.run_adb_local(["shell", "input", "keyevent", "224"])
            self.status.set("Perintah bangunkan layar dikirim.")
        except Exception as exc:
            self.show_error("Gagal membangunkan layar", exc)

    def load_packages(self):
        try:
            output = self.run_adb_local(["shell", "pm", "list", "packages", "-3"], timeout=30)
            self.packages = sorted(
                line.replace("package:", "", 1).strip()
                for line in output.splitlines()
                if line.startswith("package:")
            )
            self.package_list.delete(0, tk.END)
            for package in self.packages:
                self.package_list.insert(tk.END, package)
            self.status.set(f"{len(self.packages)} aplikasi pihak ketiga ditemukan.")
        except Exception as exc:
            self.show_error("Gagal memuat aplikasi", exc)

    def force_stop_selected(self):
        selection = self.package_list.curselection()
        if not selection:
            messagebox.showinfo("Pilih aplikasi", "Pilih satu atau beberapa aplikasi dari daftar.", parent=self.root)
            return
        selected = [self.package_list.get(index) for index in selection]
        if not messagebox.askyesno("Konfirmasi force stop", "Hentikan aplikasi berikut?\n\n" + "\n".join(selected), parent=self.root):
            return
        try:
            for package in selected:
                self.run_adb_local(["shell", "am", "force-stop", package], timeout=20)
            self.status.set(f"{len(selected)} aplikasi dihentikan.")
            messagebox.showinfo("Selesai", "Perintah force-stop berhasil dikirim.", parent=self.root)
        except Exception as exc:
            self.show_error("Gagal force stop", exc)

    def push_file(self):
        path = filedialog.askopenfilename(parent=self.root, title="Pilih file untuk dikirim")
        if not path:
            return
        try:
            name = os.path.basename(path)
            self.run_adb_local(["push", path, f"/sdcard/Download/{name}"], timeout=180)
            self.status.set(f"File dikirim: {name}")
            messagebox.showinfo("Transfer selesai", f"File dikirim ke Download/{name} pada HP.", parent=self.root)
        except Exception as exc:
            self.show_error("Transfer gagal", exc)

    def install_apk(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Pilih file APK",
            filetypes=[("Android APK", "*.apk"), ("Semua file", "*.*")]
        )
        if not path:
            return
        if not path.lower().endswith(".apk"):
            messagebox.showwarning("File tidak valid", "Pilih file dengan ekstensi .apk.", parent=self.root)
            return
        if not messagebox.askyesno("Konfirmasi instalasi", f"Instal APK ini pada HP?\n\n{path}", parent=self.root):
            return
        try:
            output = self.run_adb_local(["install", "-r", path], timeout=240)
            self.status.set(output or "Perintah instalasi selesai.")
            messagebox.showinfo("Instalasi selesai", output or "ADB menyelesaikan instalasi.", parent=self.root)
        except Exception as exc:
            self.show_error("Instalasi gagal", exc)

    def start_timer(self):
        try:
            minutes = int(self.minutes.get())
            if minutes < 1 or minutes > 1440:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Batas tidak valid", "Masukkan angka 1 sampai 1440 menit.", parent=self.root)
            return
        self.stop_timer()
        self.timer_running = True
        self.timer_start = time.monotonic()
        self.timer_limit = minutes * 60
        self._tick_timer()
        self.status.set(f"Timer sesi dimulai: {minutes} menit.")

    def stop_timer(self):
        self.timer_running = False
        if self.timer_job is not None:
            try:
                self.root.after_cancel(self.timer_job)
            except tk.TclError:
                pass
            self.timer_job = None

    def _tick_timer(self):
        if not self.timer_running or self.timer_start is None:
            return
        elapsed = int(time.monotonic() - self.timer_start)
        remaining = max(0, self.timer_limit - elapsed)
        self.timer_label.configure(text=f"{remaining // 60:02d}:{remaining % 60:02d}")
        if remaining <= 0:
            self.stop_timer()
            if messagebox.askyesno("Batas waktu tercapai", "Batas sesi tercapai. Kunci layar HP?", parent=self.root):
                self.lock_screen()
            return
        self.timer_job = self.root.after(1000, self._tick_timer)

    def _build_ui(self):
        self.root.configure(bg="#F3F6FC")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=35)

        BG, CARD, NAVY, BLUE, TEXT, MUTED, BORDER = "#F3F6FC", "#FFFFFF", "#17243A", "#356DF3", "#243149", "#68758B", "#DCE4F0"

        style.configure(".", font=("DejaVu Sans", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Header.TLabel", background=BG, foreground=NAVY, font=("DejaVu Sans", 21, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("DejaVu Sans", 9))
        style.configure("TLabelframe", background=CARD, bordercolor=BORDER, relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=CARD, foreground=NAVY, font=("DejaVu Sans", 10, "bold"))
        style.configure("TButton", background=CARD, foreground=TEXT, bordercolor=BORDER, padding=(13, 8), relief="flat", font=("DejaVu Sans", 9, "bold"))
        style.map("TButton", background=[("active", "#E8EEFF"), ("pressed", "#D8E3FF")], foreground=[("disabled", "#9AA5B5")])
        style.configure("Accent.TButton", background=BLUE, foreground="#FFFFFF", bordercolor=BLUE, padding=(14, 9))
        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(2, 5, 2, 0))
        style.configure("TNotebook.Tab", background="#E8EDF6", foreground=MUTED, padding=(15, 10), font=("DejaVu Sans", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", CARD), ("active", "#DCE6FA")], foreground=[("selected", BLUE), ("active", NAVY)])

        header = ttk.Frame(self.root, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="USB + ADB • Gunakan hanya pada perangkat milikmu atau yang kamu punya izin untuk kelola.", wraplength=940, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 8))

        device_frame = ttk.LabelFrame(self.root, text="Perangkat Android", padding=10)
        device_frame.pack(fill="x", padx=12, pady=4)
        ttk.Label(device_frame, text="Device ID:").pack(side="left")
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device, state="readonly", width=32)
        self.device_combo.pack(side="left", padx=8)
        ttk.Button(device_frame, text="Refresh", command=self.refresh_devices).pack(side="left")
        ttk.Button(device_frame, text="Info perangkat", command=self.device_info).pack(side="left", padx=6)
        ttk.Label(device_frame, textvariable=self.status, wraplength=450).pack(side="left", padx=12, fill="x", expand=True)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        dashboard_tab = ttk.Frame(notebook, padding=16)
        mirror_tab = ttk.Frame(notebook, padding=12)
        apps_tab = ttk.Frame(notebook, padding=12)
        files_tab = ttk.Frame(notebook, padding=12)
        usage_tab = ttk.Frame(notebook, padding=12)

        notebook.add(dashboard_tab, text="Dashboard")
        notebook.add(mirror_tab, text="Mirroring & Kontrol")
        notebook.add(apps_tab, text="Aplikasi")

        # Tab Memori
        mem_tab = ttk.Frame(notebook)
        notebook.add(mem_tab, text="Manajemen Memori")
        mem_top = ttk.Frame(mem_tab, padding=10)
        mem_top.pack(fill="x")
        ttk.Label(mem_top, text="Inspeksi Alokasi Memori Fisik & Swapping (Virtual Memory)", font=("Arial", 11, "bold")).pack(anchor="w")
        ttk.Label(mem_top, text="Menganalisis penggunaan RAM, ruang swap, dan cache berdasarkan struktur kernel /proc/meminfo.").pack(anchor="w", pady=(0, 10))
        ttk.Button(mem_top, text="Muat Informasi Memori", command=self.load_memory_info).pack(anchor="w")

        mem_frame = ttk.Frame(mem_tab, padding=10)
        mem_frame.pack(fill="both", expand=True)
        mem_columns = ("Parameter", "Nilai (Value)", "Keterangan Konsep OS")
        self.mem_tree = ttk.Treeview(mem_frame, columns=mem_columns, show="headings", height=12)
        self.mem_tree.heading("Parameter", text="Parameter Memori")
        self.mem_tree.heading("Nilai (Value)", text="Nilai (Value)")
        self.mem_tree.heading("Keterangan Konsep OS", text="Keterangan Konsep OS")
        self.mem_tree.column("Parameter", width=200, anchor="w", stretch=False)
        self.mem_tree.column("Nilai (Value)", width=150, anchor="w", stretch=False)
        self.mem_tree.column("Keterangan Konsep OS", width=500, anchor="w", stretch=True)
        mem_scroll = ttk.Scrollbar(mem_frame, orient="vertical", command=self.mem_tree.yview)
        self.mem_tree.configure(yscrollcommand=mem_scroll.set)
        self.mem_tree.pack(side="left", fill="both", expand=True)
        mem_scroll.pack(side="right", fill="y")

        # Tab Sinkronisasi
        sync_tab = ttk.Frame(notebook)
        notebook.add(sync_tab, text="Sinkronisasi OS")
        sync_top = ttk.Frame(sync_tab, padding=10)
        sync_top.pack(fill="x")
        ttk.Label(sync_top, text="Simulasi Antrean Proses (Queue) & Proteksi Mutex Lock", font=("Arial", 11, "bold")).pack(anchor="w")
        ttk.Label(sync_top, text="Mengatur eksekusi perintah konkuren agar tidak terjadi bentrok sumber daya (race condition).").pack(anchor="w", pady=(0, 10))
        ttk.Button(sync_top, text="Jalankan Simulasi Antrean Konkuren", command=self.test_concurrency_sync).pack(anchor="w")

        sync_frame = ttk.Frame(sync_tab, padding=10)
        sync_frame.pack(fill="both", expand=True)
        sync_scroll = ttk.Scrollbar(sync_frame, orient="vertical")
        sync_scroll.pack(side="right", fill="y")
        self.sync_log = tk.Text(sync_frame, wrap="word", bg="#1e1e1e", fg="#00ff00", font=("Courier", 10), yscrollcommand=sync_scroll.set)
        self.sync_log.pack(side="left", fill="both", expand=True)
        sync_scroll.config(command=self.sync_log.yview)

        # Dashboard content
        ttk.Label(dashboard_tab, text="Ringkasan Perangkat", font=("TkDefaultFont", 16, "bold")).pack(anchor="w", pady=(0, 12))
        self.dashboard_connection = tk.StringVar(value="Memeriksa koneksi...")
        self.dashboard_model = tk.StringVar(value="-")
        self.dashboard_android = tk.StringVar(value="-")
        self.dashboard_battery = tk.StringVar(value="-")
        self.dashboard_storage = tk.StringVar(value="-")

        info_frame = ttk.LabelFrame(dashboard_tab, text="Informasi HP", padding=12)
        info_frame.pack(fill="x", pady=4)

        for label, variable in [
            ("Status koneksi", self.dashboard_connection),
            ("Model perangkat", self.dashboard_model),
            ("Versi Android", self.dashboard_android),
            ("Baterai", self.dashboard_battery),
            ("Penyimpanan /data", self.dashboard_storage),
        ]:
            line = ttk.Frame(info_frame)
            line.pack(fill="x", pady=5)
            ttk.Label(line, text=label, width=22).pack(side="left")
            ttk.Label(line, textvariable=variable, font=("TkDefaultFont", 10, "bold")).pack(side="left", fill="x", expand=True)

        dashboard_buttons = ttk.Frame(dashboard_tab)
        dashboard_buttons.pack(fill="x", pady=12)
        ttk.Button(dashboard_buttons, text="Perbarui informasi", command=self.refresh_dashboard).pack(side="left")
        ttk.Button(dashboard_buttons, text="Refresh perangkat", command=self.refresh_devices).pack(side="left", padx=8)

        # Tab Manajemen Proses
        process_tab = ttk.Frame(notebook, padding=12)
        notebook.add(process_tab, text="Manajemen Proses & CPU")
        ttk.Label(process_tab, text="Daftar Proses Android & Penjadwalan (Process Table)", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(process_tab, text="Menampilkan PID, Status, Prioritas (Nice), dan CPU Usage (%) dari kernel Android.").pack(anchor="w", pady=4)

        proc_top = ttk.Frame(process_tab)
        proc_top.pack(fill="x", pady=6)
        ttk.Button(proc_top, text="Muat Proses (PS)", command=self.load_processes).pack(side="left")
        ttk.Button(proc_top, text="Ubah Prioritas (Renice)", command=self.change_process_priority).pack(side="left", padx=8)

        tree_frame = ttk.Frame(process_tab)
        tree_frame.pack(fill="both", expand=True, pady=4)

        self.proc_tree = ttk.Treeview(
            tree_frame, 
            columns=("PID", "USER", "STATUS", "NICE", "CPU (%)", "Command / Nama Proses"),
            show="headings",
            height=30
        )
        self.proc_tree.heading("PID", text="PID")
        self.proc_tree.heading("USER", text="User")
        self.proc_tree.heading("STATUS", text="Status")
        self.proc_tree.heading("NICE", text="Nice (NI)")
        self.proc_tree.heading("CPU (%)", text="CPU (%)")
        self.proc_tree.heading("Command / Nama Proses", text="Command / Nama Proses")

        self.proc_tree.column("PID", width=80, anchor="center", stretch=False)
        self.proc_tree.column("USER", width=100, anchor="center", stretch=False)
        self.proc_tree.column("STATUS", width=80, anchor="center", stretch=False)
        self.proc_tree.column("NICE", width=80, anchor="center", stretch=False)
        self.proc_tree.column("CPU (%)", width=80, anchor="center", stretch=False)
        self.proc_tree.column("Command / Nama Proses", width=500, anchor="w", stretch=True)

        proc_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=proc_scroll.set)
        self.proc_tree.pack(side="left", fill="both", expand=True)
        proc_scroll.pack(side="right", fill="y")

        notebook.add(files_tab, text="Transfer File")
        notebook.add(usage_tab, text="Screen Time")

        # Mirroring tab
        ttk.Label(mirror_tab, text="Mirroring menggunakan scrcpy", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(mirror_tab, text="scrcpy membuka jendela layar HP terpisah dan meneruskan klik, scroll, serta ketikan keyboard.").pack(anchor="w", pady=6)
        row = ttk.Frame(mirror_tab)
        row.pack(anchor="w", pady=8)
        ttk.Button(row, text="Mulai mirroring", command=self.start_mirroring).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Mirroring + layar HP mati", command=self.start_mirroring_screen_off).pack(side="left", padx=8)
        ttk.Button(row, text="Kunci layar HP", command=self.lock_screen).pack(side="left", padx=8)
        ttk.Button(row, text="Bangunkan layar", command=self.wake_screen).pack(side="left", padx=8)

        # Apps tab
        app_top = ttk.Frame(apps_tab)
        app_top.pack(fill="x")
        ttk.Label(app_top, text="Daftar aplikasi pihak ketiga pada HP:").pack(side="left")
        ttk.Button(app_top, text="Muat daftar", command=self.load_packages).pack(side="left", padx=8)
        ttk.Button(app_top, text="Force stop terpilih", command=self.force_stop_selected).pack(side="left", padx=4)
        list_frame = ttk.Frame(apps_tab)
        list_frame.pack(fill="both", expand=True, pady=4)
        self.package_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=18, font=("DejaVu Sans Mono", 10))
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.package_list.yview)
        self.package_list.configure(yscrollcommand=scrollbar.set)
        self.package_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Files tab
        ttk.Label(files_tab, text="Kirim file dari laptop ke folder Download HP.").pack(anchor="w")
        ttk.Button(files_tab, text="Pilih file lalu kirim ke HP", command=self.push_file).pack(anchor="w", pady=8)
        ttk.Label(files_tab, text="Pilih APK untuk memasangnya pada HP yang terhubung.").pack(anchor="w", pady=(16, 0))
        ttk.Button(files_tab, text="Pilih APK lalu instal", command=self.install_apk).pack(anchor="w", pady=8)

        # Usage tab
        ttk.Label(usage_tab, text="Timer sesi pemantauan", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        time_row = ttk.Frame(usage_tab)
        time_row.pack(anchor="w", pady=8)
        ttk.Label(time_row, text="Batas sesi (menit):").pack(side="left")
        ttk.Entry(time_row, textvariable=self.minutes, width=8).pack(side="left", padx=8)
        ttk.Button(time_row, text="Mulai timer", command=self.start_timer).pack(side="left", padx=4)
        ttk.Button(time_row, text="Hentikan timer", command=self.stop_timer).pack(side="left", padx=4)
        self.timer_label = ttk.Label(usage_tab, text="00:00", font=("TkDefaultFont", 24, "bold"))
        self.timer_label.pack(anchor="w", pady=12)

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(0, 8))
        ttk.Label(footer, text="Status: ADB hanya berfungsi setelah otorisasi USB Debugging disetujui pada HP.").pack(anchor="w")

    def on_close(self):
        self.stop_timer()
        self.os_handler.is_worker_running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    RemoteControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
