"""
Guardian Bot Module - Auto Bot Penjaga HP 24/7
================================================
Fitur:
- Mode penjaga otomatis 24/7 tanpa henti
- Alert otomatis saat kondisi kritis terdeteksi
- Log semua kejadian pemantauan
- Threshold yang dapat dikonfigurasi
- Statistik ringkasan penjagaan
"""

import os
import sys
import time
import threading
import asyncio
from datetime import datetime
from utils.helpers import (
    clear_screen, format_bytes, format_uptime, draw_bar, section_title,
    percentage_color, BOLD, RESET, CYAN, GREEN, YELLOW, RED, GRAY, WHITE,
    MAGENTA, colored, get_terminal_size, pause
)
from modules.system_monitor import snapshot_async

# ─── Konfigurasi Default ─────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "cpu_warning":      70.0,   # % CPU — peringatan
    "cpu_critical":     90.0,   # % CPU — kritis
    "ram_warning":      75.0,   # % RAM — peringatan
    "ram_critical":     90.0,   # % RAM — kritis
    "battery_low":      25.0,   # % baterai — peringatan rendah
    "battery_critical": 10.0,   # % baterai — kritis
    "temp_warning":     38.0,   # °C suhu baterai — peringatan
    "temp_critical":    45.0,   # °C suhu baterai — kritis
    "storage_warning":  80.0,   # % storage — peringatan
    "storage_critical": 92.0,   # % storage — kritis
    "check_interval":    5.0,   # detik antar pemeriksaan
}

# ─── State Global Guardian ────────────────────────────────────────────────────
_guardian_running   = False
_guardian_thread    = None
_guardian_lock      = threading.Lock()
_guardian_log: list = []         # list of dict {time, level, category, message}
_guardian_config    = dict(DEFAULT_CONFIG)
_guardian_stats     = {
    "start_time":    None,
    "checks_done":   0,
    "alerts_total":  0,
    "alerts_warn":   0,
    "alerts_crit":   0,
    "last_snap":     None,
}

MAX_LOG_ENTRIES = 500   # batas simpan log di memori


# ─── Helper ───────────────────────────────────────────────────────────────────

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _add_log(level: str, category: str, message: str):
    entry = {
        "time":     _now_str(),
        "level":    level,       # "INFO" | "WARN" | "CRIT"
        "category": category,
        "message":  message,
    }
    with _guardian_lock:
        _guardian_log.append(entry)
        if len(_guardian_log) > MAX_LOG_ENTRIES:
            _guardian_log.pop(0)
        if level == "WARN":
            _guardian_stats["alerts_warn"] += 1
            _guardian_stats["alerts_total"] += 1
        elif level == "CRIT":
            _guardian_stats["alerts_crit"] += 1
            _guardian_stats["alerts_total"] += 1


def _check_snapshot(snap: dict) -> list[dict]:
    """Periksa snapshot dan kembalikan list alert yang ditemukan."""
    cfg     = _guardian_config
    alerts  = []

    # CPU
    cpu = snap["cpu"]["overall"]
    if cpu >= cfg["cpu_critical"]:
        alerts.append({"level": "CRIT", "cat": "CPU",
                       "msg": f"CPU KRITIS: {cpu:.1f}% (threshold {cfg['cpu_critical']}%)"})
    elif cpu >= cfg["cpu_warning"]:
        alerts.append({"level": "WARN", "cat": "CPU",
                       "msg": f"CPU Tinggi: {cpu:.1f}% (threshold {cfg['cpu_warning']}%)"})

    # RAM
    ram = snap["ram"]["percent"]
    if ram >= cfg["ram_critical"]:
        alerts.append({"level": "CRIT", "cat": "RAM",
                       "msg": f"RAM KRITIS: {ram:.1f}% (threshold {cfg['ram_critical']}%)"})
    elif ram >= cfg["ram_warning"]:
        alerts.append({"level": "WARN", "cat": "RAM",
                       "msg": f"RAM Tinggi: {ram:.1f}% (threshold {cfg['ram_warning']}%)"})

    # Baterai level
    bat_level = snap["battery"].get("level")
    if bat_level is not None:
        if bat_level <= cfg["battery_critical"]:
            alerts.append({"level": "CRIT", "cat": "BATERAI",
                           "msg": f"BATERAI KRITIS: {bat_level:.0f}% — SEGERA CHARGE!"})
        elif bat_level <= cfg["battery_low"]:
            alerts.append({"level": "WARN", "cat": "BATERAI",
                           "msg": f"Baterai Rendah: {bat_level:.0f}%"})

    # Suhu baterai
    temp = snap["battery"].get("temperature")
    if temp is not None:
        if temp >= cfg["temp_critical"]:
            alerts.append({"level": "CRIT", "cat": "SUHU",
                           "msg": f"SUHU KRITIS: {temp:.1f}°C — Hentikan pengisian/gaming!"})
        elif temp >= cfg["temp_warning"]:
            alerts.append({"level": "WARN", "cat": "SUHU",
                           "msg": f"Suhu Tinggi: {temp:.1f}°C"})

    # Storage
    for part in snap["storage"]:
        pct = part["percent"]
        lbl = part["label"]
        if pct >= cfg["storage_critical"]:
            alerts.append({"level": "CRIT", "cat": "STORAGE",
                           "msg": f"STORAGE KRITIS: {lbl} {pct:.0f}% penuh — sisa {format_bytes(part['free'])}"})
        elif pct >= cfg["storage_warning"]:
            alerts.append({"level": "WARN", "cat": "STORAGE",
                           "msg": f"Storage {lbl} mulai penuh: {pct:.0f}%"})

    return alerts


