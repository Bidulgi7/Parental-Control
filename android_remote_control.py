#!/usr/bin/env python3
"""Android Remote Control Center: GUI for a user-authorized Android device."""

import os
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Android Remote Control Center"


class RemoteControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x720")
        self.root.minsize(820, 600)
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

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self.root, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="USB + ADB • Gunakan hanya pada perangkat milikmu atau yang kamu punya izin untuk kelola.",
            wraplength=940
        ).pack(anchor="w", pady=(4, 8))

        device_frame = ttk.LabelFrame(self.root, text="Perangkat Android", padding=10)
        device_frame.pack(fill="x", padx=12, pady=4)
        ttk.Label(device_frame, text="Device ID:").pack(side="left")
        self.device_combo = ttk.Combobox(
            device_frame, textvariable=self.device, state="readonly", width=32
        )
        self.device_combo.pack(side="left", padx=8)
        ttk.Button(device_frame, text="Refresh", command=self.refresh_devices).pack(side="left")
        ttk.Button(device_frame, text="Info perangkat", command=self.device_info).pack(side="left", padx=6)
        ttk.Label(device_frame, textvariable=self.status, wraplength=450).pack(
            side="left", padx=12, fill="x", expand=True
        )

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        mirror_tab = ttk.Frame(notebook, padding=12)
        apps_tab = ttk.Frame(notebook, padding=12)
        files_tab = ttk.Frame(notebook, padding=12)
        usage_tab = ttk.Frame(notebook, padding=12)
        notebook.add(mirror_tab, text="Mirroring & Kontrol")
        notebook.add(apps_tab, text="Aplikasi")
        notebook.add(files_tab, text="Transfer File")
        notebook.add(usage_tab, text="Screen Time")

        ttk.Label(mirror_tab, text="Mirroring menggunakan scrcpy", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(
            mirror_tab,
            text="scrcpy membuka jendela layar HP terpisah dan meneruskan klik, scroll, serta ketikan keyboard."
        ).pack(anchor="w", pady=6)
        row = ttk.Frame(mirror_tab)
        row.pack(anchor="w", pady=8)
        ttk.Button(row, text="Mulai mirroring", command=self.start_mirroring).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Mirroring + layar HP mati", command=self.start_mirroring_screen_off).pack(side="left", padx=8)
        ttk.Button(row, text="Kunci layar HP", command=self.lock_screen).pack(side="left", padx=8)
        ttk.Button(row, text="Bangunkan layar", command=self.wake_screen).pack(side="left", padx=8)
        ttk.Label(
            mirror_tab,
            text="Catatan: opsi layar mati bergantung pada versi scrcpy/Android. Tutup jendela scrcpy untuk menghentikan sesi."
        ).pack(anchor="w", pady=10)

        app_top = ttk.Frame(apps_tab)
        app_top.pack(fill="x")
        ttk.Label(app_top, text="Daftar aplikasi pihak ketiga pada HP:").pack(side="left")
        ttk.Button(app_top, text="Muat daftar", command=self.load_packages).pack(side="left", padx=8)
        ttk.Button(app_top, text="Force stop terpilih", command=self.force_stop_selected).pack(side="left", padx=4)
        ttk.Label(
            apps_tab,
            text="Force stop hanya menghentikan aplikasi sementara; aplikasi dapat dibuka lagi dari HP."
        ).pack(anchor="w", pady=6)
        list_frame = ttk.Frame(apps_tab)
        list_frame.pack(fill="both", expand=True, pady=4)
        self.package_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=18)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.package_list.yview)
        self.package_list.configure(yscrollcommand=scrollbar.set)
        self.package_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(files_tab, text="Kirim file dari laptop ke folder Download HP.").pack(anchor="w")
        ttk.Button(files_tab, text="Pilih file lalu kirim ke HP", command=self.push_file).pack(anchor="w", pady=8)
        ttk.Label(files_tab, text="Pilih APK untuk memasangnya pada HP yang terhubung.").pack(anchor="w", pady=(16, 0))
        ttk.Button(files_tab, text="Pilih APK lalu instal", command=self.install_apk).pack(anchor="w", pady=8)
        ttk.Label(
            files_tab,
            text="Transfer dan instalasi memerlukan perangkat berstatus 'device' di ADB. APK tetap perlu izin instalasi yang sesuai."
        ).pack(anchor="w", pady=8)

        ttk.Label(usage_tab, text="Timer sesi pemantauan", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(usage_tab, text="Timer ini menghitung sesi sejak tombol Mulai ditekan, bukan total penggunaan harian Android.").pack(anchor="w", pady=6)
        time_row = ttk.Frame(usage_tab)
        time_row.pack(anchor="w", pady=8)
        ttk.Label(time_row, text="Batas sesi (menit):").pack(side="left")
        ttk.Entry(time_row, textvariable=self.minutes, width=8).pack(side="left", padx=8)
        ttk.Button(time_row, text="Mulai timer", command=self.start_timer).pack(side="left", padx=4)
        ttk.Button(time_row, text="Hentikan timer", command=self.stop_timer).pack(side="left", padx=4)
        self.timer_label = ttk.Label(usage_tab, text="00:00", font=("TkDefaultFont", 24, "bold"))
        self.timer_label.pack(anchor="w", pady=12)
        ttk.Label(usage_tab, text="Saat batas tercapai, aplikasi meminta konfirmasi sebelum mengunci layar HP.").pack(anchor="w")

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(0, 8))
        ttk.Label(footer, text="Status: ADB hanya berfungsi setelah otorisasi USB Debugging disetujui pada HP.").pack(anchor="w")

    def run_adb(self, args, timeout=15):
        device = self.device.get().strip()
        if not device:
            raise RuntimeError("Pilih perangkat terlebih dahulu.")
        command = ["adb", "-s", device, *args]
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or "Perintah ADB gagal.")
        return result.stdout.strip()

    def show_error(self, title, error):
        self.status.set(str(error))
        messagebox.showerror(title, str(error), parent=self.root)

    def refresh_devices(self):
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "ADB gagal.")
            devices = []
            unauthorized = []
            for line in result.stdout.splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2:
                    if parts[1] == "device":
                        devices.append(parts[0])
                    elif parts[1] == "unauthorized":
                        unauthorized.append(parts[0])
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

    def device_info(self):
        try:
            model = self.run_adb(["shell", "getprop", "ro.product.model"])
            android = self.run_adb(["shell", "getprop", "ro.build.version.release"])
            serial = self.device.get()
            messagebox.showinfo("Info perangkat", f"Model: {model}\nAndroid: {android}\nADB ID: {serial}", parent=self.root)
        except Exception as exc:
            self.show_error("Gagal membaca perangkat", exc)

    def start_mirroring(self):
        self._start_scrcpy(screen_off=False)

    def start_mirroring_screen_off(self):
        if not messagebox.askyesno(
            "Konfirmasi",
            "Coba matikan layar fisik HP saat mirroring berjalan? Ini bergantung pada dukungan scrcpy/Android.",
            parent=self.root
        ):
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
            self.run_adb(["shell", "input", "keyevent", "26"])
            self.status.set("Perintah tombol daya dikirim.")
        except Exception as exc:
            self.show_error("Gagal mengunci layar", exc)

    def wake_screen(self):
        try:
            self.run_adb(["shell", "input", "keyevent", "224"])
            self.status.set("Perintah bangunkan layar dikirim.")
        except Exception as exc:
            self.show_error("Gagal membangunkan layar", exc)

    def load_packages(self):
        try:
            output = self.run_adb(["shell", "pm", "list", "packages", "-3"], timeout=30)
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
        if not messagebox.askyesno(
            "Konfirmasi force stop",
            "Hentikan aplikasi berikut?\n\n" + "\n".join(selected),
            parent=self.root
        ):
            return
        try:
            for package in selected:
                self.run_adb(["shell", "am", "force-stop", package], timeout=20)
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
            self.run_adb(["push", path, f"/sdcard/Download/{name}"], timeout=180)
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
            output = self.run_adb(["install", "-r", path], timeout=240)
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
            if messagebox.askyesno(
                "Batas waktu tercapai",
                "Batas sesi tercapai. Kirim perintah tombol daya ke HP untuk mengunci/mematikan layar?",
                parent=self.root
            ):
                self.lock_screen()
            return
        self.timer_job = self.root.after(1000, self._tick_timer)

    def on_close(self):
        self.stop_timer()
        self.root.destroy()


def main():
    root = tk.Tk()
    RemoteControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
