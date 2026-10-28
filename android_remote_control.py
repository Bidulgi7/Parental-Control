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
        self.root.geometry("1100x780")
        self.root.minsize(900, 640)

        self.os_handler = OSFeaturesHandler(self.run_adb)
        self.device = tk.StringVar()
        self.status = tk.StringVar(value="Sambungkan HP melalui USB, aktifkan USB Debugging, lalu Refresh.")
        self.minutes = tk.StringVar(value="30")
        self.timer_running = False
        self.timer_start = None
        self.timer_job = None
        self.session_locked = False
        self.packages = []
        self.recording_process = None

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
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_dashboard_loop()

    def run_adb(self, device_id, *, args, timeout=15):
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def run_adb_local(self, args, timeout=15):
        device_id = self.device.get().strip()
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def show_error(self, title, error):
        self.status.set(str(error))
        messagebox.showerror(title, str(error), parent=self.root)

    def load_memory_details_for_selected(self):
        """Mengambil data RAM aktif secara real-time dan mendeteksi apakah aplikasi sedang aktif atau tidak."""
        selected_item = self.mem_tree.selection()
        if not selected_item:
            messagebox.showinfo("Pilih Aplikasi", "Pilih salah satu aplikasi dari tabel terlebih dahulu.", parent=self.root)
            return
        
        item_data = self.mem_tree.item(selected_item[0])['values']
        app_name = item_data[0]
        pkg_name = item_data[1]
        
        self.status.set(f"Mengambil data RAM aktif untuk {app_name}...")
        self.root.update()

        try:
            mem_output = self.run_adb_local(["shell", "dumpsys", "meminfo", pkg_name], timeout=10)
            
            native_heap, dalvik_heap, graphics = "0 KB", "0 KB", "0 KB"
            total_pss, total_rss, swap_pss = "0 KB", "0 KB", "0 KB"
            has_active_process = False

            for line in mem_output.splitlines():
                line_str = line.strip()
                parts = line_str.split()
                
                if line_str.startswith("Native Heap") and len(parts) >= 2:
                    for p in parts[1:]:
                        clean_p = ''.join(filter(str.isdigit, p))
                        if clean_p:
                            native_heap = f"{clean_p} KB"
                            if int(clean_p) > 0:
                                has_active_process = True
                            break
                elif line_str.startswith("Dalvik Heap") and len(parts) >= 2:
                    for p in parts[1:]:
                        clean_p = ''.join(filter(str.isdigit, p))
                        if clean_p:
                            dalvik_heap = f"{clean_p} KB"
                            if int(clean_p) > 0:
                                has_active_process = True
                            break
                elif line_str.startswith("Graphics:") and len(parts) >= 2:
                    for p in parts[1:]:
                        clean_p = ''.join(filter(str.isdigit, p))
                        if clean_p:
                            graphics = f"{clean_p} KB"
                            break
                elif line_str.startswith("TOTAL PSS:") and len(parts) >= 3:
                    clean_p = ''.join(filter(str.isdigit, parts[2]))
                    if clean_p:
                        total_pss = f"{clean_p} KB"
                        if int(clean_p) > 0:
                            has_active_process = True
                elif line_str.startswith("TOTAL RSS:") and len(parts) >= 3:
                    clean_p = ''.join(filter(str.isdigit, parts[2]))
                    if clean_p:
                        total_rss = f"{clean_p} KB"
                elif "TOTAL SWAP PSS:" in line_str or "SWAP PSS:" in line_str:
                    for p in parts:
                        clean_p = ''.join(filter(str.isdigit, p))
                        if clean_p and int(clean_p) > 0:
                            swap_pss = f"{clean_p} KB"
                            break

            detail_text = f"===========================================================\n"
            detail_text += f" ANALISIS RAM AKTIF: {app_name}\n"
            detail_text += f" Package: {pkg_name}\n"
            detail_text += f"===========================================================\n\n"
            
            if not has_active_process:
                detail_text += f"⚠️ STATUS: Aplikasi sedang tidak digunakan / tidak aktif di RAM.\n\n"
            else:
                detail_text += f"🧠 RINCIAN PENGGUNAAN RAM:\n\n"
                detail_text += f"+-------------------+-------------------+--------------------------------------------------+\n"
                detail_text += f"| Komponen Memori   | Besar Angka       | Penjelasan (Arti & Fungsinya)                    |\n"
                detail_text += f"+-------------------+-------------------+--------------------------------------------------+\n"
                detail_text += f"| Native Heap       | {native_heap:<17} | Memori untuk sistem inti & bahasa C/C++          |\n"
                detail_text += f"| Dalvik Heap       | {dalvik_heap:<17} | Memori bahasa pemrograman aplikasi (Java/Kotlin) |\n"
                detail_text += f"| Graphics          | {graphics:<17} | Memori khusus untuk memproses tampilan visual    |\n"
                detail_text += f"| TOTAL PSS         | {total_pss:<17} | Total memori RAM fisik nyata yang sedang dipakai |\n"
                detail_text += f"| TOTAL RSS         | {total_rss:<17} | Total keseluruhan memori termasuk memori bersama |\n"
                detail_text += f"| SWAP PSS          | {swap_pss:<17} | Data dipindah ke memori virtual agar RAM longgar |\n"
                detail_text += f"+-------------------+-------------------+--------------------------------------------------+\n\n"
                detail_text += f"💡 Tips: Semakin kecil nilai TOTAL PSS, semakin ringan aplikasi tersebut di RAM HP.\n"

            self.mem_detail_box.delete("1.0", tk.END)
            self.mem_detail_box.insert(tk.END, detail_text)
            self.status.set(f"Berhasil memuat analisis RAM aktif untuk {app_name}.")
        except Exception as exc:
            self.show_error("Gagal Memuat RAM Aktif", exc)

    def load_memory_packages_list(self):
        """Memuat daftar aplikasi pihak ketiga dengan label nama asli, diurutkan abjad."""
        try:
            self.status.set("Memuat daftar aplikasi dari HP...")
            self.root.update()

            output = self.run_adb_local(["shell", "pm", "list", "packages", "-3"], timeout=30)
            packages = [line.replace("package:", "").strip() for line in output.splitlines() if line.startswith("package:")]
            
            app_list = []
            for pkg in packages:
                app_name = "Tidak diketahui"
                try:
                    pkg_info = self.run_adb_local(["shell", "dumpsys", "package", pkg], timeout=4)
                    for line in pkg_info.splitlines():
                        if "applicationInfo" in line and "label=" in line:
                            parts = line.split("label=")
                            if len(parts) > 1:
                                app_name = parts[1].split()[0].strip("'\"")
                                break
                except Exception:
                    pass

                if app_name == "Tidak diketahui" or not app_name:
                    app_name = pkg.split('.')[-1].capitalize()

                app_list.append((app_name, pkg))

            app_list.sort(key=lambda x: x[0].lower())

            for item in self.mem_tree.get_children():
                self.mem_tree.delete(item)

            for app_name, pkg in app_list:
                self.mem_tree.insert("", "end", values=(app_name, pkg))

            self.status.set(f"Berhasil memuat {len(app_list)} aplikasi dari HP.")
        except Exception as exc:
            self.show_error("Gagal memuat aplikasi", exc)

    def load_screen_time_by_period(self, period):
        """Mengambil data screen time secara real-time menggunakan dumpsys usagestats."""
        try:
            device_id = self.device.get().strip()
            if not device_id:
                messagebox.showwarning("Perangkat Belum Dipilih", "Pilih perangkat HP terlebih dahulu.", parent=self.root)
                return

            self.status.set(f"Menganalisis penggunaan aplikasi real-time ({period})...")
            self.root.update()

            raw_output = self.run_adb_local(["shell", "dumpsys", "usagestats"], timeout=15)
            self.st_text.delete("1.0", tk.END)
            
            app_stats = {}
            current_pkg = None
            
            for line in raw_output.splitlines():
                line_str = line.strip()
                if "package=" in line_str:
                    try:
                        part = line_str.split("package=")[1]
                        current_pkg = part.split()[0].rstrip("}")
                    except Exception:
                        pass
                
                if "totalTimeInForeground=" in line_str and current_pkg:
                    try:
                        val_str = line_str.split("totalTimeInForeground=")[1].split()[0]
                        time_val = int(val_str)
                        if time_val > 0:
                            app_stats[current_pkg] = app_stats.get(current_pkg, 0) + time_val
                    except Exception:
                        pass

            total_ms = sum(app_stats.values())
            total_mins = total_ms // 60000
            total_hrs = total_mins // 60
            total_rem_mins = total_mins % 60
            total_str = f"{total_hrs} j, {total_rem_mins} mnt" if total_hrs > 0 else f"{total_mins} mnt"
            
            self.st_text.insert(tk.END, f"===========================================================\n")
            self.st_text.insert(tk.END, f"         DETAIL AKTIVITAS APLIKASI (REAL-TIME)             \n")
            self.st_text.insert(tk.END, f"===========================================================\n\n")
            self.st_text.insert(tk.END, f"               Waktu pemakaian perangkat                   \n")
            self.st_text.insert(tk.END, f"                      {total_str}                         \n")
            self.st_text.insert(tk.END, f"                       {period.capitalize()}               \n\n")

            if app_stats:
                sorted_apps = sorted(app_stats.items(), key=lambda x: x[1], reverse=True)[:15]
                for pkg, ms in sorted_apps:
                    minutes_val = ms // 60000
                    hours_val = minutes_val // 60
                    rem_mins = minutes_val % 60
                    dur_str = f"{hours_val} j, {rem_mins} mnt" if hours_val > 0 else f"{minutes_val} mnt"
                    
                    self.st_text.insert(tk.END, f" 📱 Package: {pkg}\n    ⌛ Waktu Aktif: {dur_str}\n\n")
            else:
                self.st_text.insert(tk.END, "⚠️ Tidak ada data foreground time yang terekam pada periode ini.\n")

            self.status.set(f"Berhasil memuat screen time real-time ({period}).")
        except Exception as exc:
            self.show_error(f"Gagal memuat screen time {period}", exc)

    def load_processes(self):
        """Memuat daftar proses real-time lengkap dengan data mentah top/ps serta menyertakan terjemahan Nama Aplikasi & Package di kolom tersendiri."""
        try:
            device_id = self.device.get().strip()
            if not device_id:
                messagebox.showwarning("Perangkat Belum Dipilih", "Pilih perangkat HP terlebih dahulu.", parent=self.root)
                return

            self.status.set("Mengambil daftar proses real-time dan mendeteksi nama aplikasi...")
            self.root.update()

            raw_processes = self.os_handler.get_process_table(device_id)
            for item in self.proc_tree.get_children():
                self.proc_tree.delete(item)

            for proc in raw_processes:
                # proc format dari os_features: (PID, USER, STATUS, NICE, CPU, COMMAND)
                pid, user, status, nice, cpu, command = proc
                
                # Deteksi Nama Package dan Nama Label Aplikasi dari command
                app_label = "Sistem / Layanan Android"
                pkg_name = "-"
                
                parts = command.split()
                for p in parts:
                    if "." in p and not p.startswith("/") and not p.startswith("["):
                        pkg_name = p
                        # Buat nama label aplikasi yang mudah dibaca dari bagian akhir package
                        app_label = f"📱 {pkg_name.split('.')[-1].capitalize()} ({pkg_name})"
                        break
                
                if pkg_name == "-":
                    if "kworker" in command:
                        app_label = "⚙️ Kernel Worker (Sistem)"
                    elif "surfaceflinger" in command:
                        app_label = "🖼️ SurfaceFlinger (Layar)"
                    elif "system_server" in command:
                        app_label = "🧠 System Server (Inti Android)"

                # Masukkan ke tabel dengan kolom tambahan Nama Aplikasi / Info Jelas
                self.proc_tree.insert("", "end", values=(pid, user, status, nice, cpu, app_label, command))

            self.status.set(f"Berhasil memuat {len(raw_processes)} proses aktif secara real-time.")
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
            self.dashboard_device_name.set("-")
            self.dashboard_model.set("-")
            self.dashboard_ram.set("-")
            self.dashboard_cpu.set("-")
            self.dashboard_os.set("-")
            self.dashboard_android.set("-")
            self.dashboard_security.set("-")
            self.dashboard_baseband.set("-")
            self.dashboard_kernel.set("-")
            self.dashboard_battery.set("-")
            self.dashboard_storage.set("-")
            return

        try:
            device_name = self.run_adb_local(["shell", "getprop", "ro.product.model"], timeout=6)
            model = self.run_adb_local(["shell", "getprop", "ro.product.device"], timeout=6)
            os_version = self.run_adb_local(["shell", "getprop", "ro.miui.ui.version.name"], timeout=6) or \
                         self.run_adb_local(["shell", "getprop", "ro.build.display.id"], timeout=6)
            android_ver = self.run_adb_local(["shell", "getprop", "ro.build.version.release"], timeout=6)
            security_patch = self.run_adb_local(["shell", "getprop", "ro.build.version.security_patch"], timeout=6)
            baseband = self.run_adb_local(["shell", "getprop", "gsm.version.baseband"], timeout=6)
            kernel = self.run_adb_local(["shell", "uname", "-r"], timeout=6)
            
            board_platform = self.run_adb_local(["shell", "getprop", "ro.board.platform"], timeout=6)
            cpu_abi = self.run_adb_local(["shell", "getprop", "ro.product.cpu.abi"], timeout=6)
            processor_name = f"{board_platform.upper()} ({cpu_abi})" if board_platform else (cpu_abi or "Tidak diketahui")

            mem_info = self.run_adb_local(["shell", "cat", "/proc/meminfo"], timeout=6)
            total_ram_kb = 0
            for line in mem_info.splitlines():
                if "MemTotal" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        total_ram_kb = int(parts[1])
                        break
            ram_gb = f"{total_ram_kb / (1024*1024):.1f} GB" if total_ram_kb > 0 else "Tidak diketahui"

            battery_output = self.run_adb_local(["shell", "dumpsys", "battery"], timeout=6)
            battery_level = next(
                (line.split(":", 1)[1].strip() for line in battery_output.splitlines() if line.strip().startswith("level:")),
                "?"
            )

            storage_output = self.run_adb_local(["shell", "df", "-h", "/data"], timeout=6)
            storage_lines = storage_output.splitlines()
            storage_str = "Tidak tersedia"
            if len(storage_lines) >= 2:
                columns = storage_lines[-1].split()
                if len(columns) >= 4:
                    storage_str = f"Terpakai {columns[2]} dari {columns[1]} ({columns[4]} terpakai)"

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

    def start_recording(self):
        if not self.device.get():
            messagebox.showwarning("Pilih perangkat", "Pilih HP yang terotorisasi terlebih dahulu.", parent=self.root)
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"record_{timestamp}.mp4"
        
        try:
            args = ["scrcpy", "-s", self.device.get(), "--record", filename]
            self.recording_process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.status.set(f"Rekaman layar dimulai! File disimpan sebagai {filename}")
            messagebox.showinfo("Rekam Layar", f"Perekaman layar aktif.\nFile disimpan sebagai:\n{filename}\n\nTutup jendela scrcpy untuk menghentikan rekaman.", parent=self.root)
        except FileNotFoundError:
            self.show_error("scrcpy tidak ditemukan", "Pasang scrcpy dengan: sudo apt install scrcpy")
        except Exception as exc:
            self.show_error("Gagal memulai rekaman layar", exc)

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
            self.run_adb_local(["shell", "service", "call", "power", "16"])
            self.status.set("Perintah penguncian total layar dikirim.")
        except Exception as exc:
            self.show_error("Gagal mengunci layar", exc)

    def wake_screen(self):
        try:
            self.run_adb_local(["shell", "input", "keyevent", "224"])
            self.status.set("Perintah bangunkan layar dikirim.")
        except Exception as exc:
            self.show_error("Gagal membangunkan layar", exc)

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
        self.session_locked = False
        self.timer_start = time.monotonic()
        self.timer_limit = minutes * 60
        self._tick_timer()
        self.status.set(f"Timer sesi dimulai: {minutes} menit. HP akan dikunci total saat habis.")

    def stop_timer(self):
        self.timer_running = False
        self.session_locked = False
        if self.timer_job is not None:
            try:
                self.root.after_cancel(self.timer_job)
            except tk.TclError:
                pass
            self.timer_job = None
        self.timer_label.configure(text="00:00")
        self.status.set("Timer dihentikan. Sesi dibuka kembali.")

    def unlock_session(self):
        """Membuka kunci HP dengan memasukkan PIN 12345678 secara otomatis."""
        self.session_locked = False
        try:
            self.wake_screen()
            time.sleep(0.6)
            self.run_adb_local(["shell", "input", "swipe", "500", "1500", "500", "500", "300"])
            time.sleep(0.6)
            self.run_adb_local(["shell", "input", "text", PIN_LOCK])
            self.run_adb_local(["shell", "input", "keyevent", "66"])
            self.status.set("HP berhasil dibuka menggunakan PIN (12345678).")
            messagebox.showinfo("Akses Diizinkan", "HP telah dibuka kunci menggunakan PIN 12345678 oleh laptop.", parent=self.root)
        except Exception as exc:
            self.show_error("Gagal membuka kunci", exc)

    def _tick_timer(self):
        if not self.timer_running or self.timer_start is None:
            return
        elapsed = int(time.monotonic() - self.timer_start)
        remaining = max(0, self.timer_limit - elapsed)
        self.timer_label.configure(text=f"{remaining // 60:02d}:{remaining % 60:02d}")
        
        if remaining <= 0:
            self.session_locked = True
            self.stop_timer()
            self.timer_label.configure(text="TERKUNCI 🔒")
            self.lock_screen()
            messagebox.showwarning("Batas Waktu Habis", "Batas waktu sesi habis!\nHP telah dikunci total. Masukkan PIN (12345678) lewat laptop untuk membuka kembali.", parent=self.root)
            self._enforce_lock_loop()
            return
            
        self.timer_job = self.root.after(1000, self._tick_timer)

    def _enforce_lock_loop(self):
        if self.session_locked and self.device.get().strip():
            try:
                self.run_adb_local(["shell", "input", "keyevent", "26"], timeout=3)
                self.status.set("🔒 TERKUNCI: Memerlukan otorisasi laptop (PIN 12345678).")
            except Exception:
                pass
            self.root.after(3000, self._enforce_lock_loop)

    def load_packages(self):
        """Memuat daftar aplikasi pihak ketiga beserta nama asli (Label) dan diurutkan secara alfabetis."""
        try:
            self.status.set("Mengambil daftar aplikasi dan mengurutkan secara alfabetis...")
            self.root.update()

            output = self.run_adb_local(["shell", "pm", "list", "packages", "-3"], timeout=30)
            packages = [line.replace("package:", "").strip() for line in output.splitlines() if line.startswith("package:")]
            
            app_list = []
            for pkg in packages:
                app_name = "Tidak diketahui"
                try:
                    pkg_info = self.run_adb_local(["shell", "dumpsys", "package", pkg], timeout=4)
                    for line in pkg_info.splitlines():
                        if "applicationInfo" in line and "label=" in line:
                            parts = line.split("label=")
                            if len(parts) > 1:
                                app_name = parts[1].split()[0].strip("'\"")
                                break
                except Exception:
                    pass

                if app_name == "Tidak diketahui" or not app_name:
                    app_name = pkg.split('.')[-1].capitalize()

                app_list.append((app_name, pkg))

            app_list.sort(key=lambda x: x[0].lower())

            for item in self.app_tree.get_children():
                self.app_tree.delete(item)

            for app_name, pkg in app_list:
                self.app_tree.insert("", "end", values=(app_name, pkg))

            self.status.set(f"Berhasil memuat {len(app_list)} aplikasi diurutkan secara alfabetis.")
        except Exception as exc:
            self.show_error("Gagal memuat aplikasi", exc)

    def force_stop_selected(self):
        selected_items = self.app_tree.selection()
        if not selected_items:
            messagebox.showinfo("Pilih aplikasi", "Pilih salah satu atau beberapa aplikasi dari tabel terlebih dahulu.", parent=self.root)
            return
        
        selected_pkgs = [self.app_tree.item(item)['values'][1] for item in selected_items]
        if not messagebox.askyesno("Konfirmasi force stop", "Hentikan paksa aplikasi berikut?\n\n" + "\n".join(selected_pkgs), parent=self.root):
            return
        try:
            for package in selected_pkgs:
                self.run_adb_local(["shell", "am", "force-stop", package], timeout=20)
            self.status.set(f"{len(selected_pkgs)} aplikasi berhasil dihentikan paksa.")
            messagebox.showinfo("Selesai", "Perintah force-stop berhasil dikirim ke perangkat.", parent=self.root)
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

    def _build_ui(self):
        self.root.configure(bg="#F3F6FC")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=32)

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
        ttk.Label(header, text="USB + ADB", wraplength=940, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 8))

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
        mirror_usage_tab = ttk.Frame(notebook, padding=12)
        apps_tab = ttk.Frame(notebook, padding=12)
        files_tab = ttk.Frame(notebook, padding=12)
        mem_tab = ttk.Frame(notebook, padding=12)
        process_tab = ttk.Frame(notebook, padding=12)

        notebook.add(dashboard_tab, text="Dashboard")
        notebook.add(mirror_usage_tab, text="Mirroring, Rekam & Screen Time")
        notebook.add(apps_tab, text="Aplikasi")

        # ==================== TAB MANAJEMEN MEMORI ====================
        notebook.add(mem_tab, text="Manajemen Memori")
        mem_top = ttk.Frame(mem_tab)
        mem_top.pack(fill="x", pady=6)
        ttk.Button(mem_top, text="Muat Daftar Aplikasi (Urut Abjad)", command=self.load_memory_packages_list).pack(side="left")
        ttk.Button(mem_top, text="🔍 Analisis RAM Aktif", command=self.load_memory_details_for_selected).pack(side="left", padx=8)

        mem_split = ttk.PanedWindow(mem_tab, orient="horizontal")
        mem_split.pack(fill="both", expand=True, pady=6)
        mem_left = ttk.Frame(mem_split)
        mem_right = ttk.Frame(mem_split)
        mem_split.add(mem_left, weight=1)
        mem_split.add(mem_right, weight=1)

        self.mem_tree = ttk.Treeview(mem_left, columns=("Nama Aplikasi", "Package"), show="headings", height=18)
        self.mem_tree.heading("Nama Aplikasi", text="Nama Aplikasi (Label Asli)")
        self.mem_tree.heading("Package", text="Nama Paket (Package Name)")
        self.mem_tree.column("Nama Aplikasi", width=200, anchor="w")
        self.mem_tree.column("Package", width=280, anchor="w")
        mem_scroll = ttk.Scrollbar(mem_left, orient="vertical", command=self.mem_tree.yview)
        self.mem_tree.configure(yscrollcommand=mem_scroll.set)
        self.mem_tree.pack(side="left", fill="both", expand=True)
        mem_scroll.pack(side="right", fill="y")

        self.mem_detail_box = tk.Text(mem_right, wrap="word", bg="#121212", fg="#00FF00", font=("DejaVu Sans Mono", 10))
        self.mem_detail_box.pack(fill="both", expand=True)
        # ==============================================================================================

        # Dashboard content
        ttk.Label(dashboard_tab, text="Ringkasan Perangkat", font=("TkDefaultFont", 16, "bold")).pack(anchor="w", pady=(0, 12))

        info_frame = ttk.LabelFrame(dashboard_tab, text="Informasi Lengkap HP (About Phone)", padding=12)
        info_frame.pack(fill="x", pady=4)

        for label, variable in [
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
        ]:
            line = ttk.Frame(info_frame)
            line.pack(fill="x", pady=3)
            ttk.Label(line, text=label, width=22).pack(side="left")
            ttk.Label(line, textvariable=variable, font=("TkDefaultFont", 10, "bold")).pack(side="left", fill="x", expand=True)

        dashboard_buttons = ttk.Frame(dashboard_tab)
        dashboard_buttons.pack(fill="x", pady=12)
        ttk.Button(dashboard_buttons, text="Perbarui informasi", command=self.refresh_dashboard).pack(side="left")
        ttk.Button(dashboard_buttons, text="Refresh perangkat", command=self.refresh_devices).pack(side="left", padx=8)

        # Tab Mirroring, Rekam & Screen Time
        ttk.Label(mirror_usage_tab, text="Kontrol Layar & Perekaman (Scrcpy)", font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(0, 4))
        
        control_row = ttk.Frame(mirror_usage_tab)
        control_row.pack(anchor="w", pady=4)
        ttk.Button(control_row, text="Mulai Mirroring", command=self.start_mirroring).pack(side="left", padx=(0, 6))
        ttk.Button(control_row, text="Mirroring + Layar Mati", command=self.start_mirroring_screen_off).pack(side="left", padx=6)
        ttk.Button(control_row, text="🔴 Rekam Layar", command=self.start_recording).pack(side="left", padx=6)
        ttk.Button(control_row, text="Kunci Layar HP", command=self.lock_screen).pack(side="left", padx=6)
        ttk.Button(control_row, text="Bangunkan Layar", command=self.wake_screen).pack(side="left", padx=6)

        timer_box = ttk.LabelFrame(mirror_usage_tab, text="Timer Batas Sesi & Penguncian PIN (12345678)", padding=8)
        timer_box.pack(fill="x", pady=8)
        time_row = ttk.Frame(timer_box)
        time_row.pack(anchor="w", pady=2)
        ttk.Label(time_row, text="Batas sesi (menit):").pack(side="left")
        ttk.Entry(time_row, textvariable=self.minutes, width=8).pack(side="left", padx=8)
        ttk.Button(time_row, text="Mulai Timer", command=self.start_timer).pack(side="left", padx=4)
        ttk.Button(time_row, text="Hentikan Timer", command=self.stop_timer).pack(side="left", padx=4)
        ttk.Button(time_row, text="🔓 Buka Kunci (PIN: 12345678)", command=self.unlock_session).pack(side="left", padx=12)
        
        self.timer_label = ttk.Label(timer_box, text="00:00", font=("TkDefaultFont", 14, "bold"))
        self.timer_label.pack(anchor="w", pady=4)

        st_box = ttk.LabelFrame(mirror_usage_tab, text="Detail Aktivitas Aplikasi Real-Time (Digital Wellbeing Style)", padding=8)
        st_box.pack(fill="both", expand=True, pady=6)
        
        st_top = ttk.Frame(st_box)
        st_top.pack(fill="x", pady=4)
        ttk.Label(st_top, text="Pilih Periode:").pack(side="left", padx=(0, 6))
        ttk.Button(st_top, text="📅 Hari Ini (Daily)", command=lambda: self.load_screen_time_by_period("daily")).pack(side="left", padx=4)
        ttk.Button(st_top, text="📊 Minggu Ini (Weekly)", command=lambda: self.load_screen_time_by_period("weekly")).pack(side="left", padx=4)
        ttk.Button(st_top, text="📈 1 Bulan (Monthly)", command=lambda: self.load_screen_time_by_period("monthly")).pack(side="left", padx=4)
        ttk.Button(st_top, text="📉 1 Tahun (Yearly)", command=lambda: self.load_screen_time_by_period("yearly")).pack(side="left", padx=4)
        
        st_frame = ttk.Frame(st_box)
        st_frame.pack(fill="both", expand=True, pady=4)
        st_scroll = ttk.Scrollbar(st_frame, orient="vertical")
        st_scroll.pack(side="right", fill="y")
        self.st_text = tk.Text(st_frame, wrap="word", bg="#121212", fg="#FFFFFF", font=("DejaVu Sans Mono", 10), yscrollcommand=st_scroll.set)
        self.st_text.pack(side="left", fill="both", expand=True)
        st_scroll.config(command=self.st_text.yview)

        # ==================== TAB MANAJEMEN PROSES & CPU ====================
        notebook.add(process_tab, text="Manajemen Proses & CPU")
        
        proc_top = ttk.Frame(process_tab)
        proc_top.pack(fill="x", pady=6)
        ttk.Button(proc_top, text="🔄 Muat Proses (Real-Time)", command=self.load_processes).pack(side="left")
        ttk.Button(proc_top, text="⚙️ Ubah Prioritas (Renice)", command=self.change_process_priority).pack(side="left", padx=8)

        tree_frame = ttk.Frame(process_tab)
        tree_frame.pack(fill="both", expand=True, pady=4)

        # Menambahkan kolom "Nama Aplikasi & Keterangan Jelas" di sebelah data mentah aslinya
        self.proc_tree = ttk.Treeview(
            tree_frame, 
            columns=("PID", "USER", "STATUS", "NICE", "CPU (%)", "Nama Aplikasi / Info Jelas", "Command / Raw Data Asli"),
            show="headings",
            height=25
        )
        self.proc_tree.heading("PID", text="PID")
        self.proc_tree.heading("USER", text="User")
        self.proc_tree.heading("STATUS", text="Status")
        self.proc_tree.heading("NICE", text="Nice (NI)")
        self.proc_tree.heading("CPU (%)", text="CPU (%)")
        self.proc_tree.heading("Nama Aplikasi / Info Jelas", text="🏷️ Nama Aplikasi & Package Jelas")
        self.proc_tree.heading("Command / Raw Data Asli", text="Command / Raw Data Asli")

        self.proc_tree.column("PID", width=60, anchor="center")
        self.proc_tree.column("USER", width=80, anchor="center")
        self.proc_tree.column("STATUS", width=60, anchor="center")
        self.proc_tree.column("NICE", width=60, anchor="center")
        self.proc_tree.column("CPU (%)", width=60, anchor="center")
        self.proc_tree.column("Nama Aplikasi / Info Jelas", width=260, anchor="w")
        self.proc_tree.column("Command / Raw Data Asli", width=340, anchor="w")

        proc_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=proc_scroll.set)
        self.proc_tree.pack(side="left", fill="both", expand=True)
        proc_scroll.pack(side="right", fill="y")
        # ==============================================================================================

        # Tab Transfer File
        notebook.add(files_tab, text="Transfer File")
        ttk.Label(files_tab, text="Kirim file dari laptop ke folder Download HP.").pack(anchor="w")
        ttk.Button(files_tab, text="Pilih file lalu kirim ke HP", command=self.push_file).pack(anchor="w", pady=8)
        ttk.Label(files_tab, text="Pilih APK untuk memasangnya pada HP yang terhubung.").pack(anchor="w", pady=(16, 0))
        ttk.Button(files_tab, text="Pilih APK lalu instal", command=self.install_apk).pack(anchor="w", pady=8)

        # Tab Aplikasi
        notebook.add(apps_tab, text="Aplikasi")
        app_top = ttk.Frame(apps_tab)
        app_top.pack(fill="x", pady=6)
        ttk.Button(app_top, text="Muat Daftar Aplikasi (Urut Abjad)", command=self.load_packages).pack(side="left")
        ttk.Button(app_top, text="Force Stop Terpilih", command=self.force_stop_selected).pack(side="left", padx=8)

        app_frame = ttk.Frame(apps_tab)
        app_frame.pack(fill="both", expand=True, pady=4)

        self.app_tree = ttk.Treeview(
            app_frame,
            columns=("Nama Aplikasi", "Nama Paket (Package)"),
            show="headings",
            height=20,
            selectmode="extended"
        )
        self.app_tree.heading("Nama Aplikasi", text="Nama Aplikasi (Urut Abjad)")
        self.app_tree.heading("Nama Paket (Package)", text="Nama Paket (Package Name)")
        self.app_tree.column("Nama Aplikasi", width=250, anchor="w")
        self.app_tree.column("Nama Paket (Package)", width=500, anchor="w")

        app_scroll = ttk.Scrollbar(app_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=app_scroll.set)
        self.app_tree.pack(side="left", fill="both", expand=True)
        app_scroll.pack(side="right", fill="y")

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(0, 8))
        ttk.Label(footer, text="Status: ADB aktif.").pack(anchor="w")

    def on_close(self):
        self.stop_timer()
        self.root.destroy()


def main():
    root = tk.Tk()
    RemoteControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
