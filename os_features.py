#!/usr/bin/env python3
"""Modul Logika Sistem Operasi (Manajemen Proses, Memori per Aplikasi, dan Screen Time)."""

class OSFeaturesHandler:
    def __init__(self, run_adb_func):
        # Inisialisasi handler dengan fungsi eksekusi ADB yang diteruskan dari luar
        self.run_adb_func = run_adb_func

    def get_process_table(self, device_id):
        """Mengambil SEMUA proses dari Android secara kilat (<0.2 detik) menggunakan top -n 1."""
        processes = []
        
        try:
            # Menjalankan perintah terminal 'top' bawaan Android untuk mengambil daftar proses aktif
            output_top = self.run_adb_func(
                device_id, 
                args=["shell", "top", "-n", "1", "-b"], 
                timeout=4
            )
            
            # Fallback (cadangan) jika flag -b tidak didukung oleh versi ROM HP tertentu
            if not output_top:
                output_top = self.run_adb_func(
                    device_id, 
                    args=["shell", "top", "-n", "1"], 
                    timeout=4
                )
                
            if not output_top:
                return []

            lines = output_top.splitlines()
            header_found = False
            
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                
                # Mendeteksi baris header tabel proses pada output perintah top
                if "PID" in line_str and ("USER" in line_str or "ARGS" in line_str or "NAME" in line_str or "CPU" in line_str):
                    header_found = True
                    continue
                
                if not header_found:
                    continue

                tokens = line_str.split(None, 11)
                if len(tokens) >= 12:
                    pid, user, pr, ni, virt, res, shr, stat, cpu, mem, time_val, cmd = tokens
                elif len(tokens) >= 9:
                    # Menangani format alternatif untuk beberapa versi ROM Android
                    pid, user = tokens[0], tokens[1]
                    cpu, mem = tokens[2], tokens[3]
                    cmd = tokens[-1]
                    pr, ni, virt, res, shr, stat, time_val = "-", "-", "-", "-", "-", "S", "-"
                else:
                    continue

                # Memastikan token PID benar-benar berupa angka
                if not pid.isdigit():
                    continue

                # Menerjemahkan kode status proses Linux menjadi label yang mudah dibaca
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

                # Memformat persentase penggunaan CPU dan Memori
                cpu_pct = cpu if cpu.endswith("%") else cpu + "%"
                mem_pct = mem if mem.endswith("%") else mem + "%"

                # Menambahkan data proses yang sudah diparsing ke dalam list
                processes.append((
                    pid, user, status_display, pr, ni, virt, res, shr, cpu_pct, mem_pct, time_val, cmd
                ))
        except Exception:
            pass

        return processes
        
    def get_app_memory_usage(self, device_id, package_name):
        # Mengambil informasi penggunaan memori mendalam (dumpsys meminfo) untuk package tertentu
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
        # Mengambil statistik penggunaan baterai dan durasi aktivitas aplikasi (batterystats)
        try:
            output = self.run_adb_func(device_id, args=["shell", "dumpsys", "batterystats"], timeout=15)
            app_times = []
            for line in output.splitlines():
                if "Foreground" in line or "proc" in line or "time" in line.lower() or "usage" in line.lower():
                    app_times.append(line.strip())
            return app_times[:35] if app_times else ["Data batterystats kosong."]
        except Exception:
            return ["Data screen time belum tersedia pada perangkat."]
