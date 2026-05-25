import os
import sys
import time
import asyncio
import threading
from utils.helpers import (
    clear_screen, header_line, get_terminal_size, format_uptime,
    BOLD, RESET, CYAN, GREEN, YELLOW, RED, GRAY, WHITE, MAGENTA,
    colored, section_title
)
from modules.system_monitor import (
    snapshot_async, render_full_snapshot, get_battery_info,
    get_cpu_info, get_ram_info, get_storage_info, get_network_info,
    get_uptime, render_cpu, render_ram, render_storage, render_battery,
    render_network
)

APP_NAME = "Android System Monitor Pro"
VERSION  = "1.1.0"
REFRESH_INTERVAL = 2.0


def _banner(cols: int) -> str:
    title = f" {APP_NAME} v{VERSION} "
    side = max(0, (cols - len(title)) // 2)
    bar = "═" * cols
    return (
        f"{CYAN}{bar}{RESET}\n"
        f"{BOLD}{CYAN}{'═' * side}{WHITE}{title}{CYAN}{'═' * side}{RESET}\n"
        f"{CYAN}{bar}{RESET}"
    )


def _timestamp_line() -> str:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"  {GRAY}Diperbarui: {ts}  |  Tekan Ctrl+C untuk berhenti{RESET}"


def _guardian_status_line() -> str:
    """Tampilkan status guardian di header bila aktif."""
    try:
        from modules.guardian_bot import is_guardian_running, get_guardian_stats
        if is_guardian_running():
            stats = get_guardian_stats()
            elapsed = time.time() - (stats["start_time"] or time.time())
            return (
                f"  {GREEN}🛡️  Guardian AKTIF{RESET} — "
                f"berjalan {format_uptime(elapsed)} | "
                f"cek: {CYAN}{stats['checks_done']:,}{RESET} | "
                f"alert: {YELLOW}{stats['alerts_warn']}⚠{RESET} {RED}{stats['alerts_crit']}🚨{RESET}"
            )
    except Exception:
        pass
    return ""


def render_dashboard_frame(snap: dict) -> str:
    cols, _ = get_terminal_size()
    parts = [
        _banner(cols),
        _timestamp_line(),
    ]
    guardian_line = _guardian_status_line()
    if guardian_line:
        parts.append(guardian_line)
    parts += [
        render_full_snapshot(snap),
        f"\n{CYAN}{'─' * cols}{RESET}",
    ]
    return "\n".join(parts)


def render_performance_analysis(snap: dict) -> str:
    lines = [section_title("Analisa Performa & Rekomendasi")]

    cpu = snap["cpu"]
    ram = snap["ram"]
    bat = snap["battery"]
    storage = snap["storage"]

    issues: list[str] = []
    tips:   list[str] = []

    if cpu["overall"] > 85:
        issues.append(f"  {RED}• CPU sangat tinggi ({cpu['overall']:.1f}%) — cek proses berat di Process Monitor{RESET}")
    elif cpu["overall"] > 60:
        issues.append(f"  {YELLOW}• CPU cukup tinggi ({cpu['overall']:.1f}%) — pertimbangkan menutup aplikasi background{RESET}")

    if ram["percent"] > 85:
        issues.append(f"  {RED}• RAM hampir penuh ({ram['percent']:.1f}%) — tutup aplikasi yang tidak digunakan{RESET}")
        tips.append("  💡 Tutup aplikasi background di Recent Apps")
        tips.append("  💡 Gunakan Process Monitor untuk kill proses yang boros RAM")
    elif ram["percent"] > 70:
        issues.append(f"  {YELLOW}• RAM cukup penuh ({ram['percent']:.1f}%){RESET}")

    bat_level = bat.get("level")
    if bat_level is not None:
        if bat_level < 20:
            issues.append(f"  {RED}• Baterai kritis ({bat_level:.0f}%) — segera charge!{RESET}")
        elif bat_level < 30:
            issues.append(f"  {YELLOW}• Baterai rendah ({bat_level:.0f}%){RESET}")

    bat_temp = bat.get("temperature")
    if bat_temp and bat_temp > 45:
        issues.append(f"  {RED}• Suhu baterai sangat tinggi ({bat_temp:.1f}°C) — hentikan charging/gaming sementara!{RESET}")
    elif bat_temp and bat_temp > 38:
        issues.append(f"  {YELLOW}• Suhu baterai agak tinggi ({bat_temp:.1f}°C){RESET}")

    for part in storage:
        if part["percent"] > 90:
            issues.append(
                f"  {RED}• Storage {part['label']} hampir penuh ({part['percent']:.0f}%) "
                f"— sisa {format_bytes_inline(part['free'])}{RESET}"
            )
            tips.append("  💡 Gunakan Storage Analyzer untuk temukan dan hapus file besar/duplikat")
        elif part["percent"] > 75:
            issues.append(f"  {YELLOW}• Storage {part['label']} ({part['percent']:.0f}%) mulai penuh{RESET}")

    if not issues:
        lines.append(f"\n  {GREEN}✓ Sistem berjalan normal. Tidak ada masalah terdeteksi.{RESET}")
    else:
        lines.append(f"\n  {BOLD}Masalah Terdeteksi:{RESET}")
        lines.extend(issues)

    tips_general = [
        "  💡 Matikan WiFi/Bluetooth saat tidak digunakan untuk hemat baterai",
        "  💡 Kurangi kecerahan layar",
        "  💡 Gunakan Dark Mode jika HP AMOLED",
        "  💡 Hapus cache aplikasi secara berkala di Pengaturan → Aplikasi",
        "  💡 Gunakan Storage Analyzer untuk temukan file besar di Download/DCIM",
    ]
    lines.append(f"\n  {BOLD}Tips Hemat Baterai & Performa:{RESET}")
    all_tips = tips + tips_general
    for t in all_tips[:6]:
        lines.append(f"  {CYAN}{t.strip()}{RESET}")

    return "\n".join(lines)


def format_bytes_inline(b: float) -> str:
    from utils.helpers import format_bytes
    return format_bytes(b)


async def run_realtime_dashboard():
    print(f"\n  {CYAN}Memuat data awal...{RESET}")
    try:
        snap = await snapshot_async()
    except Exception as e:
        print(f"\n  {RED}Error saat memuat data: {e}{RESET}")
        return

    try:
        while True:
            clear_screen()
            print(render_dashboard_frame(snap))
            print(f"\n  {GRAY}Interval refresh: {REFRESH_INTERVAL}s{RESET}")
            await asyncio.sleep(REFRESH_INTERVAL)
            try:
                snap = await snapshot_async()
            except Exception:
                pass
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n\n  {GREEN}Dashboard dihentikan.{RESET}\n")


def show_dashboard_once():
    snap = asyncio.run(snapshot_async())
    clear_screen()
    print(render_dashboard_frame(snap))
    print(render_performance_analysis(snap))


def show_main_menu():
    while True:
        cols, _ = get_terminal_size()
        clear_screen()
        print(_banner(cols))
        print(f"\n  {GRAY}Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}{RESET}")

        # Tampilkan status guardian di menu utama
        guardian_line = _guardian_status_line()
        if guardian_line:
            print(guardian_line)
        print()

        menu_items = [
            ("1", "📊 Real-time Dashboard",         "Monitor CPU, RAM, baterai, jaringan"),
            ("2", "⚙️  Process Monitor",             "Lihat & kelola proses aktif"),
            ("3", "🗂️  Storage Analyzer",            "Scan & analisa penggunaan storage"),
            ("4", "🧹 File Cleaner (Safe Mode)",    "Hapus file aman dengan konfirmasi"),
            ("5", "📈 Performance Analysis",         "Analisa & rekomendasi optimasi"),
            ("6", "💾 System Snapshot",              "Snapshot sistem satu kali"),
            ("7", "🛡️  Guardian Bot (Auto Penjaga)", "Penjagaan otomatis HP 24/7 tanpa henti"),
            ("q", "🚪 Keluar",                      ""),
        ]

        for key, label, desc in menu_items:
            # Tandai Guardian Bot jika sedang aktif
            if key == "7":
                try:
                    from modules.guardian_bot import is_guardian_running
                    if is_guardian_running():
                        label = f"🛡️  Guardian Bot {GREEN}[AKTIF]{RESET}"
                except Exception:
                    pass
            desc_str = f"  {GRAY}{desc}{RESET}" if desc else ""
            print(f"  {BOLD}{CYAN}[{key}]{RESET} {WHITE}{label:<38}{RESET}{desc_str}")

        print(f"\n{CYAN}{'─' * cols}{RESET}")

        try:
            choice = input(f"\n  {YELLOW}Pilih menu: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            choice = "q"

        if choice == "q":
            # Hentikan guardian jika masih aktif sebelum keluar
            try:
                from modules.guardian_bot import is_guardian_running, stop_guardian
                if is_guardian_running():
                    stop_guardian()
                    print(f"\n  {YELLOW}Guardian Bot dihentikan.{RESET}")
                    time.sleep(0.5)
            except Exception:
                pass
            clear_screen()
            print(f"\n  {CYAN}Terima kasih sudah menggunakan {APP_NAME}!{RESET}\n")
            sys.exit(0)

        elif choice == "1":
            print(f"\n  {CYAN}Memulai Real-time Dashboard...{RESET}")
            print(f"  {GRAY}Tekan Ctrl+C untuk kembali ke menu.{RESET}\n")
            time.sleep(1)
            asyncio.run(run_realtime_dashboard())
            input(f"\n  {GRAY}Tekan Enter untuk kembali ke menu...{RESET}")

        elif choice == "2":
            clear_screen()
            from modules.process_monitor import show_process_menu
            show_process_menu()

        elif choice == "3":
            clear_screen()
            from modules.storage_analyzer import show_storage_analyzer_menu
            show_storage_analyzer_menu()

        elif choice == "4":
            clear_screen()
            from modules.file_cleaner import show_file_cleaner_menu
            show_file_cleaner_menu()

        elif choice == "5":
            clear_screen()
            print(f"\n  {CYAN}Mengambil snapshot sistem...{RESET}")
            snap = asyncio.run(snapshot_async())
            clear_screen()
            print(render_dashboard_frame(snap))
            print(render_performance_analysis(snap))
            input(f"\n  {GRAY}Tekan Enter untuk kembali...{RESET}")

        elif choice == "6":
            show_dashboard_once()
            input(f"\n  {GRAY}Tekan Enter untuk kembali...{RESET}")

        elif choice == "7":
            clear_screen()
            from modules.guardian_bot import show_guardian_menu
            show_guardian_menu()

        else:
            print(f"  {RED}Pilihan tidak valid.{RESET}")
            time.sleep(1)
