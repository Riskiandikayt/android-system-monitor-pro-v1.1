import os
import signal
import psutil
from utils.helpers import (
    format_bytes, draw_bar, section_title, truncate, confirm_action,
    percentage_color, BOLD, RESET, CYAN, GREEN, YELLOW, RED, GRAY,
    WHITE, MAGENTA, colored, get_terminal_size, pause
)

SORT_OPTIONS = {
    "1": ("cpu", "CPU Usage"),
    "2": ("ram", "RAM Usage"),
    "3": ("pid", "PID"),
    "4": ("name", "Nama"),
}


def get_processes(sort_by: str = "cpu", limit: int = 30) -> list[dict]:
    procs = []
    for proc in psutil.process_iter(
        ["pid", "name", "username", "status",
         "cpu_percent", "memory_info", "memory_percent", "cmdline"]
    ):
        try:
            info = proc.info
            mem_bytes = info["memory_info"].rss if info["memory_info"] else 0
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "user": info["username"] or "?",
                "status": info["status"] or "?",
                "cpu": info["cpu_percent"] or 0.0,
                "ram_bytes": mem_bytes,
                "ram_pct": info["memory_percent"] or 0.0,
                "cmdline": " ".join(info["cmdline"] or []) or info["name"] or "?",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if sort_by == "cpu":
        procs.sort(key=lambda x: x["cpu"], reverse=True)
    elif sort_by == "ram":
        procs.sort(key=lambda x: x["ram_bytes"], reverse=True)
    elif sort_by == "pid":
        procs.sort(key=lambda x: x["pid"])
    elif sort_by == "name":
        procs.sort(key=lambda x: x["name"].lower())

    return procs[:limit]


def render_process_table(procs: list[dict], sort_label: str = "CPU Usage") -> str:
    cols, _ = get_terminal_size()
    name_w = max(16, min(28, cols - 55))

    header = (
        f"  {BOLD}{CYAN}"
        f"{'PID':>7}  "
        f"{'NAMA':<{name_w}}  "
        f"{'CPU':>6}  "
        f"{'RAM':>10}  "
        f"{'RAM%':>5}  "
        f"{'STATUS':<10}"
        f"{RESET}"
    )
    separator = f"  {'─' * (cols - 4)}"

    lines = [
        section_title(f"Monitor Proses — Sort: {sort_label}"),
        f"  {GRAY}Total proses: {len(psutil.pids())}{RESET}",
        "",
        header,
        separator,
    ]

    for p in procs:
        cpu_color = percentage_color(p["cpu"])
        ram_color = percentage_color(p["ram_pct"])
        status_color = GREEN if p["status"] == "running" else GRAY
        name = truncate(p["name"], name_w)

        lines.append(
            f"  {GRAY}{p['pid']:>7}{RESET}  "
            f"{WHITE}{name:<{name_w}}{RESET}  "
            f"{cpu_color}{p['cpu']:>5.1f}%{RESET}  "
            f"{ram_color}{format_bytes(p['ram_bytes']):>10}{RESET}  "
            f"{ram_color}{p['ram_pct']:>4.1f}%{RESET}  "
            f"{status_color}{p['status']:<10}{RESET}"
        )

    return "\n".join(lines)


def process_detail(pid: int) -> str | None:
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            name = proc.name()
            status = proc.status()
            cpu = proc.cpu_percent(interval=0.3)
            mem = proc.memory_info()
            mem_pct = proc.memory_percent()
            try:
                cmdline = " ".join(proc.cmdline()) or name
            except psutil.AccessDenied:
                cmdline = name
            try:
                user = proc.username()
            except psutil.AccessDenied:
                user = "N/A"
            try:
                create_time = proc.create_time()
                import time
                running_for = time.time() - create_time
                from utils.helpers import format_uptime
                uptime_str = format_uptime(running_for)
            except Exception:
                uptime_str = "N/A"
            try:
                num_threads = proc.num_threads()
            except Exception:
                num_threads = "N/A"

        lines = [
            section_title(f"Detail Proses: {name}"),
            f"  PID        : {CYAN}{pid}{RESET}",
            f"  Nama       : {BOLD}{name}{RESET}",
            f"  Perintah   : {GRAY}{truncate(cmdline, 60)}{RESET}",
            f"  User       : {user}",
            f"  Status     : {GREEN if status == 'running' else GRAY}{status}{RESET}",
            f"  CPU        : {colored(f'{cpu:.1f}%', percentage_color(cpu), bold=True)}",
            f"  RAM (RSS)  : {YELLOW}{format_bytes(mem.rss)}{RESET} ({mem_pct:.2f}%)",
            f"  RAM (VMS)  : {format_bytes(mem.vms)}",
            f"  Threads    : {num_threads}",
            f"  Running    : {uptime_str}",
        ]
        return "\n".join(lines)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def kill_process(pid: int) -> tuple[bool, str]:
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        if not confirm_action(
            f"Yakin ingin menghentikan proses '{BOLD}{name}{RESET}' (PID {pid})?"
        ):
            return False, "Dibatalkan oleh pengguna."
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3)
            return True, f"Proses '{name}' (PID {pid}) berhasil dihentikan (SIGTERM)."
        except psutil.TimeoutExpired:
            if confirm_action(f"Proses tidak merespons. Paksa kill (SIGKILL)?"):
                proc.send_signal(signal.SIGKILL)
                return True, f"Proses '{name}' (PID {pid}) di-kill paksa (SIGKILL)."
            return False, "Dibatalkan."
    except psutil.NoSuchProcess:
        return False, f"Proses PID {pid} sudah tidak ada."
    except psutil.AccessDenied:
        return False, f"Akses ditolak. Tidak bisa menghentikan PID {pid} (perlu root)."
    except Exception as e:
        return False, f"Error: {e}"


def show_process_menu():
    sort_by = "cpu"
    sort_label = "CPU Usage"
    limit = 25

    while True:
        procs = get_processes(sort_by=sort_by, limit=limit)
        print(render_process_table(procs, sort_label))

        print(f"\n  {BOLD}Opsi:{RESET}")
        print(f"  {CYAN}[1-4]{RESET} Ubah sortir  "
              f"{CYAN}[k]{RESET} Kill proses  "
              f"{CYAN}[d]{RESET} Detail proses  "
              f"{CYAN}[r]{RESET} Refresh  "
              f"{CYAN}[q]{RESET} Kembali")

        try:
            choice = input(f"\n  {YELLOW}Pilihan: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "q":
            break
        elif choice == "r":
            continue
        elif choice in SORT_OPTIONS:
            sort_by, sort_label = SORT_OPTIONS[choice]
        elif choice == "k":
            try:
                pid_str = input(f"  {YELLOW}Masukkan PID yang ingin dihentikan: {RESET}").strip()
                pid = int(pid_str)
                ok, msg = kill_process(pid)
                color = GREEN if ok else RED
                print(f"\n  {color}{msg}{RESET}")
                pause()
            except ValueError:
                print(f"  {RED}PID tidak valid.{RESET}")
                pause()
        elif choice == "d":
            try:
                pid_str = input(f"  {YELLOW}Masukkan PID: {RESET}").strip()
                pid = int(pid_str)
                detail = process_detail(pid)
                if detail:
                    print(detail)
                else:
                    print(f"  {RED}Proses tidak ditemukan atau akses ditolak.{RESET}")
                pause()
            except ValueError:
                print(f"  {RED}PID tidak valid.{RESET}")
                pause()
