#!/usr/bin/env python3
"""Android Remote Control Center: GUI for a user-authorized Android device."""

import os
import subprocess
import time
import threading 
import tkinter as tk
from queue import Queue
from datetime import datetime
from tkinter import ttk, filedialog, messagebox, simpledialog

from adb_helper import run_adb_cmd, get_adb_devices
from os_features import OSFeaturesHandler

APP_TITLE = "Android Remote Control Center"
PIN_LOCK = "12345678"


class RemoteControlApp:
    def __init__(self, root):
        # Inisialisasi jendela utama aplikasi Tkinter
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1220x880")
        self.root.minsize(980, 680)

        # Inisialisasi handler OS, variabel string reaktif, dan status awal
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
        self.is_fetching_proc = False

        # Variabel untuk penghitungan kecepatan jaringan
        self.prev_rx_bytes = 0
        self.prev_tx_bytes = 0
        self.prev_net_time = time.monotonic()

        # Inisialisasi StringVar untuk monitor jaringan dan dashboard perangkat
        self.net_main_status = tk.StringVar(value="Memeriksa...")
        self.net_wifi_name = tk.StringVar(value="-")
        self.net_speed_dl = tk.StringVar(value="0 B/s")
        self.net_speed_ul = tk.StringVar(value="0 B/s")
        self.net_ping = tk.StringVar(value="Mengecek...")
        self.net_total_quota = tk.StringVar(value="0 MB")
        self.net_wifi_quota = tk.StringVar(value="0 MB")
        self.net_mobile_quota = tk.StringVar(value="0 MB")
        self.net_hotspot_status = tk.StringVar(value="Mati")
        self.net_hotspot_source = tk.StringVar(value="Tidak ada")

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
        
        self.dashboard_battery_level = tk.StringVar(value="-")
        self.dashboard_battery_temp = tk.StringVar(value="-")
        self.dashboard_cpu_temp = tk.StringVar(value="-")
        self.dashboard_battery_power = tk.StringVar(value="-")
        self.dashboard_battery_health = tk.StringVar(value="-")
        self.dashboard_battery_cycles = tk.StringVar(value="-")
        self.dashboard_battery_summary = tk.StringVar(value="-")
        
        self.dashboard_performance = tk.StringVar(value="-")
        self.dashboard_network_status = tk.StringVar(value="-")
        self.dashboard_storage = tk.StringVar(value="-")

        # Membangun UI, memuat perangkat terhubung, dan menjalankan loop latar belakang
        self._build_ui()
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_dashboard_loop()
        self.auto_refresh_cpu_loop()

    def run_adb(self, device_id, *, args, timeout=15):
        # Wrapper fungsi untuk menjalankan perintah ADB ke perangkat target
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def run_adb_local(self, args, timeout=15):
        # Wrapper perintah ADB menggunakan ID perangkat yang sedang aktif dipilih di UI
        device_id = self.device.get().strip()
        return run_adb_cmd(device_id, args=args, timeout=timeout)

    def show_error(self, title, error):
        # Menampilkan pesan error pada status bar dan pop-up dialog
        self.status.set(str(error))
        messagebox.showerror(title, str(error), parent=self.root)
        
    def extract_app_name(self, pkg_name):
        # Kamus pemetaan nama package sistem/aplikasi populer agar mudah dibaca manusia
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
            "com.android.chrome": "Google Chrome"
        }
        
        lower_pkg = pkg_name.lower()
        if lower_pkg in known_apps:
            return known_apps[lower_pkg]
            
        for key in known_apps:
            if key in lower_pkg:
                return known_apps[key]
            
        ignore_words = {'id', 'android', 'app', 'apps', 'mobile', 'lite', 'www', 'com', 'net', 'org', 'miui'}
        parts = pkg_name.split('.')
        valid_parts = [p for p in parts if p.lower() not in ignore_words]
        
        if valid_parts:
            return valid_parts[-1].capitalize()
            
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return pkg_name.capitalize()

    def on_mem_tree_click(self, event):
        # Event handler saat baris tabel manajemen memori diklik
        item = self.mem_tree.identify_row(event.y)
        if item:
            self.mem_tree.selection_set(item)
            self.load_memory_details_for_selected()

    def on_proc_tree_click(self, event):
        # Event handler saat baris tabel proses CPU diklik
        item = self.proc_tree.identify_row(event.y)
        if item:
            self.proc_tree.selection_set(item)
            self.change_process_priority()

    def on_app_tree_click(self, event):
        # Event handler saat baris tabel aplikasi diklik
        item = self.app_tree.identify_row(event.y)
        if item:
            self.app_tree.selection_set(item)
            self.force_stop_selected()

    def on_tab_changed(self, event):
        # Memuat data secara dinamis saat pengguna berpindah antar tab menu
        try:
            selected_tab = self.notebook.tab(self.notebook.select(), "text")
            if selected_tab == "Manajemen Memori":
                if not self.mem_tree.get_children(): 
                    self.load_memory_packages_list()
            elif selected_tab == "Aplikasi":
                if not self.app_tree.get_children():
                    self.load_packages()
            elif selected_tab == "Manajemen Proses & CPU":
                self.load_processes()
            elif selected_tab == "Monitor Jaringan":
                self.load_network_traffic()
        except Exception:
            pass

    def auto_refresh_cpu_loop(self):
        """Loop auto-refresh yang dijalankan via background thread agar GUI tidak lag."""
        try:
            if hasattr(self, 'notebook'):
                selected_tab = self.notebook.tab(self.notebook.select(), "text")
                if selected_tab == "Manajemen Proses & CPU":
                    if getattr(self, 'auto_refresh_proc_var', None) and self.auto_refresh_proc_var.get():
                        if not self.is_fetching_proc:
                            self.is_fetching_proc = True
                            threading.Thread(target=self._fetch_processes_worker, daemon=True).start()
                elif selected_tab == "Monitor Jaringan":
                    self.load_network_traffic()
        except Exception:
            pass
        self.root.after(2500, self.auto_refresh_cpu_loop)

    def _fetch_processes_worker(self):
        """Worker thread khusus mengambil data proses via ADB dengan pengunci aman."""
        device_id = self.device.get().strip()
        if device_id:
            try:
                raw_processes = self.os_handler.get_process_table(device_id)
                self.root.after(0, self._smart_update_proc_tree, raw_processes)
            except Exception as exc:
                err_msg = str(exc)
                self.root.after(0, lambda msg=err_msg: self.status.set(f"Gagal memuat proses: {msg}"))
            finally:
                self.is_fetching_proc = False
        else:
            self.is_fetching_proc = False
        
    def _smart_update_proc_tree(self, raw_processes):
        """Memperbarui isi TreeView dengan menempatkan Aplikasi di paling atas."""
        if not raw_processes:
            self.status.set("⚠️ ADB mengembalikan data proses kosong.")
            return

        processed_list = []
        for proc in raw_processes:
            if len(proc) >= 12:
                pid, user, status, pr, ni, virt, res, shr, cpu_pct, mem_pct, time_plus, command = proc
            else:
                pid, user, status, ni, cpu_pct, command = proc[:6]
                pr, virt, res, shr, mem_pct, time_plus = "-", "-", "-", "-", "-", "-"
            
            app_label = "Sistem / Layanan Android"
            pkg_name = "-"
            
            clean_token = command.strip("()[]{}")
            if "." in clean_token and not clean_token.startswith("/") and not clean_token.startswith("0:"):
                parts_dot = clean_token.split(".")
                if len(parts_dot) >= 2 and not all(p.isdigit() for p in parts_dot):
                    pkg_name = clean_token
                    app_label = self.extract_app_name(pkg_name)

            try:
                cpu_float = float(str(cpu_pct).replace("%", "").strip())
            except ValueError:
                cpu_float = 0.0

            is_app = (pkg_name != "-")
            priority = 0 if is_app else 1

            vals = (pid, user, status, pr, ni, virt, res, shr, cpu_pct, mem_pct, time_plus, app_label, command)
            processed_list.append({
                "pid_str": str(pid),
                "vals": vals,
                "priority": priority,
                "cpu_float": cpu_float
            })

        processed_list.sort(key=lambda x: (x["priority"], -x["cpu_float"]))

        existing_items = {}
        for item in self.proc_tree.get_children():
            item_vals = self.proc_tree.item(item, "values")
            if item_vals:
                existing_items[str(item_vals[0])] = item

        new_pids = set()
        for idx, item_data in enumerate(processed_list):
            pid_str = item_data["pid_str"]
            vals = item_data["vals"]
            new_pids.add(pid_str)

            if pid_str in existing_items:
                item_id = existing_items[pid_str]
                if self.proc_tree.item(item_id, "values") != vals:
                    self.proc_tree.item(item_id, values=vals)
                self.proc_tree.move(item_id, "", idx)
            else:
                self.proc_tree.insert("", idx, values=vals)

        for pid_str, item_id in existing_items.items():
            if pid_str not in new_pids:
                self.proc_tree.delete(item_id)

        self.status.set(f"Berhasil memuat {len(processed_list)} proses (Aplikasi diprioritaskan di atas).")
        

    def _get_active_network_state(self):
        """Logika deteksi Wi-Fi Client vs Paket Data Seluler (Mengabaikan Nama Hotspot HP)."""
        wifi_active = False
        data_active = False
        wifi_ssid = "-"
        
        try:
            wifi_dump = self.run_adb_local(["shell", "dumpsys", "wifi"], timeout=4)
            route_out = self.run_adb_local(["shell", "ip", "route"], timeout=3)
            
            has_wlan_route = "wlan0" in route_out or "wlan1" in route_out
            
            for line in wifi_dump.splitlines():
                if "mWifiInfo" in line and "SSID:" in line:
                    parts = line.split("SSID:")
                    if len(parts) > 1:
                        candidate = parts[1].split(",")[0].split("BSSID:")[0].strip('"\' ')
                        if candidate and candidate not in ["<unknown ssid>", "-", "null"]:
                            wifi_ssid = candidate
                            break

            if has_wlan_route and wifi_ssid != "-":
                wifi_active = True
            else:
                wifi_ssid = "-"
                data_active = True

        except Exception:
            data_active = True

        return wifi_active, wifi_ssid, data_active

    def load_network_traffic(self):
        # Memuat statistik traffic jaringan, kecepatan transfer, kuota, dan ping
        try:
            device_id = self.device.get().strip()
            if not device_id:
                return

            raw_net = self.run_adb_local(["shell", "cat", "/proc/net/dev"], timeout=4)
            current_time = time.monotonic()
            time_delta = current_time - self.prev_net_time
            if time_delta <= 0:
                time_delta = 1.0

            total_rx = 0
            total_tx = 0
            wifi_rx, wifi_tx = 0, 0
            mobile_rx, mobile_tx = 0, 0

            for line in raw_net.splitlines():
                if ":" in line:
                    iface, data = line.split(":", 1)
                    iface = iface.strip()
                    if iface in ["lo", "dummy0"]: 
                        continue
                    parts = data.split()
                    if len(parts) >= 9:
                        rx = int(parts[0])
                        tx = int(parts[8])
                        total_rx += rx
                        total_tx += tx
                        if "wlan" in iface or "swlan" in iface:
                            wifi_rx += rx
                            wifi_tx += tx
                        elif "rmnet" in iface or "ccmni" in iface or "wwan" in iface:
                            mobile_rx += rx
                            mobile_tx += tx

            rx_speed = (total_rx - self.prev_rx_bytes) / time_delta if self.prev_rx_bytes > 0 else 0
            tx_speed = (total_tx - self.prev_tx_bytes) / time_delta if self.prev_tx_bytes > 0 else 0

            self.prev_rx_bytes = total_rx
            self.prev_tx_bytes = total_tx
            self.prev_net_time = current_time

            def format_speed(b_sec):
                if b_sec > 1024 * 1024:
                    return f"{b_sec / (1024 * 1024):.2f} MB/s"
                elif b_sec > 1024:
                    return f"{b_sec / 1024:.2f} KB/s"
                else:
                    return f"{int(b_sec)} B/s"

            wifi_on, wifi_ssid_val, data_on = self._get_active_network_state()

            if wifi_on:
                self.net_main_status.set("Wi-Fi (Aktif & Diprioritaskan)")
                self.net_wifi_name.set(wifi_ssid_val)
            elif data_on:
                self.net_main_status.set("Paket Data Seluler")
                self.net_wifi_name.set("Mati / Tidak Terhubung")
            else:
                self.net_main_status.set("Tidak Ada Koneksi Aktif")
                self.net_wifi_name.set("-")

            self.net_speed_dl.set(format_speed(rx_speed))
            self.net_speed_ul.set(format_speed(tx_speed))
            self.net_total_quota.set(f"{(total_rx + total_tx) / (1024*1024):.2f} MB")
            self.net_wifi_quota.set(f"{wifi_rx / (1024*1024):.2f} MB")
            self.net_mobile_quota.set(f"{mobile_rx / (1024*1024):.2f} MB")

            ping_latency = "Mengecek..."
            try:
                ping_out = self.run_adb_local(["shell", "ping", "-c", "1", "8.8.8.8"], timeout=3)
                for pline in ping_out.splitlines():
                    if "time=" in pline:
                        ping_latency = f"{pline.split('time=')[1].split()[0]} ms"
                        break
            except Exception:
                ping_latency = "RTO / Timeout"
            self.net_ping.set(ping_latency)

            clients_list = []
            is_hotspot_on = False
            
            try:
                route_out = self.run_adb_local(["shell", "ip", "route"], timeout=3)
                
                for line in route_out.splitlines():
                    if any(iface in line for iface in ["ap0", "wlan1", "softap", "swlan0"]) and "dev" in line:
                        is_hotspot_on = True
                        break

                if not is_hotspot_on:
                    tether_out = self.run_adb_local(["shell", "dumpsys", "connectivity"], timeout=3)
                    if "tetheringClasses" in tether_out or "tethered" in tether_out.lower():
                        for tline in tether_out.splitlines():
                            if "tethered:" in tline.lower() and any(k in tline for k in ["ap0", "wlan1", "swlan0"]):
                                is_hotspot_on = True
                                break

                if is_hotspot_on:
                    self.net_hotspot_status.set("🟢 Nyala (Aktif)")
                    if wifi_on:
                        self.net_hotspot_source.set(f"Wi-Fi ({wifi_ssid_val}) — Meneruskan koneksi Wi-Fi")
                    else:
                        self.net_hotspot_source.set("Paket Data Seluler — Meneruskan kuota seluler")

                    arp_out = self.run_adb_local(["shell", "cat", "/proc/net/arp"], timeout=3)
                    for aline in arp_out.splitlines():
                        parts = aline.split()
                        if len(parts) >= 4 and parts[0] != "IP":
                            ip_addr = parts[0]
                            mac_addr = parts[3]
                            if mac_addr != "00:00:00:00:00:00" and not ip_addr.startswith("10."):
                                clients_list.append((ip_addr, mac_addr))
                else:
                    self.net_hotspot_status.set("🔴 Mati (Tidak Aktif)")
                    self.net_hotspot_source.set("Tidak Ada (Hotspot Sedang Dimatikan)")

            except Exception:
                self.net_hotspot_status.set("🔴 Mati (Tidak Aktif)")
                self.net_hotspot_source.set("Tidak Ada (Hotspot Sedang Dimatikan)")
            for item in self.client_tree.get_children():
                self.client_tree.delete(item)

            if clients_list:
                for ip, mac in clients_list:
                    self.client_tree.insert("", "end", values=(ip, mac, "Terhubung Aktif ke Hotspot"))
            else:
                self.client_tree.insert("", "end", values=("-", "-", "Tidak ada perangkat klien terhubung"))

            self.status.set("Traffic & status jaringan diperbarui secara akurat.")
        except Exception as exc:
            pass

    def toggle_wifi_connection(self):
        # Mengaktifkan atau menonaktifkan Wi-Fi di perangkat
        try:
            state = simpledialog.askstring("Kontrol Wi-Fi", "Ketik 'on' untuk menyalakan atau 'off' untuk mematikan Wi-Fi:", parent=self.root)
            if state:
                val = state.strip().lower()
                if val == 'on':
                    self.run_adb_local(["shell", "svc", "wifi", "enable"], timeout=5)
                    messagebox.showinfo("Berhasil", "Perintah menyalakan Wi-Fi dikirim.", parent=self.root)
                elif val == 'off':
                    self.run_adb_local(["shell", "svc", "wifi", "disable"], timeout=5)
                    messagebox.showinfo("Berhasil", "Perintah mematikan Wi-Fi dikirim.", parent=self.root)
                self.load_network_traffic()
                self.refresh_dashboard()
        except Exception as exc:
            self.show_error("Gagal", exc)

    def toggle_data_connection(self):
        # Mengaktifkan atau menonaktifkan paket data seluler
        try:
            state = simpledialog.askstring("Kontrol Paket Data", "Ketik 'on' untuk menyalakan atau 'off' untuk mematikan Paket Data:", parent=self.root)
            if state:
                val = state.strip().lower()
                if val == 'on':
                    self.run_adb_local(["shell", "svc", "data", "enable"], timeout=5)
                    messagebox.showinfo("Berhasil", "Perintah menyalakan Paket Data dikirim.", parent=self.root)
                elif val == 'off':
                    self.run_adb_local(["shell", "svc", "data", "disable"], timeout=5)
                    messagebox.showinfo("Berhasil", "Perintah mematikan Paket Data dikirim.", parent=self.root)
                self.load_network_traffic()
                self.refresh_dashboard()
        except Exception as exc:
            self.show_error("Gagal", exc)

    def toggle_airplane_mode(self):
        # Mengaktifkan atau menonaktifkan mode pesawat
        try:
            state = simpledialog.askstring("Mode Pesawat", "Ketik 'on' untuk mengaktifkan atau 'off' untuk menonaktifkan Mode Pesawat:", parent=self.root)
            if state:
                val = state.strip().lower()
                enable_val = "1" if val == 'on' else "0"
                self.run_adb_local(["shell", "settings", "put", "global", "airplane_mode_on", enable_val], timeout=5)
                self.run_adb_local(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", enable_val], timeout=5)
                messagebox.showinfo("Berhasil", f"Mode Pesawat diubah menjadi: {val.upper()}.", parent=self.root)
                self.load_network_traffic()
                self.refresh_dashboard()
        except Exception as exc:
            self.show_error("Gagal mengubah Mode Pesawat", exc)

    def toggle_hotspot_connection(self):
        """Menyalakan/mematikan Hotspot via ADB atau membuka Halaman Tethering HP secara otomatis."""
        try:
            state = simpledialog.askstring(
                "Kontrol Hotspot", 
                "Ketik 'on' untuk menyalakan, 'off' untuk mematikan, atau 'open' untuk membuka menu di HP:", 
                parent=self.root
            )
            if not state:
                return

            val = state.strip().lower()
            success = False

            if val == 'on':
                try:
                    out = self.run_adb_local(["shell", "cmd", "tethering", "startTethering", "0"], timeout=4)
                    if "Error" not in out and "Exception" not in out and "Permission" not in out:
                        success = True
                except Exception:
                    pass

                if not success:
                    try:
                        self.run_adb_local(["shell", "am", "start", "-a", "android.settings.TetherSettings"], timeout=4)
                        messagebox.showinfo(
                            "Fitur Keamanan OS HP", 
                            "Sistem ROM HP Anda memblokir aktifasi Hotspot tersembunyi via ADB.\n\n"
                            "Halaman 'Pengaturan Hotspot' telah otomatis dibuka di layar HP Anda. Silakan geser tombol sakelar Hotspot.", 
                            parent=self.root
                        )
                    except Exception as exc:
                        self.show_error("Gagal membuka menu Hotspot", exc)
                else:
                    messagebox.showinfo("Berhasil", "Perintah menyalakan Hotspot dikirim.", parent=self.root)

            elif val == 'off':
                try:
                    out = self.run_adb_local(["shell", "cmd", "tethering", "stopTethering", "0"], timeout=4)
                    if "Error" not in out and "Exception" not in out:
                        success = True
                except Exception:
                    pass

                if not success:
                    try:
                        self.run_adb_local(["shell", "am", "start", "-a", "android.settings.TetherSettings"], timeout=4)
                    except Exception:
                        pass
                    messagebox.showinfo("Buka Pengaturan", "Silakan matikan sakelar Hotspot pada layar HP yang telah dibuka.", parent=self.root)
                else:
                    messagebox.showinfo("Berhasil", "Hotspot dimatikan.", parent=self.root)

            elif val == 'open':
                self.run_adb_local(["shell", "am", "start", "-a", "android.settings.TetherSettings"], timeout=4)
                self.status.set("Halaman Pengaturan Hotspot dibuka di HP.")

            self.load_network_traffic()
            self.refresh_dashboard()

        except Exception as exc:
            self.show_error("Gagal mengatur hotspot", exc)
            

    def load_memory_packages_list(self):
        """Memuat daftar aplikasi ke tabel Manajemen Memori secara asynchronous (background thread)."""
        device_id = self.device.get().strip()
        if not device_id:
            messagebox.showwarning("Perangkat Belum Dipilih", "Pilih HP yang terhubung terlebih dahulu.", parent=self.root)
            return

        self.status.set("Memuat daftar aplikasi untuk Manajemen Memori...")
        self.root.update()

        threading.Thread(target=self._fetch_memory_packages_worker, args=(device_id,), daemon=True).start()

    def _fetch_memory_packages_worker(self, device_id):
        """Worker thread untuk mengambil daftar package pihak ketiga."""
        try:
            output = self.run_adb(device_id, args=["shell", "pm", "list", "packages", "-3"], timeout=20)
            packages = []
            for line in output.splitlines():
                line_clean = line.strip().replace("\r", "")
                if line_clean.startswith("package:"):
                    pkg = line_clean.replace("package:", "").strip()
                    if pkg:
                        packages.append(pkg)
        
            app_list = []
            for pkg in packages:
                app_name = self.extract_app_name(pkg)
                app_list.append((app_name, pkg))

            app_list.sort(key=lambda x: x[0].lower())

            self.root.after(0, self._populate_memory_tree_ui, app_list)
        except Exception as exc:
            err_msg = str(exc)
            self.root.after(0, self.show_error, "Gagal memuat daftar aplikasi", err_msg)

    def _populate_memory_tree_ui(self, app_list):
        """Memperbarui TreeView pada main thread setelah data siap."""
        for item in self.mem_tree.get_children():
            self.mem_tree.delete(item)

        for app_name, pkg in app_list:
            self.mem_tree.insert("", "end", values=(app_name, pkg))

        self.status.set(f"Berhasil memuat {len(app_list)} aplikasi pada Manajemen Memori.")

    def load_memory_details_for_selected(self):
        """Mengambil rincian RAM (PSS/RSS/Swap) dan Data Eksternal untuk aplikasi yang dipilih."""
        selected_item = self.mem_tree.selection()
        if not selected_item:
            messagebox.showinfo("Pilih Aplikasi", "Pilih salah satu aplikasi dari tabel terlebih dahulu.", parent=self.root)
            return
        
        item_data = self.mem_tree.item(selected_item[0])['values']
        app_name = item_data[0]
        pkg_name = item_data[1]
        
        self.status.set(f"Mengambil data RAM & Storage untuk {app_name}...")
        
        threading.Thread(target=self._fetch_memory_details_worker, args=(app_name, pkg_name), daemon=True).start()

    def _fetch_memory_details_worker(self, app_name, pkg_name):
        """Worker thread fleksibel & andal untuk dumpsys meminfo dan storage eksternal."""
        try:
            mem_output = self.run_adb_local(["shell", "dumpsys", "meminfo", pkg_name], timeout=10)
            
            native_heap, dalvik_heap, graphics = "0 KB", "0 KB", "0 KB"
            total_pss, total_rss, swap_pss = "0 KB", "0 KB", "0 KB"
            has_active_process = False

            if "No process found" in mem_output or not mem_output.strip():
                has_active_process = False
            else:
                for line in mem_output.splitlines():
                    line_str = line.strip()
                    
                    if "Native Heap" in line_str:
                        for token in line_str.split():
                            clean_val = ''.join(filter(str.isdigit, token))
                            if clean_val and int(clean_val) > 0:
                                native_heap = f"{int(clean_val):,} KB".replace(",", ".")
                                has_active_process = True
                                break

                    elif "Dalvik Heap" in line_str:
                        for token in line_str.split():
                            clean_val = ''.join(filter(str.isdigit, token))
                            if clean_val and int(clean_val) > 0:
                                dalvik_heap = f"{int(clean_val):,} KB".replace(",", ".")
                                has_active_process = True
                                break

                    elif "Graphics:" in line_str or "Graphics" in line_str:
                        for token in line_str.split():
                            clean_val = ''.join(filter(str.isdigit, token))
                            if clean_val and int(clean_val) > 0:
                                graphics = f"{int(clean_val):,} KB".replace(",", ".")
                                break

                    if "TOTAL PSS:" in line_str or "TOTAL PSS" in line_str or line_str.startswith("TOTAL:"):
                        parts = line_str.split()
                        for idx, token in enumerate(parts):
                            clean_token = token.rstrip(":")
                            if clean_token in ["PSS", "TOTAL"] and idx + 1 < len(parts):
                                clean_val = ''.join(filter(str.isdigit, parts[idx + 1]))
                                if clean_val and int(clean_val) > 0:
                                    total_pss = f"{int(clean_val):,} KB".replace(",", ".")
                                    has_active_process = True
                                    break

                    if "TOTAL RSS:" in line_str or "TOTAL RSS" in line_str or "RSS:" in line_str:
                        parts = line_str.split()
                        for idx, token in enumerate(parts):
                            if token.rstrip(":") == "RSS" and idx + 1 < len(parts):
                                clean_val = ''.join(filter(str.isdigit, parts[idx + 1]))
                                if clean_val:
                                    total_rss = f"{int(clean_val):,} KB".replace(",", ".")
                                    break

                    if "SWAP" in line_str:
                        parts = line_str.split()
                        for idx, token in enumerate(parts):
                            if "SWAP" in token and idx + 1 < len(parts):
                                next_token = parts[idx + 1].rstrip(":")
                                target_idx = idx + 2 if next_token == "PSS" and idx + 2 < len(parts) else idx + 1
                                clean_val = ''.join(filter(str.isdigit, parts[target_idx]))
                                if clean_val:
                                    swap_pss = f"{int(clean_val):,} KB".replace(",", ".")
                                    break

            data_eksternal = "0 KB / Dibatasi OS"
            try:
                ext_out = self.run_adb_local(["shell", "du", "-sh", f"/sdcard/Android/data/{pkg_name}"], timeout=5)
                if ext_out and "No such" not in ext_out and "denied" not in ext_out.lower():
                    data_eksternal = ext_out.split()[0].strip()
            except Exception:
                pass

            detail_text = f"===========================================================\n"
            detail_text += f" ANALISIS MEMORI & STORAGE EKSTERNAL: {app_name}\n"
            detail_text += f" Package: {pkg_name}\n"
            detail_text += f"===========================================================\n\n"
            
            if not has_active_process:
                detail_text += f"⚠️ STATUS RAM: Aplikasi sedang tidak aktif / terhenti di RAM.\n\n"
            else:
                detail_text += f"🧠 RINCIAN PENGGUNAAN MEMORI RAM:\n"
                detail_text += f" • Native Heap  : {native_heap}\n"
                detail_text += f" • Dalvik Heap  : {dalvik_heap}\n"
                detail_text += f" • Graphics     : {graphics}\n"
                detail_text += f" • TOTAL PSS    : {total_pss} (RAM fisik terpakai)\n"
                detail_text += f" • TOTAL RSS    : {total_rss} (Termasuk shared memory)\n"
                detail_text += f" • SWAP PSS     : {swap_pss} (Memori virtual)\n\n"

            detail_text += f"📁 STORAGE EKSTERNAL (/sdcard/Android/data):\n"
            detail_text += f" • Ukuran Data  : {data_eksternal}\n"

            self.root.after(0, self._render_memory_detail_text, detail_text, app_name)

        except Exception as exc:
            err_msg = str(exc)
            self.root.after(0, self.show_error, "Gagal Memuat Detail Memori", err_msg)            

    def _render_memory_detail_text(self, detail_text, app_name):
        self.mem_detail_box.delete("1.0", tk.END)
        self.mem_detail_box.insert(tk.END, detail_text)
        self.status.set(f"Berhasil memuat analisis memori untuk {app_name}.")
        
    def load_uptime(self):
        # Memuat informasi berapa lama perangkat telah menyala tanpa henti (uptime)
        try:
            device_id = self.device.get().strip()
            if not device_id:
                messagebox.showwarning("Perangkat Belum Dipilih", "Pilih perangkat HP terlebih dahulu.", parent=self.root)
                return

            self.status.set("Mengambil data waktu menyala (uptime)...")
            self.root.update()

            raw_output = self.run_adb_local(["shell", "cat", "/proc/uptime"], timeout=10)
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
            self.st_text.insert(tk.END, f"===========================================================\n")
            self.st_text.insert(tk.END, f"            INFO WAKTU MENYALA PERANGKAT (UPTIME)          \n")
            self.st_text.insert(tk.END, f"===========================================================\n\n")
            self.st_text.insert(tk.END, f" HP Anda telah hidup / menyala non-stop selama:\n")
            self.st_text.insert(tk.END, f" ⏳ {time_str}\n\n")

            self.status.set("Berhasil memuat waktu uptime perangkat.")
        except Exception as exc:
            self.show_error("Gagal memuat uptime", exc)

    def load_processes(self, auto=False):
        """Manual refresh saat tombol diklik."""
        if not auto:
            self.status.set("Mengambil daftar proses...")
        device_id = self.device.get().strip()
        if device_id and not self.is_fetching_proc:
            self.is_fetching_proc = True
            threading.Thread(target=self._fetch_processes_worker, daemon=True).start()
            
    def change_process_priority(self):
        # Mengubah prioritas proses (nilai nice) berdasarkan PID yang dipilih
        selected_item = self.proc_tree.selection()
        if not selected_item:
            messagebox.showinfo("Pilih Proses", "Pilih salah satu baris proses dari tabel terlebih dahulu.", parent=self.root)
            return

        item_data = self.proc_tree.item(selected_item[0])['values']
        pid = item_data[0]

        new_nice = simpledialog.askinteger("Ubah Prioritas (Nice)", f"PID {pid}:\nMasukkan nilai Nice (-20 sampai 19):", minvalue=-20, maxvalue=19, parent=self.root)
        if new_nice is not None:
            try:
                self.run_adb_local(["shell", "renice", str(new_nice), str(pid)], timeout=10)
                self.status.set(f"Prioritas PID {pid} berhasil diubah menjadi {new_nice}.")
                self.load_processes(auto=False)
            except Exception as exc:
                self.show_error("Gagal mengubah prioritas", exc)

    def refresh_devices(self):
        # Mendeteksi perangkat ADB yang terhubung dan status otorisasi USB debugging
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
        # Memuat ringkasan sistem, hardware, baterai, dan suhu secara real-time
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
            self.dashboard_battery_level.set("-")
            self.dashboard_battery_temp.set("-")
            self.dashboard_cpu_temp.set("-")
            self.dashboard_battery_power.set("-")
            self.dashboard_battery_health.set("-")
            self.dashboard_battery_cycles.set("-")
            self.dashboard_battery_summary.set("-")
            self.dashboard_performance.set("-")
            self.dashboard_network_status.set("-")
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
            total_ram_kb, free_ram_kb = 0, 0
            for line in mem_info.splitlines():
                if "MemTotal" in line:
                    parts = line.split()
                    if len(parts) >= 2: total_ram_kb = int(parts[1])
                elif "MemAvailable" in line:
                    parts = line.split()
                    if len(parts) >= 2: free_ram_kb = int(parts[1])
            
            ram_gb = f"Total: {total_ram_kb / (1024*1024):.1f} GB | Tersedia: {free_ram_kb / (1024*1024):.1f} GB" if total_ram_kb > 0 else "Tidak diketahui"

            load_avg = self.run_adb_local(["shell", "cat", "/proc/loadavg"], timeout=4)
            performance_str = f"Load Avg: {load_avg}" if load_avg else "Stabil"

            battery_output = self.run_adb_local(["shell", "dumpsys", "battery"], timeout=6)
            battery_level, battery_temp_num, battery_volt, battery_health_status = "?", 0.0, "?", "Baik"
            cycles = "Tidak Didukung Sistem"
            
            for line in battery_output.splitlines():
                line_str = line.strip()
                if line_str.startswith("level:"):
                    battery_level = f"{line_str.split(':', 1)[1].strip()}%"
                elif line_str.startswith("temperature:"):
                    raw_temp = line_str.split(":", 1)[1].strip()
                    try:
                        battery_temp_num = int(raw_temp) / 10.0
                    except ValueError:
                        pass
                elif line_str.startswith("voltage:"):
                    battery_volt = f"{line_str.split(':', 1)[1].strip()} mV"
                elif line_str.startswith("health:"):
                    h_code = line_str.split(":", 1)[1].strip()
                    health_map = {"2": "Sehat (Good)", "3": "Panas Berlebih (Overheat)", "4": "Rusak (Dead)", "5": "Tegangan Berlebih"}
                    battery_health_status = health_map.get(h_code, f"Status Code {h_code}")
                elif "cycle" in line_str.lower():
                    cycles = line_str.split(":", 1)[1].strip()

            if cycles == "Tidak Didukung Sistem":
                try:
                    c_out = self.run_adb_local(["shell", "cat", "/sys/class/power_supply/battery/cycle_count"], timeout=3)
                    if c_out and c_out.isdigit():
                        cycles = f"{c_out} Kali Cas"
                    else:
                        cycles = "Dibatasi Sistem (Butuh Android 14+ / Root)"
                except Exception:
                    cycles = "Dibatasi Sistem (Butuh Android 14+ / Root)"
            else:
                cycles = f"{cycles} Kali Cas"

            cpu_temp_str = "N/A"
            for zone_idx in range(5):
                try:
                    thermal_out = self.run_adb_local(["shell", "cat", f"/sys/class/thermal/thermal_zone{zone_idx}/temp"], timeout=2)
                    if thermal_out and thermal_out.isdigit():
                        t_val = float(thermal_out)
                        if t_val > 1000: t_val /= 1000.0
                        if 10.0 < t_val < 110.0:
                            cpu_temp_str = f"{t_val:.1f}°C"
                            break
                except Exception:
                    pass

            wifi_is_on, ssid_name, data_is_on = self._get_active_network_state()
            if wifi_is_on:
                net_status = f"Terhubung ke Wi-Fi ({ssid_name}) — (Prioritas Utama)"
            elif data_is_on:
                net_status = "Terhubung ke Paket Data Seluler"
            else:
                net_status = "Tidak Ada Koneksi Internet Aktif"

            b_temp_str = f"{battery_temp_num}°C" if battery_temp_num > 0 else "N/A"
            summary_eval = []
            if "Good" in battery_health_status or "Sehat" in battery_health_status:
                summary_eval.append("Status Fisik: Prima")
            else:
                summary_eval.append(f"Status Fisik: {battery_health_status}")

            if battery_temp_num > 42.0:
                summary_eval.append("Suhu: Overheating! (Waspada)")
            elif battery_temp_num > 37.0:
                summary_eval.append("Suhu: Hangat")
            else:
                summary_eval.append("Suhu: Normal/Adem")

            battery_summary_text = " | ".join(summary_eval)

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
            
            self.dashboard_battery_level.set(battery_level)
            self.dashboard_battery_temp.set(b_temp_str)
            self.dashboard_cpu_temp.set(cpu_temp_str)
            self.dashboard_battery_power.set(battery_volt)
            self.dashboard_battery_health.set(battery_health_status)
            self.dashboard_battery_cycles.set(cycles)
            self.dashboard_battery_summary.set(battery_summary_text)
            
            self.dashboard_performance.set(performance_str)
            self.dashboard_network_status.set(net_status)
            self.dashboard_storage.set(storage_str)

        except Exception as exc:
            self.dashboard_connection.set("Gagal membaca detail perangkat")
            self.status.set(str(exc))

    def refresh_dashboard_loop(self):
        # Looping otomatis untuk memperbarui dashboard setiap 5 detik
        self.refresh_dashboard()
        self.root.after(5000, self.refresh_dashboard_loop)

    def device_info(self):
        # Menampilkan pop-up informasi singkat perangkat
        try:
            model = self.run_adb_local(["shell", "getprop", "ro.product.model"])
            android = self.run_adb_local(["shell", "getprop", "ro.build.version.release"])
            serial = self.device.get()
            messagebox.showinfo("Info perangkat", f"Model: {model}\nAndroid: {android}\nADB ID: {serial}", parent=self.root)
        except Exception as exc:
            self.show_error("Gagal membaca perangkat", exc)

    def start_mirroring(self):
        # Memulai screen mirroring menggunakan scrcpy
        self._start_scrcpy(screen_off=False)

    def start_mirroring_screen_off(self):
        # Memulai screen mirroring dengan mematikan layar fisik HP
        if not messagebox.askyesno("Konfirmasi", "Coba matikan layar fisik HP saat mirroring berjalan?", parent=self.root):
            return
        self._start_scrcpy(screen_off=True)

    def start_recording(self):
        # Memulai perekaman layar HP ke file video MP4
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
        # Fungsi internal untuk menjalankan proses scrcpy
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
        # Mengirim perintah untuk mengunci layar HP
        try:
            self.run_adb_local(["shell", "input", "keyevent", "26"])
            self.run_adb_local(["shell", "service", "call", "power", "16"])
            self.status.set("Perintah penguncian total layar dikirim.")
        except Exception as exc:
            self.show_error("Gagal mengunci layar", exc)

    def wake_screen(self):
        # Mengirim perintah untuk membangunkan layar HP
        try:
            self.run_adb_local(["shell", "input", "keyevent", "224"])
            self.status.set("Perintah bangunkan layar dikirim.")
        except Exception as exc:
            self.show_error("Gagal membangunkan layar", exc)

    def start_timer(self):
        # Memulai timer pembatas sesi penggunaan HP
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
        self.status.set(f"Timer sesi dimulai: {minutes} menit. HP akan tidur.")

    def stop_timer(self):
        # Menghentikan timer sesi
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
        # Membuka kunci layar HP otomatis dari laptop menggunakan PIN default
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
        # Fungsi perhitungan mundur waktu timer sesi
        if not self.timer_running or self.timer_start is None:
            return
        elapsed = int(time.monotonic() - self.timer_start)
        remaining = max(0, self.timer_limit - elapsed)
        self.timer_label.configure(text=f"{remaining // 60:02d}:{remaining % 60:02d}")
        
        if remaining <= 0:
            self.session_locked = True
            self.stop_timer()
            self.lock_screen()
            messagebox.showwarning("Batas Waktu Habis", "Batas waktu sesi habis!\nHP telah tidur.", parent=self.root)
            self._enforce_lock_loop()
            return
            
        self.timer_job = self.root.after(1000, self._tick_timer)

    def _enforce_lock_loop(self):
        # Loop penguncian ketat jika sesi habis agar HP tidak bisa dibuka sembarangan
        if self.session_locked and self.device.get().strip():
            try:
                power_state = self.run_adb_local(["shell", "dumpsys", "power"], timeout=5)
                is_screen_on = False
                for line in power_state.splitlines():
                    if "mWakefulness=" in line and ("Awake" in line or "Dreaming" in line):
                        is_screen_on = True
                        break
                    elif "Display Power: state=ON" in line:
                        is_screen_on = True
                        break
                
                if is_screen_on:
                    self.run_adb_local(["shell", "input", "keyevent", "26"], timeout=3)
                    self.run_adb_local(["shell", "service", "call", "power", "16"], timeout=3) 
                
                self.status.set("🔒 TERKUNCI: Memerlukan otorisasi laptop (PIN 12345678).")
            except Exception:
                pass
            self.root.after(1000, self._enforce_lock_loop)

    def load_packages(self):
        # Memuat daftar aplikasi pihak ketiga yang terinstal di HP
        try:
            self.status.set("Mengambil daftar aplikasi dan mengurutkan secara alfabetis...")
            self.root.update()

            output = self.run_adb_local(["shell", "pm", "list", "packages", "-3"], timeout=30)
            packages = []
            for line in output.splitlines():
                line_clean = line.strip().replace("\r", "")
                if line_clean.startswith("package:"):
                    pkg_name = line_clean.replace("package:", "").strip()
                    if pkg_name:
                        packages.append(pkg_name)       
            app_list = []
            for pkg in packages:
                app_name = "Tidak diketahui"
                try:
                    pkg_info = self.run_adb_local(["shell", "dumpsys", "package", pkg], timeout=4)
                    for line in pkg_info.splitlines():
                        if "applicationInfo" in line and "label=" in line:
                            val = line.split("label=")[1].strip()
                            if val.startswith("'") or val.startswith('"'):
                                quote = val[0]
                                end_idx = val.find(quote, 1)
                                if end_idx != -1:
                                    app_name = val[1:end_idx]
                            else:
                                app_name = val.split()[0].strip("'\"")
                            break
                except Exception:
                    pass

                if app_name == "Tidak diketahui" or not app_name:
                    app_name = self.extract_app_name(pkg)

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
        # Menghentikan paksa (force-stop) aplikasi yang dipilih dari tabel
        selected_items = self.app_tree.selection()
        if not selected_items:
            messagebox.showinfo("Pilih aplikasi", "Pilih salah satu atau beberapa aplikasi dari tabel terlebih dahulu.", parent=self.root)
            return
        
        selected_pkgs = [self.app_tree.item(item)['values'][1] for item in selected_items]
        if not messagebox.askyesno("Konfirmasi force stop", "Hentikan paksa aplikasi berikut?\n\n" + "\n".join(selected_pkgs), parent=self.root):
            return
        try:
            for package in selected_pkgs:
                pkg = package.strip() 
                if pkg:
                    self.run_adb_local(["shell", "am", "force-stop", pkg], timeout=20)
            self.status.set(f"{len(selected_pkgs)} aplikasi berhasil dihentikan paksa.")
            messagebox.showinfo("Selesai", "Perintah force-stop berhasil dikirim ke perangkat.", parent=self.root)
        except Exception as exc:
            self.show_error("Gagal force stop", exc)

    def push_file(self):
        # Mengirim file dari laptop ke folder Download di HP
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
        # Memasang file APK dari laptop ke perangkat HP
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
        # Membangun seluruh tampilan antarmuka (GUI) aplikasi menggunakan Tkinter ttk
        self.root.configure(bg="#F3F6FC")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=30)

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
        ttk.Label(header, text="USB + ADB (Real-Time Live Monitor)", wraplength=940, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 8))

        device_frame = ttk.LabelFrame(self.root, text="Perangkat Android", padding=10)
        device_frame.pack(fill="x", padx=12, pady=4)
        ttk.Label(device_frame, text="Device ID:").pack(side="left")
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device, state="readonly", width=32)
        self.device_combo.pack(side="left", padx=8)
        ttk.Button(device_frame, text="Refresh", command=self.refresh_devices).pack(side="left")
        ttk.Button(device_frame, text="Info perangkat", command=self.device_info).pack(side="left", padx=6)
        ttk.Label(device_frame, textvariable=self.status, wraplength=450).pack(side="left", padx=12, fill="x", expand=True)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)
        
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        dashboard_tab = ttk.Frame(self.notebook, padding=16)
        mirror_usage_tab = ttk.Frame(self.notebook, padding=12)
        network_tab = ttk.Frame(self.notebook, padding=12)
        apps_tab = ttk.Frame(self.notebook, padding=12)
        files_tab = ttk.Frame(self.notebook, padding=12)
        mem_tab = ttk.Frame(self.notebook, padding=12)
        process_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(dashboard_tab, text="Dashboard")
        self.notebook.add(mirror_usage_tab, text="Mirroring & Uptime")
        self.notebook.add(network_tab, text="Monitor Jaringan")
        self.notebook.add(apps_tab, text="Aplikasi")
        self.notebook.add(mem_tab, text="Manajemen Memori")
        self.notebook.add(process_tab, text="Manajemen Proses & CPU")
        self.notebook.add(files_tab, text="Transfer File")

        # Layout Tab Monitor Jaringan
        net_top = ttk.Frame(network_tab)
        net_top.pack(fill="x", pady=4)
        ttk.Button(net_top, text="🔄 Refresh Traffic", command=self.load_network_traffic).pack(side="left")
        ttk.Button(net_top, text="📶 Toggle Wi-Fi (On/Off)", command=self.toggle_wifi_connection).pack(side="left", padx=4)
        ttk.Button(net_top, text="📡 Toggle Data (On/Off)", command=self.toggle_data_connection).pack(side="left", padx=4)

        net_content_frame = ttk.Frame(network_tab)
        net_content_frame.pack(fill="both", expand=True, pady=6)

        card_main = ttk.LabelFrame(net_content_frame, text="🔹 Status Koneksi Utama (Prioritas Wi-Fi Dulu)", padding=10)
        card_main.pack(fill="x", pady=4)
        
        for lbl_txt, var_ref in [
            ("Koneksi yang Digunakan:", self.net_main_status),
            ("Nama Wi-Fi (SSID):", self.net_wifi_name),
            ("Latency / Ping (Google):", self.net_ping)
        ]:
            row = ttk.Frame(card_main)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=lbl_txt, width=25).pack(side="left")
            ttk.Label(row, textvariable=var_ref, font=("TkDefaultFont", 10, "bold")).pack(side="left")

        card_stats = ttk.LabelFrame(net_content_frame, text="📊 Kecepatan & Statistik Kuota Terpakai", padding=10)
        card_stats.pack(fill="x", pady=4)

        for lbl_txt, var_ref in [
            ("Kecepatan Download (Rx):", self.net_speed_dl),
            ("Kecepatan Upload (Tx):", self.net_speed_ul),
            ("Kuota Wi-Fi Terpakai:", self.net_wifi_quota),
            ("Kuota Paket Data:", self.net_mobile_quota),
            ("Total Keseluruhan Kuota:", self.net_total_quota)
        ]:
            row = ttk.Frame(card_stats)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=lbl_txt, width=25).pack(side="left")
            ttk.Label(row, textvariable=var_ref, font=("TkDefaultFont", 10, "bold")).pack(side="left")

        card_hotspot = ttk.LabelFrame(net_content_frame, text="🌐 Status Hotspot & Perangkat Klien Terhubung", padding=10)
        card_hotspot.pack(fill="both", expand=True, pady=4)

        hs_info_row = ttk.Frame(card_hotspot)
        hs_info_row.pack(fill="x", pady=2)
        ttk.Label(hs_info_row, text="Status Hotspot:", width=25).pack(side="left")
        ttk.Label(hs_info_row, textvariable=self.net_hotspot_status, font=("TkDefaultFont", 10, "bold")).pack(side="left")

        hs_src_row = ttk.Frame(card_hotspot)
        hs_src_row.pack(fill="x", pady=2)
        ttk.Label(hs_src_row, text="Sumber Internet Hotspot:", width=25).pack(side="left")
        ttk.Label(hs_src_row, textvariable=self.net_hotspot_source, font=("TkDefaultFont", 10, "bold")).pack(side="left")

        # Layout Dashboard Tab
        ttk.Label(dashboard_tab, text="Ringkasan Perangkat (Real-Time Dashboard)", font=("TkDefaultFont", 16, "bold")).pack(anchor="w", pady=(0, 12))

        info_frame = ttk.LabelFrame(dashboard_tab, text="Informasi Lengkap HP & Kesehatan Sistem", padding=12)
        info_frame.pack(fill="x", pady=4)

        for label, variable in [
            ("Status koneksi", self.dashboard_connection),
            ("Nama perangkat", self.dashboard_device_name),
            ("Model", self.dashboard_model),
            ("RAM & Penggunaan", self.dashboard_ram),
            ("CPU / Chipset", self.dashboard_cpu),
            ("Versi OS / UI", self.dashboard_os),
            ("Versi Android", self.dashboard_android),
            ("Update keamanan", self.dashboard_security),
            ("Versi pita basis", self.dashboard_baseband),
            ("Versi kernel", self.dashboard_kernel),
            ("Kapasitas Baterai", self.dashboard_battery_level),
            ("Suhu Baterai", self.dashboard_battery_temp),
            ("Suhu CPU / Prosessor", self.dashboard_cpu_temp),
            ("Tegangan Listrik", self.dashboard_battery_power),
            ("Status Kesehatan", self.dashboard_battery_health),
            ("Jumlah Cas (Cycles)", self.dashboard_battery_cycles),
            ("Ringkasan Baterai", self.dashboard_battery_summary),
            ("Performa Sistem", self.dashboard_performance),
            ("Status Jaringan", self.dashboard_network_status),
            ("Penyimpanan (/data)", self.dashboard_storage),
        ]:
            line = ttk.Frame(info_frame)
            line.pack(fill="x", pady=2)
            ttk.Label(line, text=label, width=22).pack(side="left")
            ttk.Label(line, textvariable=variable, font=("TkDefaultFont", 10, "bold")).pack(side="left", fill="x", expand=True)

        dashboard_buttons = ttk.Frame(dashboard_tab)
        dashboard_buttons.pack(fill="x", pady=12)
        ttk.Button(dashboard_buttons, text="Perbarui informasi", command=self.refresh_dashboard).pack(side="left")
        ttk.Button(dashboard_buttons, text="Refresh perangkat", command=self.refresh_devices).pack(side="left", padx=8)

        # Layout Tab Mirroring, Rekam & Uptime
        ttk.Label(mirror_usage_tab, text="Kontrol Layar & Perekaman (Scrcpy)", font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(0, 4))
        
        control_row = ttk.Frame(mirror_usage_tab)
        control_row.pack(anchor="w", pady=4)
        ttk.Button(control_row, text="Mulai Mirroring", command=self.start_mirroring).pack(side="left", padx=(0, 6))
        ttk.Button(control_row, text="Mirroring + Layar Mati", command=self.start_mirroring_screen_off).pack(side="left", padx=6)
        ttk.Button(control_row, text="Rekam Layar", command=self.start_recording).pack(side="left", padx=6)
        ttk.Button(control_row, text="Kunci Layar HP", command=self.lock_screen).pack(side="left", padx=6)
        ttk.Button(control_row, text="Bangunkan Layar", command=self.wake_screen).pack(side="left", padx=6)

        timer_box = ttk.LabelFrame(mirror_usage_tab, text="Timer Batas Sesi", padding=8)
        timer_box.pack(fill="x", pady=8)
        time_row = ttk.Frame(timer_box)
        time_row.pack(anchor="w", pady=2)
        ttk.Label(time_row, text="Batas sesi (menit):").pack(side="left")
        ttk.Entry(time_row, textvariable=self.minutes, width=8).pack(side="left", padx=8)
        ttk.Button(time_row, text="Mulai Timer", command=self.start_timer).pack(side="left", padx=4)
        ttk.Button(time_row, text="Hentikan Timer", command=self.stop_timer).pack(side="left", padx=4)
        
        self.timer_label = ttk.Label(timer_box, text="00:00", font=("TkDefaultFont", 14, "bold"))
        self.timer_label.pack(anchor="w", pady=4)

        st_box = ttk.LabelFrame(mirror_usage_tab, text="Waktu Menyala Perangkat (Uptime)", padding=8)
        st_box.pack(fill="both", expand=True, pady=6)
        
        st_top = ttk.Frame(st_box)
        st_top.pack(fill="x", pady=4)
        ttk.Button(st_top, text="⏱️ Cek Berapa Lama HP Menyala", command=self.load_uptime).pack(side="left", padx=4)
        
        st_frame = ttk.Frame(st_box)
        st_frame.pack(fill="both", expand=True, pady=4)
        st_scroll = ttk.Scrollbar(st_frame, orient="vertical")
        st_scroll.pack(side="right", fill="y")
        self.st_text = tk.Text(st_frame, wrap="word", bg="#121212", fg="#FFFFFF", font=("DejaVu Sans Mono", 10), yscrollcommand=st_scroll.set)
        self.st_text.pack(side="left", fill="both", expand=True)
        st_scroll.config(command=self.st_text.yview)

        # Layout Tab Manajemen Memori
        mem_top = ttk.Frame(mem_tab)
        mem_top.pack(fill="x", pady=6)
        ttk.Button(mem_top, text="🔄 Refresh Daftar Aplikasi", command=self.load_memory_packages_list).pack(side="left")
        ttk.Button(mem_top, text="📊 Analisis Memori Terpilih", command=self.load_memory_details_for_selected).pack(side="left", padx=8)

        mem_container = ttk.Frame(mem_tab)
        mem_container.pack(fill="both", expand=True, pady=4)

        left_frame = ttk.LabelFrame(mem_container, text="Daftar Aplikasi Pihak Ketiga", padding=8)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.mem_tree = ttk.Treeview(
            left_frame,
            columns=("Nama Aplikasi", "Nama Paket (Package)"),
            show="headings",
            height=20
        )
        self.mem_tree.heading("Nama Aplikasi", text="Nama Aplikasi")
        self.mem_tree.heading("Nama Paket (Package)", text="Package Name")
        self.mem_tree.column("Nama Aplikasi", width=180, anchor="w")
        self.mem_tree.column("Nama Paket (Package)", width=220, anchor="w")
        self.mem_tree.bind("<ButtonRelease-1>", self.on_mem_tree_click)

        mem_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.mem_tree.yview)
        self.mem_tree.configure(yscrollcommand=mem_scroll.set)
        self.mem_tree.pack(side="left", fill="both", expand=True)
        mem_scroll.pack(side="right", fill="y")

        right_frame = ttk.LabelFrame(mem_container, text="Detail Analisis Memori & Storage", padding=8)
        right_frame.pack(side="right", fill="both", expand=True, padx=(4, 0))

        detail_scroll = ttk.Scrollbar(right_frame, orient="vertical")
        detail_scroll.pack(side="right", fill="y")

        self.mem_detail_box = tk.Text(
            right_frame, wrap="word", bg="#121212", fg="#FFFFFF",
            font=("DejaVu Sans Mono", 9), yscrollcommand=detail_scroll.set
        )
        self.mem_detail_box.pack(side="left", fill="both", expand=True)
        detail_scroll.config(command=self.mem_detail_box.yview)

        # Layout Tab Manajemen Proses & CPU
        proc_top = ttk.Frame(process_tab)
        proc_top.pack(fill="x", pady=6)
        ttk.Button(proc_top, text="🔄 Muat Ulang Real-Time", command=self.load_processes).pack(side="left")
        ttk.Button(proc_top, text="⚙️ Ubah Prioritas (Renice)", command=self.change_process_priority).pack(side="left", padx=8)
        self.auto_refresh_proc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(proc_top, text="Auto Refresh (1.5s)", variable=self.auto_refresh_proc_var).pack(side="left", padx=12)

        tree_frame = ttk.Frame(process_tab)
        tree_frame.pack(fill="both", expand=True, pady=4)

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.proc_tree = ttk.Treeview(
            tree_frame, 
            columns=("PID", "USER", "STATUS", "PR", "NI", "VIRT", "RES", "SHR", "CPU (%)", "MEM (%)", "TIME+", "Nama Aplikasi / Proses", "Command Asli (Raw)"),
            show="headings",
            height=25
        )
        self.proc_tree.heading("PID", text="PID")
        self.proc_tree.heading("USER", text="User")
        self.proc_tree.heading("STATUS", text="Status")
        self.proc_tree.heading("PR", text="PR")
        self.proc_tree.heading("NI", text="NI")
        self.proc_tree.heading("VIRT", text="VIRT")
        self.proc_tree.heading("RES", text="RES")
        self.proc_tree.heading("SHR", text="SHR")
        self.proc_tree.heading("CPU (%)", text="CPU (%)")
        self.proc_tree.heading("MEM (%)", text="MEM (%)")
        self.proc_tree.heading("TIME+", text="Waktu CPU")
        self.proc_tree.heading("Nama Aplikasi / Proses", text="Nama Aplikasi / Proses")
        self.proc_tree.heading("Command Asli (Raw)", text="Command Asli (Raw)")

        self.proc_tree.column("PID", width=90, anchor="center", stretch=False)
        self.proc_tree.column("USER", width=100, anchor="center", stretch=True)
        self.proc_tree.column("STATUS", width=150, anchor="center", stretch=True)
        self.proc_tree.column("PR", width=80, anchor="center", stretch=False)
        self.proc_tree.column("NI", width=80, anchor="center", stretch=False)
        self.proc_tree.column("VIRT", width=75, anchor="center", stretch=True)
        self.proc_tree.column("RES", width=75, anchor="center", stretch=True)
        self.proc_tree.column("SHR", width=75, anchor="center", stretch=True)
        self.proc_tree.column("CPU (%)", width=65, anchor="center", stretch=True)
        self.proc_tree.column("MEM (%)", width=65, anchor="center", stretch=True)
        self.proc_tree.column("TIME+", width=120, anchor="center", stretch=True)
        self.proc_tree.column("Nama Aplikasi / Proses", width=400, anchor="w", stretch=True)
        self.proc_tree.column("Command Asli (Raw)", width=500, anchor="w", stretch=True)
        
        self.proc_tree.bind("<ButtonRelease-1>", self.on_proc_tree_click) 

        proc_v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.proc_tree.yview)
        proc_h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.proc_tree.xview)
        self.proc_tree.configure(yscrollcommand=proc_v_scroll.set, xscrollcommand=proc_h_scroll.set)

        self.proc_tree.grid(row=0, column=0, sticky="nsew")
        proc_v_scroll.grid(row=0, column=1, sticky="ns")
        proc_h_scroll.grid(row=1, column=0, sticky="ew")

        # Layout Tab Transfer File
        ttk.Label(files_tab, text="Kirim file dari laptop ke folder Download HP.").pack(anchor="w")
        ttk.Button(files_tab, text="Pilih file lalu kirim ke HP", command=self.push_file).pack(anchor="w", pady=8)
        ttk.Label(files_tab, text="Pilih APK untuk memasangnya pada HP yang terhubung.").pack(anchor="w", pady=(16, 0))
        ttk.Button(files_tab, text="Pilih APK lalu instal", command=self.install_apk).pack(anchor="w", pady=8)

        # Layout Tab Aplikasi
        app_top = ttk.Frame(apps_tab)
        app_top.pack(fill="x", pady=6)
        ttk.Button(app_top, text="🔄 Refresh", command=self.load_packages).pack(side="left")
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
        self.app_tree.column("Nama Aplikasi", width=320, anchor="w")
        self.app_tree.column("Nama Paket (Package)", width=600, anchor="w")
        self.app_tree.bind("<ButtonRelease-1>", self.on_app_tree_click) 

        app_scroll = ttk.Scrollbar(app_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=app_scroll.set)
        self.app_tree.pack(side="left", fill="both", expand=True)
        app_scroll.pack(side="right", fill="y")

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Separator(footer).pack(fill="x", pady=(0, 8))
        ttk.Label(footer, text="Status: ADB aktif (Real-Time Mode).").pack(anchor="w")

    def on_close(self):
        # Menutup aplikasi secara aman dan menghentikan proses latar belakang
        self.stop_timer()
        self.root.destroy()


def main():
    # Fungsi utama untuk menjalankan aplikasi GUI Tkinter
    root = tk.Tk()
    RemoteControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
