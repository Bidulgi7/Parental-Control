#!/usr/bin/env python3
"""Modul Logika Sistem Operasi (Manajemen Proses, Memori per Aplikasi, dan Screen Time)."""

class OSFeaturesHandler:
    def __init__(self, run_adb_func):
        self.run_adb_func = run_adb_func

    def get_process_table(self, device_id):
        """Mengambil daftar proses dengan memastikan nama aplikasi/command terbaca utuh."""
        try:
            output = self.run_adb_func(device_id, args=["shell", "top", "-n", "1", "-b"], timeout=15)
            processes = []
            lines = output.splitlines()
            data_started = False

            for line in lines:
                if "PID" in line and ("CPU" in line or "COMMAND" in line or "NAME" in line):
                    data_started = True
                    continue

                if data_started and line.strip():
                    parts = line.split(None, 8)
                    if len(parts) >= 9:
                        pid = parts[0]
                        user = parts[1]
                        cpu_pct = parts[2] + "%"
                        status = parts[3]
                        nice = "0"
                        name = parts[8].strip()
                        processes.append((pid, user, status, nice, cpu_pct, name))
            return processes
        except Exception as exc:
            raise RuntimeError(f"Gagal mengambil tabel proses: {str(exc)}")

    def get_app_memory_usage(self, device_id, package_name):
        """Mengambil detail penggunaan memori RAM (PSS/RSS) untuk paket aplikasi tertentu."""
        try:
            output = self.run_adb_func(device_id, args=["shell", "dumpsys", "meminfo", package_name], timeout=15)
            summary_lines = []
            for line in output.splitlines():
                if "TOTAL" in line or "PSS" in line or "Java Heap" in line or "Native Heap" in line:
                    summary_lines.append(line.strip())
            return "\n".join(summary_lines) if summary_lines else output[:500]
        except Exception as exc:
            return f"Gagal memuat memori untuk {package_name}: {str(exc)}"

    def get_app_usage_stats(self, device_id):
        """Mengambil statistik waktu penggunaan (screen time) aplikasi."""
        try:
            output = self.run_adb_func(device_id, args=["shell", "dumpsys", "batterystats"], timeout=15)
            app_times = []
            for line in output.splitlines():
                if "Foreground" in line or "proc" in line or "time" in line.lower() or "usage" in line.lower():
                    app_times.append(line.strip())
            return app_times[:35] if app_times else ["Data batterystats kosong."]
        except Exception:
            return ["Data screen time belum tersedia pada perangkat."]
