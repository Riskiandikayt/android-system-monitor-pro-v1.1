# Android System Monitor Pro v1.1.0

Tool monitoring & optimasi Android secara real-time di Termux tanpa root.

## Fitur

1. **📊 Real-time Dashboard** — Monitor CPU, RAM, baterai, jaringan live
2. **⚙️ Process Monitor** — Lihat & kelola proses aktif
3. **🗂️ Storage Analyzer** — Scan & analisa penggunaan storage
4. **🧹 File Cleaner (Safe Mode)** — Hapus file aman dengan konfirmasi
5. **📈 Performance Analysis** — Analisa & rekomendasi optimasi
6. **💾 System Snapshot** — Snapshot sistem satu kali
7. **🛡️ Guardian Bot (Auto Penjaga)** *(BARU)* — Penjagaan otomatis HP 24/7 tanpa henti

## Instalasi

```bash
pkg install python
pip install psutil
python main.py
```

## Guardian Bot — Penjaga HP 24/7

Fitur baru Guardian Bot berjalan di **background thread** secara terus-menerus selama program aktif.

### Yang dipantau:
- 🔴 **CPU** — peringatan & kritis
- 🔴 **RAM** — peringatan & kritis  
- 🔋 **Baterai** — level rendah & kritis
- 🌡️ **Suhu** — baterai overheat
- 💾 **Storage** — hampir penuh

### Fitur Guardian:
- Live Monitor real-time (refresh otomatis)
- Log lengkap semua kejadian (peringatan & kritis)
- Statistik total pemantauan
- Threshold dapat dikonfigurasi sendiri
- Berjalan 24/7 tanpa henti di background

## Penggunaan

```bash
python main.py
# Pilih menu [7] untuk Guardian Bot
# Pilih [1] untuk Start Guardian
# Pilih [2] untuk Live Monitor
```