def _guardian_loop():
    """Loop utama yang berjalan di background thread."""
    global _guardian_running

    _add_log("INFO", "SISTEM", "🛡️  Guardian Bot dimulai — mode penjagaan 24/7 aktif")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while _guardian_running:
        try:
            snap = loop.run_until_complete(snapshot_async())

            with _guardian_lock:
                _guardian_stats["checks_done"] += 1
                _guardian_stats["last_snap"] = snap

            alerts = _check_snapshot(snap)

            if not alerts:
                # Log INFO setiap 12 pemeriksaan (~1 menit) supaya tidak banjir
                if _guardian_stats["checks_done"] % 12 == 0:
                    cpu  = snap["cpu"]["overall"]
                    ram  = snap["ram"]["percent"]
                    bat  = snap["battery"].get("level", "?")
                    bat_s = f"{bat:.0f}%" if isinstance(bat, float) else str(bat)
                    _add_log("INFO", "SISTEM",
                             f"✅ Semua normal — CPU:{cpu:.1f}% RAM:{ram:.1f}% Baterai:{bat_s}")
            else:
                for a in alerts:
                    _add_log(a["level"], a["cat"], a["msg"])

        except Exception as e:
            _add_log("INFO", "ERROR", f"Error pemeriksaan: {e}")

        # Tidur dengan interval yang dapat diinterupsi
        interval = _guardian_config["check_interval"]
        slept = 0.0
        while slept < interval and _guardian_running:
            time.sleep(0.5)
            slept += 0.5

    loop.close()
    _add_log("INFO", "SISTEM", "🛑 Guardian Bot dihentikan.")


# ─── Public API ───────────────────────────────────────────────────────────────

def start_guardian() -> bool:
    """Mulai guardian bot di background. Return True jika berhasil start."""
    global _guardian_running, _guardian_thread

    if _guardian_running:
        return False  # sudah berjalan

    _guardian_running = True
    _guardian_stats["start_time"] = time.time()
    _guardian_stats["checks_done"] = 0
    _guardian_stats["alerts_total"] = 0
    _guardian_stats["alerts_warn"] = 0
    _guardian_stats["alerts_crit"] = 0

    _guardian_thread = threading.Thread(
        target=_guardian_loop,
        daemon=True,        # ikut mati saat program utama keluar
        name="GuardianBot"
    )
    _guardian_thread.start()
    return True


def stop_guardian() -> bool:
    """Hentikan guardian bot. Return True jika berhasil stop."""
    global _guardian_running
    if not _guardian_running:
        return False
    _guardian_running = False
    return True


def is_guardian_running() -> bool:
    return _guardian_running


def get_guardian_log(last_n: int = 50) -> list[dict]:
    with _guardian_lock:
        return list(_guardian_log[-last_n:])


def get_guardian_stats() -> dict:
    with _guardian_lock:
        return dict(_guardian_stats)


