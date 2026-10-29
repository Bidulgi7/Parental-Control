
#!/usr/bin/env python3
"""Android Remote Control Center: GUI for a user-authorized Android device."""

import os
import subprocess
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog, messagebox, simpledialog

from adb_helper import run_adb_cmd, get_adb_devices
from os_features import OSFeaturesHandler

APP_TITLE = "Android Remote Control Center"
PIN_LOCK = "12345678"


class RemoteControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x780")
        self.root.minsize(950, 640)

        self.os_handler = OSFeaturesHandler(self.run_adb)
        self.device = tk.StringVar()
        self.status = tk.StringVar(
            value="Sambungkan HP melalui USB, aktifkan USB Debugging, lalu Refresh."
        )
        self.minutes = tk.StringVar(value="30")
        self.timer_running = False
        self.timer_start = None
        self.timer_job = None
        self.timer_limit = 0
        self.session_locked = False
        self.packages = []
        self.recording_process = None
        self.lock_job = None

        self.dashboard_connection = tk.StringVar(value="Memeriksa koneksi...")
        self.dashboard_device_name = tk.StringVar(value="-")
        self.dashboard_model = tk.StringVar(value="-")
        self.dashboard_ram = tk.StringVar(value="-")
        self.dashboard_cpu = tk.StringVar(value="-")
        self.dashboard_os = tk.StringVar(value="-")
        self.dashboard_android = tk.StringVar(value="-")
        self.dashboard_security = tk.StringVar(value="-")
        self.dashboard_baseband = tk.StringVar(value="-")
        self.dashboard_kernel = tk.StringVar(value="-")
        self.dashboard_battery = tk.StringVar(value="-")
        self.dashboard_storage = tk.StringVar(value="-")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_devices()
        self.refresh_dashboard_loop()
        self.auto_refresh_cpu_loop()

    def run_adb(self, device_id, *, args, timeout=15):
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def run_adb_local(self, args, timeout=15):
        device_id = self.device.get().strip()
        if not device_id:
            raise RuntimeError(
                "Belum ada perangkat Android yang terhubung dan terotorisasi."
            )
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def show_error(self, title, error):
        self.status.set(str(error))
        messagebox.showerror(title, str(error), parent=self.root)

    def extract_app_name(self, pkg_name):
        known_apps = {
            "com.shopee.id": "Shopee",
            "com.google.android.apps.youtube.music": "YouTube Music",
            "com.google.android.youtube": "YouTube",
            "com.twitter.android": "Twitter",
            "com.instagram.android": "Instagram",
            "instagram": "Instagram",
            "com.facebook.katana": "Facebook",
            "com.facebook.orca": "Messenger",
            "com.whatsapp": "WhatsApp",
            "whatsapp": "WhatsApp",
            "com.ss.android.ugc.trill": "TikTok",
            "com.mobile.legends": "Mobile Legends",
            "com.zhiliaoapp.musically": "TikTok",
            "com.gojek.app": "Gojek",
            "com.grabtaxi.passenger": "Grab",
            "id.dana": "DANA",
            "com.spotify.music": "Spotify",
            "com.android.vending": "Google Play Store",
            "com.google.android.gms": "Google Play Services",
            "com.google.android.play.games": "Google Play Games",
            "com.google.android.apps.photos": "Google Photos",
            "com.google.android.gm": "Gmail",
            "com.google.android.googlequicksearchbox": "Google App",
            "com.google.android.apps.maps": "Google Maps",
            "com.google.android.apps.docs": "Google Drive",
            "com.google.android.calendar": "Google Calendar",
            "com.android.chrome": "Google Chrome",
        }

        lower_pkg = pkg_name.lower()
        if lower_pkg in known_apps:
            return known_apps[lower_pkg]

        for key, value in known_apps.items():
            if key in lower_pkg:
                return value

        ignore_words = {
            "id", "android", "app", "apps", "mobile", "lite",
            "www", "com", "net", "org", "miui",
        }
        parts = pkg_name.split(".")
        valid_parts = [p for p in parts if p.lower() not in ignore_words]

        if valid_parts:
            return valid_parts[-1].capitalize()
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return pkg_name.capitalize()

    # -------------------- EVENTS & TAB --------------------

    def on_mem_tree_click(self, event):
        item = self.mem_tree.identify_row(event.y)
        if item:
            self.mem_tree.selection_set(item)
            self.load_memory_details_for_selected()

    def on_proc_tree_click(self, event):
        # Klik hanya memilih proses; perubahan prioritas tetap lewat tombol.
        item = self.proc_tree.identify_row(event.y)
        if item:
            self.proc_tree.selection_set(item)

    def on_app_tree_click(self, event):
        # Klik hanya memilih aplikasi; force-stop tetap lewat tombol.
        item = self.app_tree.identify_row(event.y)
        if item:
            self.app_tree.selection_set(item)

    def on_tab_changed(self, event):
        try:
            selected_tab = self.notebook.tab(
                self.notebook.select(), "text"
            )
            if selected_tab == "Manajemen Memori":
                if not self.mem_tree.get_children():
                    self.load_memory_packages_list()
            elif selected_tab == "Aplikasi":
                if not self.app_tree.get_children():
                    self.load_packages()
            elif selected_tab == "Manajemen Proses & CPU":
                self.load_processes()
        except (tk.TclError, RuntimeError):
            pass

    def auto_refresh_cpu_loop(self):
        try:
            if self.root.winfo_exists() and hasattr(self, "notebook"):
                selected_tab = self.notebook.tab(
                    self.notebook.select(), "text"
                )
                if selected_tab == "Manajemen Proses & CPU":
                    self.load_processes(auto=True)
                self.root.after(2000, self.auto_refresh_cpu_loop)
        except tk.TclError:
            pass

    # -------------------- MEMORY MANAGEMENT --------------------

    def load_memory_details_for_selected(self):
        selected_item = self.mem_tree.selection()
        if not selected_item:
            messagebox.showinfo(
                "Pilih Aplikasi",
                "Pilih salah satu aplikasi dari tabel terlebih dahulu.",
                parent=self.root,
            )
            return

        item_data = self.mem_tree.item(selected_item[0])["values"]
        app_name, pkg_name = item_data[0], item_data[1]

        self.status.set(f"Mengambil data RAM aktif untuk {app_name}...")
        self.root.update_idletasks()

        try:
            mem_output = self.run_adb_local(
                ["shell", "dumpsys", "meminfo", pkg_name], timeout=10
            )

            native_heap = "0 KB"
            dalvik_heap = "0 KB"
            graphics = "0 KB"
            total_pss = "0 KB"
            total_rss = "0 KB"
            swap_pss = "0 KB"
            has_active_process = False

            for line in mem_output.splitlines():
                line_str = line.strip()
                parts = line_str.split()

                if line_str.startswith("Native Heap") and len(parts) >= 2:
                    for value in parts[1:]:
                        digits = "".join(filter(str.isdigit, value))
                        if digits:
                            native_heap = f"{digits} KB"
                            has_active_process |= int(digits) > 0
                            break

                elif line_str.startswith("Dalvik Heap") and len(parts) >= 2:
                    for value in parts[1:]:
                        digits = "".join(filter(str.isdigit, value))
                        if digits:
                            dalvik_heap = f"{digits} KB"
                            has_active_process |= int(digits) > 0
                            break

                elif line_str.startswith("Graphics:") and len(parts) >= 2:
                    for value in parts[1:]:
                        digits = "".join(filter(str.isdigit, value))
                        if digits:
                            graphics = f"{digits} KB"
                            break

                elif line_str.startswith("TOTAL PSS:") and len(parts) >= 3:
                    digits = "".join(filter(str.isdigit, parts[2]))
                    if digits:
                        total_pss = f"{digits} KB"
                        has_active_process |= int(digits) > 0

                elif line_str.startswith("TOTAL RSS:") and len(parts) >= 3:
                    digits = "".join(filter(str.isdigit, parts[2]))
                    if digits:
                        total_rss = f"{digits} KB"

                elif "TOTAL SWAP PSS:" in line_str or "SWAP PSS:" in line_str:
                    for value in parts:
                        digits = "".join(filter(str.isdigit, value))
                        if digits and int(digits) > 0:
                            swap_pss = f"{digits} KB"
                            break

            external_data = "0 KB"
            try:
                ext_output = self.run_adb_local(
                    ["shell", "du", "-sh", f"/sdcard/Android/data/{pkg_name}"],
                    timeout=5,
                )
                if (
                    ext_output
                    and "No such" not in ext_output
                    and "denied" not in ext_output.lower()
                ):
                    external_data = ext_output.split()[0].strip()
            except Exception:
                pass

            detail_text = (
                "===========================================================\n"
                f" ANALISIS MEMORI & STORAGE: {app_name}\n"
                f" Package: {pkg_name}\n"
                "===========================================================\n\n"
            )

            if not has_active_process:
                detail_text += (
                    "STATUS RAM: Aplikasi sedang tidak digunakan "
                    "atau tidak aktif di RAM.\n\n"
                )
            else:
                detail_text += (
                    "RINCIAN PENGGUNAAN RAM:\n\n"
                    "+-------------------+-------------------+"
                    "--------------------------------------------------+\n"
                    "| Komponen Memori   | Besar Angka       | "
                    "Penjelasan                                      |\n"
                    "+-------------------+-------------------+"
                    "--------------------------------------------------+\n"
                    f"| Native Heap       | {native_heap:<17} | "
                    "Memori native C/C++                              |\n"
                    f"| Dalvik Heap       | {dalvik_heap:<17} | "
                    "Memori Java/Kotlin                               |\n"
                    f"| Graphics          | {graphics:<17} | "
                    "Memori grafis                                   |\n"
                    f"| TOTAL PSS         | {total_pss:<17} | "
                    "Perkiraan RAM proporsional yang digunakan       |\n"
                    f"| TOTAL RSS         | {total_rss:<17} | "
                    "Memori resident termasuk halaman bersama       |\n"
                    f"| SWAP PSS          | {swap_pss:<17} | "
                    "Memori swap proporsional                         |\n"
                    "+-------------------+-------------------+"
                    "--------------------------------------------------+\n\n"
                )

            detail_text += (
                "RINCIAN STORAGE (DATA EKSTERNAL):\n\n"
                f"Data eksternal: {external_data}\n\n"
                "Catatan: Android dapat membatasi akses ke folder data "
                "aplikasi tertentu.\n"
            )

            self.mem_detail_box.delete("1.0", tk.END)
            self.mem_detail_box.insert(tk.END, detail_text)
            self.status.set(f"Analisis memori {app_name} selesai.")

        except Exception as exc:
            self.show_error("Gagal Memuat Detail Memori", exc)

    def _load_package_list_for_tree(self, tree, status_message):
        self.status.set(status_message)
        self.root.update_idletasks()

        output = self.run_adb_local(
            ["shell", "pm", "list", "packages", "-3"], timeout=30
        )
        packages = [
            line.strip().removeprefix("package:").strip()
            for line in output.splitlines()
            if line.strip().startswith("package:")
        ]

        app_list = []
        for pkg in packages:
            app_name = self.extract_app_name(pkg)
            app_list.append((app_name, pkg))

        app_list.sort(key=lambda item: item[0].lower())

        for item in tree.get_children():
            tree.delete(item)

        for app_name, pkg in app_list:
            tree.insert("", "end", values=(app_name, pkg))

        self.status.set(f"Berhasil memuat {len(app_list)} aplikasi.")

    def load_memory_packages_list(self):
        try:
            self._load_package_list_for_tree(
                self.mem_tree, "Memuat daftar aplikasi dari HP..."
            )
        except Exception as exc:
            self.show_error("Gagal memuat aplikasi", exc)

    # -------------------- UPTIME --------------------

    def load_uptime(self):
        try:
            raw_output = self.run_adb_local(
                ["shell", "cat", "/proc/uptime"], timeout=10
            )
            uptime_seconds = float(raw_output.split()[0])
            total_mins = int(uptime_seconds // 60)
            days = total_mins // 1440
            hours = (total_mins % 1440) // 60
            mins = total_mins % 60

            if days > 0:
                time_str = f"{days} hari, {hours} jam, {mins} menit"
            else:
                time_str = f"{hours} jam, {mins} menit"

            self.st_text.delete("1.0", tk.END)
            self.st_text.insert(
                tk.END,
                "INFO WAKTU MENYALA PERANGKAT (UPTIME)\n"
                "===========================================================\n\n"
                f"HP telah menyala selama:\n{time_str}\n\n"
                "Dihitung sejak HP terakhir kali dihidupkan atau direstart.\n",
            )
            self.status.set("Berhasil memuat waktu uptime perangkat.")
        except Exception as exc:
            self.show_error("Gagal memuat uptime", exc)

    # -------------------- PROCESS & CPU --------------------

    def load_processes(self, auto=False):
        try:
            if not self.device.get().strip():
                return

            if not auto:
                self.status.set("Mengambil daftar proses...")
                self.root.update_idletasks()

            raw_processes = self.os_handler.get_process_table(
                self.device.get().strip()
            )

            selected_pids = set()
            for item in self.proc_tree.selection():
                values = self.proc_tree.item(item).get("values")
                if values:
                    selected_pids.add(str(values[0]))

            processed_list = []

            for proc in raw_processes:
                if len(proc) >= 12:
                    (
                        pid, user, status, pr, ni, virt, res, shr,
                        cpu_pct, mem_pct, time_plus, command
                    ) = proc[:12]
                else:
                    pid, user, status, ni, cpu_pct, command = proc[:6]
                    pr = virt = res = shr = mem_pct = time_plus = "-"

                app_label = "Sistem / Layanan Android"
                pkg_name = "-"
                real_cmd = str(command)
                try:
                    real_cpu_float = float(
                        str(cpu_pct).replace("%", "")
                    )
                except (ValueError, TypeError):
                    real_cpu_float = 0.0

                clean_token = real_cmd.strip("()[]{}")

                corrections = {
                    "stagram": "com.instagram.android",
                    "oid.apps.photos": "com.google.android.apps.photos",
                    "wp.wattpad": "com.wattpad.app",
                    "ndroid.systemui": "com.android.systemui",
                }
                for fragment, corrected in corrections.items():
                    if clean_token.startswith(fragment):
                        clean_token = corrected
                        break

                if (
                    "." in clean_token
                    and not clean_token.startswith("/")
                    and not clean_token.startswith("0:")
                    and not clean_token.startswith("top")
                ):
                    parts_dot = clean_token.split(".")
                    if len(parts_dot) >= 2 and not all(
                        part.isdigit() for part in parts_dot
                    ):
                        pkg_name = clean_token
                        app_label = self.extract_app_name(pkg_name)

                is_special_system = False
                if pkg_name == "-":
                    system_names = {
                        "kworker": "Kernel Worker (Latar Belakang)",
                        "surfaceflinger": "SurfaceFlinger (Layar Grafis)",
                        "system_server": "System Server (Utama Android)",
                        "zygote": "Zygote (Inkubator Proses)",
                        "logd": "Log Daemon (Pencatat Sistem)",
                    }
                    for fragment, label in system_names.items():
                        if fragment in real_cmd:
                            app_label = label
                            is_special_system = True
                            break

                if pkg_name != "-" and real_cpu_float > 0:
                    priority = 1
                elif is_special_system:
                    priority = 2
                elif pkg_name != "-":
                    priority = 3
                else:
                    priority = 4

                processed_list.append({
                    "values": (
                        pid, user, status, pr, ni, virt, res, shr,
                        cpu_pct, mem_pct, time_plus, app_label, command,
                    ),
                    "priority": priority,
                    "cpu_float": real_cpu_float,
                })

            processed_list.sort(
                key=lambda item: (item["priority"], -item["cpu_float"])
            )

            for item in self.proc_tree.get_children():
                self.proc_tree.delete(item)

            for process in processed_list:
                new_item = self.proc_tree.insert(
                    "", "end", values=process["values"]
                )
                if str(process["values"][0]) in selected_pids:
                    self.proc_tree.selection_add(new_item)

            if not auto:
                self.status.set(
                    f"Berhasil memuat {len(raw_processes)} proses dari perangkat."
                )
        except Exception as exc:
            if not auto:
                self.status.set(f"Gagal memuat proses: {exc}")

    def change_process_priority(self):
        selected_item = self.proc_tree.selection()
        if not selected_item:
            messagebox.showinfo(
                "Pilih Proses",
                "Pilih salah satu proses dari tabel terlebih dahulu.",
                parent=self.root,
            )
            return

        item_data = self.proc_tree.item(selected_item[0])["values"]
        pid = item_data[0]

        new_nice = simpledialog.askinteger(
            "Ubah Prioritas (Nice)",
            f"PID {pid}:\nMasukkan nilai Nice (-20 sampai 19):",
            minvalue=-20,
            maxvalue=19,
            parent=self.root,
        )
        if new_nice is None:
            return

        try:
            output = self.run_adb_local(
                ["shell", "renice", str(new_nice), str(pid)], timeout=10
            )
            self.status.set(output or f"Perintah renice untuk PID {pid} dikirim.")
            self.load_processes(auto=False)
        except Exception as exc:
            self.show_error("Gagal mengubah prioritas", exc)

    # -------------------- DEVICE & DASHBOARD --------------------

    def refresh_devices(self):
        try:
            devices, unauthorized = get_adb_devices()
            self.device_combo["values"] = devices

            if self.device.get() in devices:
                pass
            elif devices:
                self.device.set(devices[0])
                self.status.set(f"{len(devices)} perangkat terotorisasi.")
            elif unauthorized:
                self.device.set("")
                self.status.set(
                    "HP unauthorized: setujui dialog USB Debugging di layar HP."
                )
            else:
                self.device.set("")
                self.status.set(
                    "Belum ada HP terotorisasi. Periksa kabel USB dan USB Debugging."
                )
        except Exception as exc:
            self.show_error("Gagal mendeteksi perangkat", exc)

    def refresh_dashboard(self):
        if not self.device.get().strip():
            for variable in (
                self.dashboard_connection,
                self.dashboard_device_name,
                self.dashboard_model,
                self.dashboard_ram,
                self.dashboard_cpu,
                self.dashboard_os,
                self.dashboard_android,
                self.dashboard_security,
                self.dashboard_baseband,
                self.dashboard_kernel,
                self.dashboard_battery,
                self.dashboard_storage,
            ):
                variable.set("Tidak terhubung" if variable is self.dashboard_connection else "-")
            return

        try:
            device_name = self.run_adb_local(
                ["shell", "getprop", "ro.product.model"], timeout=6
            )
            model = self.run_adb_local(
                ["shell", "getprop", "ro.product.device"], timeout=6
            )
            os_version = (
                self.run_adb_local(
                    ["shell", "getprop", "ro.miui.ui.version.name"], timeout=6
                )
                or self.run_adb_local(
                    ["shell", "getprop", "ro.build.display.id"], timeout=6
                )
            )
            android_ver = self.run_adb_local(
                ["shell", "getprop", "ro.build.version.release"], timeout=6
            )
            security_patch = self.run_adb_local(
                ["shell", "getprop", "ro.build.version.security_patch"], timeout=6
            )
            baseband = self.run_adb_local(
                ["shell", "getprop", "gsm.version.baseband"], timeout=6
            )
            kernel = self.run_adb_local(
                ["shell", "uname", "-r"], timeout=6
            )

            board_platform = self.run_adb_local(
                ["shell", "getprop", "ro.board.platform"], timeout=6
            )
            cpu_abi = self.run_adb_local(
                ["shell", "getprop", "ro.product.cpu.abi"], timeout=6
            )
            processor_name = (
                f"{board_platform.upper()} ({cpu_abi})"
                if board_platform
                else (cpu_abi or "Tidak diketahui")
            )

            mem_info = self.run_adb_local(
                ["shell", "cat", "/proc/meminfo"], timeout=6
            )
            total_ram_kb = 0
            for line in mem_info.splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        total_ram_kb = int(parts[1])
                    break

            ram_gb = (
                f"{total_ram_kb / (1024 * 1024):.1f} GB"
                if total_ram_kb > 0
                else "Tidak diketahui"
            )

            battery_output = self.run_adb_local(
                ["shell", "dumpsys", "battery"], timeout=6
            )
            battery_level = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in battery_output.splitlines()
                    if line.strip().startswith("level:")
                ),
                "?",
            )

            storage_output = self.run_adb_local(
                ["shell", "df", "-h", "/data"], timeout=6
            )
            storage_lines = storage_output.splitlines()
            storage_str = "Tidak tersedia"
            if len(storage_lines) >= 2:
                columns = storage_lines[-1].split()
                if len(columns) >= 5:
                    storage_str = (
                        f"Terpakai {columns[2]} dari {columns[1]} "
                        f"({columns[4]} terpakai)"
                    )

            self.dashboard_connection.set("Terhubung melalui ADB")
            self.dashboard_device_name.set(device_name or "Perangkat Android")
            self.dashboard_model.set(model or "-")
            self.dashboard_ram.set(ram_gb)
            self.dashboard_cpu.set(processor_name)
            self.dashboard_os.set(os_version or "Android OS")
            self.dashboard_android.set(android_ver or "-")
            self.dashboard_security.set(security_patch or "-")
            self.dashboard_baseband.set(baseband or "-")
            self.dashboard_kernel.set(kernel or "-")
            self.dashboard_battery.set(f"{battery_level}%")
            self.dashboard_storage.set(storage_str)

        except Exception as exc:
            self.dashboard_connection.set("Gagal membaca detail perangkat")
            self.status.set(str(exc))

    def refresh_dashboard_loop(self):
        try:
            if self.root.winfo_exists():
                self.refresh_dashboard()
                self.root.after(10000, self.refresh_dashboard_loop)
        except tk.TclError:
            pass

    def device_info(self):
        try:
            model = self.run_adb_local(
                ["shell", "getprop", "ro.product.model"]
            )
            android = self.run_adb_local(
                ["shell", "getprop", "ro.build.version.release"]
            )
            serial = self.device.get()
            messagebox.showinfo(
                "Info perangkat",
                f"Model: {model}\nAndroid: {android}\nADB ID: {serial}",
                parent=self.root,
            )
        except Exception as exc:
            self.show_error("Gagal membaca perangkat", exc)

    # -------------------- SCRCPY --------------------

    def start_mirroring(self):
        self._start_scrcpy(screen_off=False)

    def start_mirroring_screen_off(self):
        if messagebox.askyesno(
            "Konfirmasi",
            "Coba matikan layar fisik HP saat mirroring berjalan?",
            parent=self.root,
        ):
            self._start_scrcpy(screen_off=True)

    def start_recording(self):
        if not self.device.get():
            messagebox.showwarning(
                "Pilih perangkat",
                "Pilih HP yang terotorisasi terlebih dahulu.",
                parent=self.root,
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"record_{timestamp}.mp4"

        try:
            self.recording_process = subprocess.Popen(
                [
                    "scrcpy", "-s", self.device.get(),
                    "--record", filename,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.status.set(f"Rekaman layar dimulai: {filename}")
            messagebox.showinfo(
                "Rekam Layar",
                f"Perekaman layar aktif.\nFile: {filename}\n\n"
                "Tutup jendela scrcpy untuk menghentikan rekaman.",
                parent=self.root,
            )
        except FileNotFoundError:
            self.show_error(
                "scrcpy tidak ditemukan",
                "Pasang scrcpy dengan: sudo apt install scrcpy",
            )
        except Exception as exc:
            self.show_error("Gagal memulai rekaman layar", exc)

    def _start_scrcpy(self, screen_off):
        if not self.device.get():
            messagebox.showwarning(
                "Pilih perangkat",
                "Pilih HP yang terotorisasi terlebih dahulu.",
                parent=self.root,
            )
            return

        try:
            args = ["scrcpy", "-s", self.device.get()]
            if screen_off:
                args.append("--turn-screen-off")

            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.status.set("scrcpy dijalankan di jendela terpisah.")
        except FileNotFoundError:
            self.show_error(
                "scrcpy tidak ditemukan",
                "Pasang scrcpy dengan: sudo apt install scrcpy",
            )
        except Exception as exc:
            self.show_error("Gagal memulai mirroring", exc)

    # -------------------- SCREEN & TIMER --------------------

    def lock_screen(self):
        try:
            # Meminta Android mematikan layar tanpa mengirim toggle Power
            # berulang kali. Efeknya dapat berbeda menurut perangkat.
            self.run_adb_local(
                ["shell", "input", "keyevent", "223"], timeout=10
            )
            self.status.set("Perintah tidur layar telah dikirim ke HP.")
        except Exception as exc:
            self.show_error("Gagal mengunci layar", exc)

    def wake_screen(self):
        try:
            self.run_adb_local(
                ["shell", "input", "keyevent", "224"], timeout=10
            )
            self.status.set("Perintah membangunkan layar telah dikirim.")
        except Exception as exc:
            self.show_error("Gagal membangunkan layar", exc)

    def start_timer(self):
        try:
            minutes = int(self.minutes.get())
            if minutes < 1 or minutes > 1440:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Batas tidak valid",
                "Masukkan angka 1 sampai 1440 menit.",
                parent=self.root,
            )
            return

        # Membatalkan timer lama sebelum memulai timer baru.
        self._cancel_timer_job()
        self.timer_running = True
        self.session_locked = False
        self.timer_start = time.monotonic()
        self.timer_limit = minutes * 60
        self.timer_label.configure(text=f"{minutes:02d}:00")
        self.status.set(f"Timer sesi dimulai: {minutes} menit.")
        self._tick_timer()

    def _cancel_timer_job(self):
        if self.timer_job is not None:
            try:
                self.root.after_cancel(self.timer_job)
            except tk.TclError:
                pass
            self.timer_job = None

    def stop_timer(self):
        # Tombol Hentikan Timer membatalkan timer dan status sesi terkunci.
        self.timer_running = False
        self.session_locked = False
        self.timer_start = None
        self._cancel_timer_job()
        self.timer_label.configure(text="00:00")
        self.status.set("Timer dihentikan. Status sesi pada aplikasi dibuka.")

    def unlock_session(self):
        if not self.device.get().strip():
            messagebox.showwarning(
                "Perangkat belum dipilih",
                "Pilih perangkat Android terlebih dahulu.",
                parent=self.root,
            )
            return

        # Minta konfirmasi karena tindakan ini mengirim input ke HP.
        if not messagebox.askyesno(
            "Konfirmasi",
            "Coba bangunkan layar dan kirim PIN yang dikonfigurasi "
            "ke perangkat terhubung?",
            parent=self.root,
        ):
            return

        try:
            self.wake_screen()
            self.root.update_idletasks()
            time.sleep(0.6)
            self.run_adb_local(
                ["shell", "input", "swipe", "500", "1500", "500", "500", "300"]
            )
            time.sleep(0.6)
            self.run_adb_local(
                ["shell", "input", "text", PIN_LOCK]
            )
            self.run_adb_local(
                ["shell", "input", "keyevent", "66"]
            )
            self.session_locked = False
            self.status.set(
                "Input pembukaan layar telah dikirim. "
                "Keberhasilannya bergantung pada keamanan perangkat."
            )
            messagebox.showinfo(
                "Perintah dikirim",
                "Input pembukaan layar telah dikirim. "
                "Jika PIN perangkat berbeda atau metode input ditolak, "
                "buka kunci langsung pada HP.",
                parent=self.root,
            )
        except Exception as exc:
            self.show_error("Gagal membuka kunci", exc)

    def _tick_timer(self):
        if not self.timer_running or self.timer_start is None:
            return

        elapsed = int(time.monotonic() - self.timer_start)
        remaining = max(0, self.timer_limit - elapsed)

        self.timer_label.configure(
            text=f"{remaining // 60:02d}:{remaining % 60:02d}"
        )

        if remaining <= 0:
            # Jangan panggil stop_timer() di sini karena fungsi itu
            # menghapus session_locked.
            self.timer_running = False
            self.timer_start = None
            self.timer_job = None
            self.session_locked = True
            self.timer_label.configure(text="TERKUNCI")

            try:
                self.lock_screen()
            except Exception:
                pass

            self.status.set(
                "Batas waktu habis. Perintah tidur layar telah dikirim."
            )
            messagebox.showwarning(
                "Batas Waktu Habis",
                "Batas waktu sesi habis. Perintah tidur layar telah dikirim "
                "ke HP.\n\n"
                "Status ini tidak menjamin HP terkunci total; "
                "keamanan layar tetap mengikuti pengaturan Android.",
                parent=self.root,
            )
            return

        self.timer_job = self.root.after(1000, self._tick_timer)

    def _enforce_lock_loop(self):
        # Tidak mengirim tombol daya berulang kali. Keyevent Power
        # dapat menjadi toggle dan menyebabkan layar menyala kembali.
        if self.session_locked:
            self.status.set(
                "Status timer terkunci. Periksa kunci layar Android "
                "pada perangkat."
            )

    # -------------------- APPLICATION MANAGEMENT --------------------

    def load_packages(self):
        try:
            self._load_package_list_for_tree(
                self.app_tree,
                "Mengambil daftar aplikasi dan mengurutkannya...",
            )
        except Exception as exc:
            self.show_error("Gagal memuat aplikasi", exc)

    def force_stop_selected(self):
        selected_items = self.app_tree.selection()
        if not selected_items:
            messagebox.showinfo(
                "Pilih aplikasi",
                "Pilih satu atau beberapa aplikasi dari tabel terlebih dahulu.",
                parent=self.root,
            )
            return

        selected_pkgs = [
            self.app_tree.item(item)["values"][1]
            for item in selected_items
        ]
        if not messagebox.askyesno(
            "Konfirmasi force stop",
            "Hentikan paksa aplikasi berikut?\n\n"
            + "\n".join(selected_pkgs),
            parent=self.root,
        ):
            return

        try:
            for package in selected_pkgs:
                pkg = str(package).strip()
                if pkg:
                    self.run_adb_local(
                        ["shell", "am", "force-stop", pkg], timeout=20
                    )

            self.status.set(
                f"Perintah force-stop dikirim untuk {len(selected_pkgs)} aplikasi."
            )
            messagebox.showinfo(
                "Selesai",
                "Perintah force-stop telah dikirim ke perangkat.",
                parent=self.root,
            )
        except Exception as exc:
            self.show_error("Gagal force stop", exc)

    # -------------------- FILE TRANSFER & APK --------------------

    def push_file(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Pilih file untuk dikirim"
        )
        if not path:
            return

        try:
            name = os.path.basename(path)
            self.run_adb_local(
                ["push", path, f"/sdcard/Download/{name}"], timeout=180
            )
            self.status.set(f"File dikirim: {name}")
            messagebox.showinfo(
                "Transfer selesai",
                f"File dikirim ke Download/{name} pada HP.",
                parent=self.root,
            )
        except Exception as exc:
            self.show_error("Transfer gagal", exc)

    def install_apk(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Pilih file APK",
            filetypes=[("Android APK", "*.apk"), ("Semua file", "*.*")],
        )
        if not path:
            return

        if not path.lower().endswith(".apk"):
            messagebox.showwarning(
                "File tidak valid",
                "Pilih file dengan ekstensi .apk.",
                parent=self.root,
            )
            return

        if not messagebox.askyesno(
            "Konfirmasi instalasi",
            f"Instal APK ini pada HP?\n\n{path}",
            parent=self.root,
        ):
            return

        try:
            output = self.run_adb_local(
                ["install", "-r", path], timeout=240
            )
            self.status.set(output or "Perintah instalasi selesai.")
            messagebox.showinfo(
                "Instalasi selesai",
                output or "ADB menyelesaikan instalasi.",
                parent=self.root,
            )
        except Exception as exc:
            self.show_error("Instalasi gagal", exc)

    # -------------------- USER INTERFACE --------------------

    def _build_ui(self):
        self.root.configure(bg="#F3F6FC")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=32)

        BG = "#F3F6FC"
        CARD = "#FFFFFF"
        NAVY = "#17243A"
        BLUE = "#356DF3"
        TEXT = "#243149"
        MUTED = "#68758B"
        BORDER = "#DCE4F0"

        style.configure(".", font=("DejaVu Sans", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure(
            "Header.TLabel",
            background=BG,
            foreground=NAVY,
            font=("DejaVu Sans", 21, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=BG,
            foreground=MUTED,
            font=("DejaVu Sans", 9),
        )
        style.configure(
            "TLabelframe",
            background=CARD,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=CARD,
            foreground=NAVY,
            font=("DejaVu Sans", 10, "bold"),
        )
        style.configure(
            "TButton",
            background=CARD,
            foreground=TEXT,
            bordercolor=BORDER,
            padding=(13, 8),
            relief="flat",
            font=("DejaVu Sans", 9, "bold"),
        )
        style.map(
            "TButton",
            background=[
                ("active", "#E8EEFF"),
                ("pressed", "#D8E3FF"),
            ],
            foreground=[("disabled", "#9AA5B5")],
        )
        style.configure(
            "Accent.TButton",
            background=BLUE,
            foreground="#FFFFFF",
            bordercolor=BLUE,
            padding=(14, 9),
        )
        style.configure(
            "TNotebook",
            background=BG,
            borderwidth=0,
            tabmargins=(2, 5, 2, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#E8EDF6",
            foreground=MUTED,
            padding=(15, 10),
            font=("DejaVu Sans", 9, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[
                ("selected", CARD),
                ("active", "#DCE6FA"),
            ],
            foreground=[
                ("selected", BLUE),
                ("active", NAVY),
            ],
        )

        header = ttk.Frame(self.root, padding=12)
        header.pack(fill="x")
        ttk.Label(
            header, text=APP_TITLE, style="Header.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="USB + ADB",
            wraplength=940,
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 8))

        device_frame = ttk.LabelFrame(
            self.root, text="Perangkat Android", padding=10
        )
        device_frame.pack(fill="x", padx=12, pady=4)
        ttk.Label(device_frame, text="Device ID:").pack(side="left")

        self.device_combo = ttk.Combobox(
            device_frame,
            textvariable=self.device,
            state="readonly",
            width=32,
        )
        self.device_combo.pack(side="left", padx=8)

        ttk.Button(
            device_frame, text="Refresh", command=self.refresh_devices
        ).pack(side="left")
        ttk.Button(
            device_frame, text="Info perangkat", command=self.device_info
        ).pack(side="left", padx=6)
        ttk.Label(
            device_frame,
            textvariable=self.status,
            wraplength=450,
        ).pack(side="left", padx=12, fill="x", expand=True)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        dashboard_tab = ttk.Frame(self.notebook, padding=16)
        mirror_usage_tab = ttk.Frame(self.notebook, padding=12)
        apps_tab = ttk.Frame(self.notebook, padding=12)
        files_tab = ttk.Frame(self.notebook, padding=12)
        mem_tab = ttk.Frame(self.notebook, padding=12)
        process_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(dashboard_tab, text="Dashboard")
        self.notebook.add(mirror_usage_tab, text="Mirroring & Uptime")
        self.notebook.add(apps_tab, text="Aplikasi")
        self.notebook.add(mem_tab, text="Manajemen Memori")
        self.notebook.add(process_tab, text="Manajemen Proses & CPU")
        self.notebook.add(files_tab, text="Transfer File")

        # Tab Manajemen Memori
        mem_top = ttk.Frame(mem_tab)
        mem_top.pack(fill="x", pady=6)
        ttk.Button(
            mem_top,
            text="🔄 Refresh Aplikasi",
            command=self.load_memory_packages_list,
        ).pack(side="left")
        ttk.Button(
            mem_top,
            text="🔄 Refresh Analisa RAM",
            command=self.load_memory_details_for_selected,
        ).pack(side="left", padx=8)

        mem_split = ttk.PanedWindow(mem_tab, orient="horizontal")
        mem_split.pack(fill="both", expand=True, pady=6)
        mem_left = ttk.Frame(mem_split)
        mem_right = ttk.Frame(mem_split)
        mem_split.add(mem_left, weight=1)
        mem_split.add(mem_right, weight=1)

        self.mem_tree = ttk.Treeview(
            mem_left,
            columns=("Nama Aplikasi", "Package"),
            show="headings",
            height=18,
        )
        self.mem_tree.heading(
            "Nama Aplikasi", text="Nama Aplikasi (Label)"
        )
        self.mem_tree.heading("Package", text="Nama Paket (Package Name)")
        self.mem_tree.column("Nama Aplikasi", width=200, anchor="w")
        self.mem_tree.column("Package", width=500, anchor="w")
        self.mem_tree.bind(
            "<ButtonRelease-1>", self.on_mem_tree_click
        )

        mem_scroll = ttk.Scrollbar(
            mem_left, orient="vertical", command=self.mem_tree.yview
        )
        self.mem_tree.configure(yscrollcommand=mem_scroll.set)
        self.mem_tree.pack(side="left", fill="both", expand=True)
        mem_scroll.pack(side="right", fill="y")

        self.mem_detail_box = tk.Text(
            mem_right,
            wrap="word",
            bg="#121212",
            fg="#00FF00",
            font=("DejaVu Sans Mono", 10),
        )
        self.mem_detail_box.pack(fill="both", expand=True)

        # Dashboard
        ttk.Label(
            dashboard_tab,
            text="Ringkasan Perangkat",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        info_frame = ttk.LabelFrame(
            dashboard_tab,
            text="Informasi Lengkap HP (About Phone)",
            padding=12,
        )
        info_frame.pack(fill="x", pady=4)

        dashboard_items = [
            ("Status koneksi", self.dashboard_connection),
            ("Nama perangkat", self.dashboard_device_name),
            ("Model", self.dashboard_model),
            ("RAM", self.dashboard_ram),
            ("CPU / Chipset", self.dashboard_cpu),
            ("Versi OS / UI", self.dashboard_os),
            ("Versi Android", self.dashboard_android),
            ("Update keamanan", self.dashboard_security),
            ("Versi pita basis", self.dashboard_baseband),
            ("Versi kernel", self.dashboard_kernel),
            ("Baterai", self.dashboard_battery),
            ("Penyimpanan", self.dashboard_storage),
        ]

        for label, variable in dashboard_items:
            line = ttk.Frame(info_frame)
            line.pack(fill="x", pady=3)
            ttk.Label(line, text=label, width=22).pack(side="left")
            ttk.Label(
                line,
                textvariable=variable,
                font=("TkDefaultFont", 10, "bold"),
            ).pack(side="left", fill="x", expand=True)

        dashboard_buttons = ttk.Frame(dashboard_tab)
        dashboard_buttons.pack(fill="x", pady=12)
        ttk.Button(
            dashboard_buttons,
            text="Perbarui informasi",
            command=self.refresh_dashboard,
        ).pack(side="left")
        ttk.Button(
            dashboard_buttons,
            text="Refresh perangkat",
            command=self.refresh_devices,
        ).pack(side="left", padx=8)

        # Mirroring, rekaman, timer, dan uptime
        ttk.Label(
            mirror_usage_tab,
            text="Kontrol Layar & Perekaman (Scrcpy)",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        control_row = ttk.Frame(mirror_usage_tab)
        control_row.pack(anchor="w", pady=4)

        ttk.Button(
            control_row, text="Mulai Mirroring",
            command=self.start_mirroring,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            control_row, text="Mirroring + Layar Mati",
            command=self.start_mirroring_screen_off,
        ).pack(side="left", padx=6)
        ttk.Button(
            control_row, text="Rekam Layar",
            command=self.start_recording,
        ).pack(side="left", padx=6)
        ttk.Button(
            control_row, text="Kunci Layar HP",
            command=self.lock_screen,
        ).pack(side="left", padx=6)
        ttk.Button(
            control_row, text="Bangunkan Layar",
            command=self.wake_screen,
        ).pack(side="left", padx=6)

        timer_box = ttk.LabelFrame(
            mirror_usage_tab,
            text="Timer Batas Sesi & Penguncian",
            padding=8,
        )
        timer_box.pack(fill="x", pady=8)

        time_row = ttk.Frame(timer_box)
        time_row.pack(anchor="w", pady=2)
        ttk.Label(time_row, text="Batas sesi (menit):").pack(side="left")
        ttk.Entry(
            time_row, textvariable=self.minutes, width=8
        ).pack(side="left", padx=8)
        ttk.Button(
            time_row, text="Mulai Timer", command=self.start_timer
        ).pack(side="left", padx=4)
        ttk.Button(
            time_row, text="Hentikan Timer", command=self.stop_timer
        ).pack(side="left", padx=4)
        ttk.Button(
            time_row,
            text="🔓 Buka Kunci",
            command=self.unlock_session,
        ).pack(side="left", padx=12)

        self.timer_label = ttk.Label(
            timer_box, text="00:00",
            font=("TkDefaultFont", 14, "bold"),
        )
        self.timer_label.pack(anchor="w", pady=4)

        st_box = ttk.LabelFrame(
            mirror_usage_tab,
            text="Waktu Menyala Perangkat (Uptime)",
            padding=8,
        )
        st_box.pack(fill="both", expand=True, pady=6)

        st_top = ttk.Frame(st_box)
        st_top.pack(fill="x", pady=4)
        ttk.Button(
            st_top,
            text="⏱️ Cek Berapa Lama HP Menyala",
            command=self.load_uptime,
        ).pack(side="left", padx=4)

        st_frame = ttk.Frame(st_box)
        st_frame.pack(fill="both", expand=True, pady=4)
        st_scroll = ttk.Scrollbar(st_frame, orient="vertical")
        st_scroll.pack(side="right", fill="y")
        self.st_text = tk.Text(
            st_frame,
            wrap="word",
            bg="#121212",
            fg="#FFFFFF",
            font=("DejaVu Sans Mono", 10),
            yscrollcommand=st_scroll.set,
        )
        self.st_text.pack(side="left", fill="both", expand=True)
        st_scroll.config(command=self.st_text.yview)

        # Manajemen Proses & CPU
        proc_top = ttk.Frame(process_tab)
        proc_top.pack(fill="x", pady=6)
        ttk.Button(
            proc_top,
            text="🔄 Muat Ulang Real-Time",
            command=self.load_processes,
        ).pack(side="left")
        ttk.Button(
            proc_top,
            text="⚙️ Ubah Prioritas (Renice)",
            command=self.change_process_priority,
        ).pack(side="left", padx=8)

        tree_frame = ttk.Frame(process_tab)
        tree_frame.pack(fill="both", expand=True, pady=4)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        proc_columns = (
            "PID", "USER", "STATUS", "PR", "NI", "VIRT", "RES",
            "SHR", "CPU (%)", "MEM (%)", "TIME+",
            "Nama Aplikasi / Proses", "Command Asli (Raw)",
        )
        self.proc_tree = ttk.Treeview(
            tree_frame,
            columns=proc_columns,
            show="headings",
            height=25,
        )

        headings = {
            "PID": "PID",
            "USER": "User",
            "STATUS": "Status",
            "PR": "PR",
            "NI": "NI",
            "VIRT": "VIRT",
            "RES": "RES",
            "SHR": "SHR",
            "CPU (%)": "CPU (%)",
            "MEM (%)": "MEM (%)",
            "TIME+": "Waktu CPU",
            "Nama Aplikasi / Proses": "Nama Aplikasi / Proses",
            "Command Asli (Raw)": "Command Asli (Raw)",
        }
        widths = {
            "PID": 90,
            "USER": 100,
            "STATUS": 150,
            "PR": 80,
            "NI": 80,
            "VIRT": 75,
            "RES": 75,
            "SHR": 75,
            "CPU (%)": 65,
            "MEM (%)": 65,
            "TIME+": 120,
            "Nama Aplikasi / Proses": 400,
            "Command Asli (Raw)": 500,
        }

        for column in proc_columns:
            self.proc_tree.heading(column, text=headings[column])
            self.proc_tree.column(
                column,
                width=widths[column],
                anchor="w" if column in (
                    "Nama Aplikasi / Proses", "Command Asli (Raw)"
                ) else "center",
                stretch=column not in ("PID", "PR", "NI"),
            )

        self.proc_tree.bind(
            "<ButtonRelease-1>", self.on_proc_tree_click
        )

        proc_v_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.proc_tree.yview
        )
        proc_h_scroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.proc_tree.xview
        )
        self.proc_tree.configure(
            yscrollcommand=proc_v_scroll.set,
            xscrollcommand=proc_h_scroll.set,
        )
        self.proc_tree.grid(row=0, column=0, sticky="nsew")
        proc_v_scroll.grid(row=0, column=1, sticky="ns")
        proc_h_scroll.grid(row=1, column=0, sticky="ew")

        # Transfer File
        ttk.Label(
            files_tab,
            text="Kirim file dari laptop ke folder Download HP.",
        ).pack(anchor="w")
        ttk.Button(
            files_tab,
            text="Pilih file lalu kirim ke HP",
            command=self.push_file,
        ).pack(anchor="w", pady=8)
        ttk.Label(
            files_tab,
            text="Pilih APK untuk memasangnya pada HP yang terhubung.",
        ).pack(anchor="w", pady=(16, 0))
        ttk.Button(
            files_tab,
            text="Pilih APK lalu instal",
            command=self.install_apk,
        ).pack(anchor="w", pady=8)

        # Aplikasi
        app_top = ttk.Frame(apps_tab)
        app_top.pack(fill="x", pady=6)
        ttk.Button(
            app_top, text="🔄 Refresh", command=self.load_packages
        ).pack(side="left")
        ttk.Button(
            app_top,
            text="Force Stop Terpilih",
            command=self.force_stop_selected,
        ).pack(side="left", padx=8)

        app_frame = ttk.Frame(apps_tab)
        app_frame.pack(fill="both", expand=True, pady=4)

        self.app_tree = ttk.Treeview(
            app_frame,
            columns=("Nama Aplikasi", "Nama Paket (Package)"),
            show="headings",
            height=20,
            selectmode="extended",
        )
        self.app_tree.heading(
            "Nama Aplikasi", text="Nama Aplikasi (Urut Abjad)"
        )
        self.app_tree.heading(
            "Nama Paket (Package)", text="Nama Paket (Package Name)"
        )
        self.app_tree.column("Nama Aplikasi", width=320, anchor="w")
        self.app_tree.column(
            "Nama Paket (Package)", width=600, anchor="w"
        )
        self.app_tree.bind(
            "<ButtonRelease-1>", self.on_app_tree_click
        )

        app_scroll = ttk.Scrollbar(
            app_frame, orient="vertical", command=self.app_tree.yview
        )
        self.app_tree.configure(yscrollcommand=app_scroll.set)
        self.app_tree.pack(side="left", fill="both", expand=True)
        app_scroll.pack(side="right", fill="y")

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(0, 8))
        ttk.Label(footer, text="Status: ADB aktif.").pack(anchor="w")

    def on_close(self):
        self.timer_running = False
        self._cancel_timer_job()

        if self.lock_job is not None:
            try:
                self.root.after_cancel(self.lock_job)
            except tk.TclError:
                pass
            self.lock_job = None

        self.root.destroy()


def main():
    root = tk.Tk()
    app = RemoteControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

