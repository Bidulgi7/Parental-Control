#!/usr/bin/env python3
"""Modul Khusus Komunikasi ADB dan Perangkat Android."""

import subprocess


def run_adb_cmd(device_id, *, args, timeout=15):
    """Fungsi dasar untuk menjalankan perintah ADB ke perangkat tertentu."""
    if not device_id:
        raise RuntimeError("Pilih perangkat terlebih dahulu.")
    command = ["adb", "-s", device_id, *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Perintah ADB gagal.")
    return result.stdout.strip()


def get_adb_devices():
    """Mengambil daftar perangkat ADB yang terhubung dan status otorisasi."""
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
    return devices, unauthorized