def get_guardian_config() -> dict:
    with _guardian_lock:
        return dict(_guardian_config)


def update_guardian_config(key: str, value: float) -> bool:
    if key not in DEFAULT_CONFIG:
        return False
    with _guardian_lock:
        _guardian_config[key] = value
    return True


# ─── Render ───────────────────────────────────────────────────────────────────

def _level_color(level: str) -> str:
    return {"INFO": GREEN, "WARN": YELLOW, "CRIT": RED}.get(level, GRAY)


def _level_icon(level: str) -> str:
    return {"INFO": "✅", "WARN": "⚠️ ", "CRIT": "🚨"}.get(level, "ℹ️ ")


def render_guardian_status(cols: int = 80) -> str:
    running = is_guardian_running()
    stats   = get_guardian_stats()
    cfg     = get_guardian_config()

    # Header status
    status_icon  = f"{GREEN}🛡️  AKTIF — Berjalan 24/7{RESET}" if running else f"{RED}⛔ TIDAK AKTIF{RESET}"
    uptime_str   = ""
    if running and stats["start_time"]:
        elapsed  = time.time() - stats["start_time"]
        uptime_str = f"  {GRAY}Berjalan selama: {format_uptime(elapsed)}{RESET}"

    lines = [
        section_title("Guardian Bot — Penjaga HP 24/7"),
        f"  Status     : {status_icon}",
    ]
    if uptime_str:
        lines.append(uptime_str)

    lines += [
        f"  Pemeriksaan: {CYAN}{stats['checks_done']:,}{RESET} kali",
        f"  Total Alert: {YELLOW}{stats['alerts_total']}{RESET}  "
        f"({YELLOW}⚠ {stats['alerts_warn']} peringatan{RESET} | "
        f"{RED}🚨 {stats['alerts_crit']} kritis{RESET})",
        f"  Interval   : {CYAN}{cfg['check_interval']:.0f} detik{RESET}",
        "",
        f"  {BOLD}Threshold Pemantauan:{RESET}",
        f"    CPU   : ⚠ >{cfg['cpu_warning']:.0f}%  🚨 >{cfg['cpu_critical']:.0f}%",
        f"    RAM   : ⚠ >{cfg['ram_warning']:.0f}%  🚨 >{cfg['ram_critical']:.0f}%",
        f"    Baterai: ⚠ <{cfg['battery_low']:.0f}%  🚨 <{cfg['battery_critical']:.0f}%",
        f"    Suhu  : ⚠ >{cfg['temp_warning']:.0f}°C  🚨 >{cfg['temp_critical']:.0f}°C",
        f"    Storage: ⚠ >{cfg['storage_warning']:.0f}%  🚨 >{cfg['storage_critical']:.0f}%",
    ]

    # Snapshot terakhir
    snap = stats.get("last_snap")
    if snap:
        bat = snap["battery"].get("level")
        bat_str = f"{bat:.0f}%" if bat is not None else "N/A"
        temp = snap["battery"].get("temperature")
        temp_str = f"{temp:.1f}°C" if temp is not None else "N/A"
        lines += [
            "",
            f"  {BOLD}Snapshot Terakhir:{RESET}",
            f"    CPU    : {colored(f\"{snap['cpu']['overall']:.1f}%\", percentage_color(snap['cpu']['overall']), bold=True)}",
            f"    RAM    : {colored(f\"{snap['ram']['percent']:.1f}%\", percentage_color(snap['ram']['percent']), bold=True)}",
            f"    Baterai: {bat_str}  ({snap['battery'].get('status', '?')})  Suhu: {temp_str}",
        ]

    return "\n".join(lines)


def render_guardian_log_display(last_n: int = 40) -> str:
    logs = get_guardian_log(last_n)
    cols, _ = get_terminal_size()
    lines = [section_title(f"Log Penjagaan (terakhir {last_n} entri)")]

    if not logs:
        lines.append(f"  {GRAY}Belum ada log. Mulai Guardian Bot terlebih dahulu.{RESET}")
        return "\n".join(lines)

    for entry in reversed(logs):   # terbaru di atas
        lc   = _level_color(entry["level"])
        icon = _level_icon(entry["level"])
        cat  = f"{BOLD}{entry['category']:<8}{RESET}"
        ts   = f"{GRAY}{entry['time']}{RESET}"
        msg  = f"{lc}{entry['message']}{RESET}"
        lines.append(f"  {icon} {ts}  {cat}  {msg}")

    return "\n".join(lines)


