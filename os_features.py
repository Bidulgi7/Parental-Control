#!/usr/bin/env python3
"""Modul Logika Sistem Operasi (Manajemen Proses, Memori per Aplikasi, dan Screen Time)."""

class OSFeaturesHandler:
    def __init__(self, run_adb_func):
        self.run_adb_func = run_adb_func

    def get_process_table(self, device_id):
        """Mengambil SEMUA proses dari Android secara lengkap dan utuh dengan teknik batch kilat."""
        processes = []
        
        try:
            # 1. Ambil daftar tabel proses utama menggunakan ps -A
            output_ps = self.run_adb_func(device_id, args=["shell", "ps", "-A", "-o", "PID,USER,PR,NI,VIRT,RES,SHR,S,%CPU,%MEM,TIME,CMD"], timeout=8)
            if not output_ps:
                return []
                
            lines = output_ps.splitlines()
            
            # 2. Ambil SEMUA file cmdline dari direktori /proc sekaligus dalam 1 kali perintah ADB (Sangat Cepat)
            cmdlines = {}
            try:
                raw_cmdlines = self.run_adb_func(device_id, args=["shell", "for d in /proc/[0-9]*; do echo \"${d##*/}: $(cat $d/cmdline 2>/dev/null)\"; done"], timeout=3)
                if raw_cmdlines:
                    for cline in raw_cmdlines.splitlines():
                        if ":" in cline:
                            parts = cline.split(":", 1)
                            pid_val = parts[0].strip()
                            c_val = parts[1].strip().replace("\x00", " ").strip()
                            if c_val:
                                cmdlines[pid_val] = c_val
            except Exception:
                pass

            # 3. Gabungkan data ps dengan cmdline utuh secara lokal di memori Python (Tanpa jeda ADB beruntun)
            if len(lines) > 1:
                for line in lines[1:]:
                    tokens = line.split(None, 11)
                    if len(tokens) >= 12:
                        pid, user, pr, ni, virt, res, shr, stat, cpu, mem, time_val, cmd = tokens
                        
                        # Timpa command bawaan ps yang terpotong dengan command utuh dari /proc
                        if pid in cmdlines:
                            cmd = cmdlines[pid]

                        # Terjemahkan status agar jelas dibaca pengguna
                        if stat.startswith("R"):
                            status_display = "Running (Aktif)"
                        elif stat.startswith("S") or stat.startswith("D"):
                            status_display = "Sleeping (Latar Belakang)"
                        elif stat.startswith("T"):
                            status_display = "Stopped (Ditahan)"
                        elif stat.startswith("Z"):
                            status_display = "Zombie (Mati)"
                        else:
                            status_display = f"Status ({stat})"

                        cpu_pct = cpu + "%" if not cpu.endswith("%") else cpu
                        mem_pct = mem + "%" if not mem.endswith("%") else mem

                        processes.append((
                            pid, user, status_display, pr, ni, virt, res, shr, cpu_pct, mem_pct, time_val, cmd
                        ))
        except Exception:
            pass

        return processes
    def get_app_memory_usage(self, device_id, package_name):
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
        try:
            output = self.run_adb_func(device_id, args=["shell", "dumpsys", "batterystats"], timeout=15)
            app_times = []
            for line in output.splitlines():
                if "Foreground" in line or "proc" in line or "time" in line.lower() or "usage" in line.lower():
                    app_times.append(line.strip())
            return app_times[:35] if app_times else ["Data batterystats kosong."]
        except Exception:
            return ["Data screen time belum tersedia pada perangkat."]
