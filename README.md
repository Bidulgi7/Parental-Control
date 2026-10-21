# Android Remote Control Center

Aplikasi desktop Python/Tkinter untuk mengelola **perangkat Android milik sendiri atau perangkat yang pengguna berwenang mengelolanya** melalui USB Debugging + ADB.

## Fitur
- Deteksi perangkat ADB dan info perangkat.
- Mirroring, mouse, dan keyboard melalui scrcpy (jendela scrcpy terpisah).
- Daftar aplikasi pihak ketiga dan `force-stop` dengan konfirmasi.
- Timer sesi; setelah batas waktu, meminta konfirmasi sebelum mengirim perintah tombol daya.
- Transfer file ke folder Download.
- Instal APK melalui ADB dengan konfirmasi.
- Opsi menjalankan scrcpy dengan layar HP dimatikan.

## Persyaratan
Ubuntu/Debian, Python 3, Tkinter, ADB, scrcpy, kabel USB yang mendukung data, dan HP Android dengan Developer Options + USB Debugging aktif.

Pasang dependensi:
```bash
sudo apt update
sudo apt install -y python3 python3-tk adb scrcpy git
```

## Menjalankan
```bash
python3 android_remote_control.py
```

Di HP, aktifkan Developer Options dan USB Debugging. Hubungkan kabel, buka dialog otorisasi RSA pada HP, lalu pilih **Allow/Izinkan**. Pastikan:
```bash
adb devices
```
menampilkan status `device`, bukan `unauthorized`.

## Batasan
- Mirroring dijalankan di jendela scrcpy terpisah, bukan tertanam di panel Tkinter.
- Timer hanya menghitung sesi yang dimulai dari aplikasi ini; bukan statistik penggunaan harian Android.
- `force-stop` tidak memblokir aplikasi secara permanen.
- Perintah tombol daya dapat mengunci atau membangunkan layar tergantung kondisi perangkat.
- Opsi layar mati bergantung pada dukungan scrcpy dan versi Android.
- Aplikasi tidak mencoba melewati kunci layar, otorisasi USB, atau mekanisme keamanan Android.

## Kolaborasi
Clone repository ini, buat branch masing-masing, lalu ajukan Pull Request:
```bash
git clone https://github.com/Bidulgi7/Parental-Control.git
cd Parental-Control
git switch -c nama-fitur
```