def render_live_guardian(stop_event: threading.Event):
    """Tampilkan live monitoring guardian sampai stop_event di-set."""
    cols, _ = get_terminal_size()
    while not stop_event.is_set():
        clear_screen()

        # Banner
        bar = "═" * cols
        title = " 🛡️  GUARDIAN BOT — LIVE MONITOR "
        side  = max(0, (cols - len(title)) // 2)
        print(f"{CYAN}{bar}{RESET}")
        print(f"{BOLD}{CYAN}{'═' * side}{WHITE}{title}{CYAN}{'═' * side}{RESET}")
        print(f"{CYAN}{bar}{RESET}")
        print(f"  {GRAY}Tekan Ctrl+C untuk kembali ke menu Guardian{RESET}\n")

        print(render_guardian_status(cols))
        print()
        print(render_guardian_log_display(last_n=25))
        print(f"\n{CYAN}{'─' * cols}{RESET}")
        print(f"  {GRAY}Diperbarui: {_now_str()}  |  Interval pemeriksaan: {_guardian_config['check_interval']:.0f}d{RESET}")

        stop_event.wait(timeout=3.0)


# ─── Menu Guardian ────────────────────────────────────────────────────────────

def _config_menu():
    """Sub-menu untuk ubah konfigurasi threshold."""
    cfg_keys = [
        ("cpu_warning",       "CPU Peringatan (%)",          "cpu_critical"),
        ("cpu_critical",      "CPU Kritis (%)",              None),
        ("ram_warning",       "RAM Peringatan (%)",          "ram_critical"),
        ("ram_critical",      "RAM Kritis (%)",              None),
        ("battery_low",       "Baterai Rendah (%)",          "battery_critical"),
        ("battery_critical",  "Baterai Kritis (%)",          None),
        ("temp_warning",      "Suhu Peringatan (°C)",        "temp_critical"),
        ("temp_critical",     "Suhu Kritis (°C)",            None),
        ("storage_warning",   "Storage Peringatan (%)",      "storage_critical"),
        ("storage_critical",  "Storage Kritis (%)",          None),
        ("check_interval",    "Interval Cek (detik, min 2)", None),
    ]

    clear_screen()
    cfg = get_guardian_config()
    print(section_title("Konfigurasi Threshold Guardian"))
    for i, (key, label, _) in enumerate(cfg_keys, 1):
        print(f"  {CYAN}[{i:>2}]{RESET} {label:<35} = {YELLOW}{cfg[key]}{RESET}")

    print(f"\n  {CYAN}[0]{RESET} Kembali (tanpa simpan)")
    print(f"  {CYAN}[r]{RESET} Reset ke default")

    try:
        choice = input(f"\n  {YELLOW}Pilih nomor untuk diubah: {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return

    if choice == "0":
        return
    if choice == "r":
        with _guardian_lock:
            _guardian_config.update(DEFAULT_CONFIG)
        print(f"  {GREEN}✓ Konfigurasi direset ke default.{RESET}")
        pause()
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(cfg_keys):
            raise ValueError
        key, label, _ = cfg_keys[idx]
        val_str = input(f"  {YELLOW}Nilai baru untuk '{label}': {RESET}").strip()
        val = float(val_str)
        if key == "check_interval":
            val = max(2.0, val)
        update_guardian_config(key, val)
        print(f"  {GREEN}✓ {label} diubah ke {val}{RESET}")
        pause()
    except (ValueError, IndexError):
        print(f"  {RED}Input tidak valid.{RESET}")
        pause()


def show_guardian_menu():
    """Menu utama Guardian Bot."""
    while True:
        cols, _ = get_terminal_size()
        clear_screen()

        bar = "═" * cols
        title = " 🛡️  Guardian Bot — Penjaga HP 24/7 "
        side  = max(0, (cols - len(title)) // 2)
        print(f"{CYAN}{bar}{RESET}")
        print(f"{BOLD}{CYAN}{'═' * side}{WHITE}{title}{CYAN}{'═' * side}{RESET}")
        print(f"{CYAN}{bar}{RESET}\n")

        running = is_guardian_running()
        stats   = get_guardian_stats()

        # Status ringkas
        if running:
            elapsed = time.time() - (stats["start_time"] or time.time())
            print(f"  Status  : {GREEN}🛡️  AKTIF{RESET}  — berjalan {format_uptime(elapsed)}")
            print(f"  Checks  : {CYAN}{stats['checks_done']:,}{RESET}   "
                  f"Alert: {YELLOW}{stats['alerts_warn']} warn{RESET} / "
                  f"{RED}{stats['alerts_crit']} kritis{RESET}")
        else:
            print(f"  Status  : {RED}⛔ TIDAK AKTIF{RESET}")
        print()

        # Menu
        toggle_label = f"{'🛑 Hentikan' if running else '▶️  Mulai'} Guardian Bot"
        menu_items = [
            ("1", toggle_label,                   "Start/stop penjagaan otomatis 24/7"),
            ("2", "📺 Live Monitor",               "Lihat status & log secara real-time"),
            ("3", "📋 Lihat Log Penjagaan",        "Riwayat semua alert & pemantauan"),
            ("4", "⚙️  Konfigurasi Threshold",     "Atur batas peringatan & kritis"),
            ("5", "📊 Statistik Penjagaan",        "Ringkasan total pemantauan"),
            ("q", "🔙 Kembali ke Menu Utama",      ""),
        ]

        for key, label, desc in menu_items:
            desc_str = f"  {GRAY}{desc}{RESET}" if desc else ""
            print(f"  {BOLD}{CYAN}[{key}]{RESET} {WHITE}{label:<38}{RESET}{desc_str}")

        print(f"\n{CYAN}{'─' * cols}{RESET}")

        try:
            choice = input(f"\n  {YELLOW}Pilih menu: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "q":
            break

        elif choice == "1":
            if running:
                ok = stop_guardian()
                if ok:
                    print(f"\n  {YELLOW}Guardian Bot dihentikan.{RESET}")
                else:
                    print(f"\n  {RED}Gagal menghentikan.{RESET}")
            else:
                ok = start_guardian()
                if ok:
                    print(f"\n  {GREEN}🛡️  Guardian Bot AKTIF — memantau HP 24/7...{RESET}")
                else:
                    print(f"\n  {YELLOW}Guardian Bot sudah berjalan.{RESET}")
            time.sleep(1.5)

        elif choice == "2":
            if not running:
                print(f"\n  {YELLOW}Guardian Bot belum aktif. Mulai dahulu dengan [1].{RESET}")
                pause()
                continue
            stop_event = threading.Event()
            try:
                render_live_guardian(stop_event)
            except KeyboardInterrupt:
                stop_event.set()
            print(f"\n  {GREEN}Live Monitor dihentikan.{RESET}")
            time.sleep(0.5)

        elif choice == "3":
            clear_screen()
            print(render_guardian_log_display(last_n=50))
            pause()

        elif choice == "4":
            _config_menu()

        elif choice == "5":
            clear_screen()
            stats = get_guardian_stats()
            cfg   = get_guardian_config()
            print(section_title("Statistik Penjagaan Guardian Bot"))

            if stats["start_time"]:
                elapsed = time.time() - stats["start_time"]
                print(f"  Mulai sejak    : {datetime.fromtimestamp(stats['start_time']).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Total berjalan : {format_uptime(elapsed)}")
            else:
                print(f"  Guardian belum pernah dijalankan sesi ini.")

            print(f"  Total cek      : {CYAN}{stats['checks_done']:,}{RESET}")
            print(f"  Total alert    : {YELLOW}{stats['alerts_total']}{RESET}")
            print(f"    ⚠ Peringatan : {YELLOW}{stats['alerts_warn']}{RESET}")
            print(f"    🚨 Kritis    : {RED}{stats['alerts_crit']}{RESET}")

            checks = max(stats["checks_done"], 1)
            alert_rate = stats["alerts_total"] / checks * 100
            print(f"  Tingkat alert  : {YELLOW}{alert_rate:.1f}%{RESET} dari semua pemeriksaan")
            print(f"  Interval cek   : {CYAN}{cfg['check_interval']:.0f} detik{RESET}")
            pause()

        else:
            print(f"  {RED}Pilihan tidak valid.{RESET}")
            time.sleep(1)
