#!/usr/bin/env python3
"""Modul Konsep Teori Sistem Operasi (Concurrency, Mutex, Memory & Process Inspection)."""

import queue
import threading


class OSFeaturesHandler:
    def __init__(self, run_adb_func):
        self.run_adb_func = run_adb_func
        self.cmd_queue = queue.Queue()
        self.mutex = threading.Lock()
        self.is_worker_running = True

    def queue_worker(self, root_tk):
        """Worker thread yang memproses antrean perintah secara sinkron menggunakan Mutex."""
        while self.is_worker_running:
            try:
                task = self.cmd_queue.get(timeout=0.5)
                if task is None:
                    break

                func, args, callback = task

                # KRITIKAL SECTION: Dilindungi oleh Mutex Lock
                with self.mutex:
                    try:
                        result = func(*args)
                        if callback and root_tk:
                            root_tk.after(0, lambda res=result: callback(True, res))
                    except Exception as exc:
                        error_msg = str(exc)
                        if callback and root_tk:
                            root_tk.after(0, lambda err=error_msg: callback(False, err))

                self.cmd_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                pass

    def submit_to_queue(self, func, args=(), callback=None):
        """Memasukkan tugas baru ke dalam antrean (Queue) sistem."""
        self.cmd_queue.put((func, args, callback))

    def get_memory_info(self, device_id):
        """Membaca dan parsing /proc/meminfo untuk Manajemen Memori & Swapping."""
        output = self.run_adb_func(device_id, args=["shell", "cat", "/proc/meminfo"], timeout=10)
        memory_data = {}
        for line in output.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                memory_data[parts[0].strip()] = parts[1].strip()
        return memory_data

    @staticmethod
    def get_memory_description(key):
        """Keterangan teoretis OS untuk setiap parameter memori."""
        descriptions = {
            "MemTotal": "Total kapasitas RAM fisik yang dapat diakses oleh sistem operasi.",
            "MemFree": "Kapasitas RAM murni yang belum digunakan sama sekali.",
            "MemAvailable": "Estimasi RAM yang tersedia untuk menjalankan aplikasi baru tanpa swapping.",
            "Buffers": "Memori RAM yang dialokasikan untuk buffer blok disk I/O.",
            "Cached": "Memori RAM yang digunakan untuk cache file sistem/kernel.",
            "SwapTotal": "Total kapasitas ruang swap (memori virtual cadangan di storage).",
            "SwapFree": "Kapasitas ruang swap yang saat ini masih kosong/belum terpakai.",
            "VmallocTotal": "Total ruang memori virtual yang dialokasikan kernel.",
            "VmallocUsed": "Ruang memori virtual kernel yang sedang terpakai."
        }
        return descriptions.get(key, "Parameter manajemen memori kernel Linux.")

    def get_process_table(self, device_id):
        """Mengambil daftar proses dengan memastikan nama aplikasi/command terbaca utuh."""
        try:
            output = self.run_adb_func(device_id, args=["shell", "top", "-n", "1", "-b"], timeout=15)
            processes = []
            lines = output.splitlines()
            data_started = False

            for line in lines:
                # Deteksi baris header dari perintah top Android
                if "PID" in line and ("CPU" in line or "COMMAND" in line or "NAME" in line):
                    data_started = True
                    continue

                if data_started and line.strip():
                    # Pisahkan maksimal 8 bagian pertama, biarkan sisa baris menjadi satu nama aplikasi utuh
                    parts = line.split(None, 8)
                    if len(parts) >= 9:
                        pid = parts[0]
                        user = parts[1]
                        cpu_pct = parts[2] + "%"
                        status = parts[3]
                        nice = "0"
                        # Mengambil kolom terakhir (indeks ke-8) yang berisi nama proses/aplikasi secara lengkap
                        name = parts[8].strip()

                        processes.append((pid, user, status, nice, cpu_pct, name))
            return processes
        except Exception as exc:
            raise RuntimeError(f"Gagal mengambil tabel proses: {str(exc)}")
