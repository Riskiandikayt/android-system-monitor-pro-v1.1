import os
import time
import asyncio
import psutil
from utils.helpers import (
    format_bytes, format_uptime, draw_bar, section_title,
    percentage_color, safe_read_file, BOLD, RESET, CYAN, GREEN,
    YELLOW, RED, GRAY, WHITE, MAGENTA, colored, get_terminal_size
)

# Android battery info paths
BATTERY_BASE = "/sys/class/power_supply"


def _find_battery_path() -> str | None:
    if not os.path.exists(BATTERY_BASE):
        return None
    for name in ("battery", "Battery", "BAT0", "BAT1", "AC"):
        candidate = os.path.join(BATTERY_BASE, name)
        if os.path.isdir(candidate):
            return candidate
    try:
        entries = os.listdir(BATTERY_BASE)
        for entry in entries:
            p = os.path.join(BATTERY_BASE, entry)
            if os.path.isfile(os.path.join(p, "capacity")):
                return p
    except Exception:
        pass
    return None


def get_battery_info() -> dict:
    info = {
        "level": None,
        "status": "Unknown",
        "health": "Unknown",
        "temperature": None,
        "voltage": None,
        "technology": "Unknown",
    }
    path = _find_battery_path()
    if not path:
        try:
            bat = psutil.sensors_battery()
            if bat:
                info["level"] = round(bat.percent, 1)
                info["status"] = "Charging" if bat.power_plugged else "Discharging"
                if bat.secsleft and bat.secsleft > 0:
                    info["time_left"] = format_uptime(bat.secsleft)
        except Exception:
            pass
        return info

    def _read(name):
        return safe_read_file(os.path.join(path, name))

    cap = _read("capacity")
    if cap:
        try:
            info["level"] = float(cap)
        except ValueError:
            pass

    status = _read("status")
    if status:
        info["status"] = status

    health = _read("health")
    if health:
        info["health"] = health

    temp = _read("temp")
    if temp:
        try:
            info["temperature"] = float(temp) / 10.0
        except ValueError:
            pass

    voltage = _read("voltage_now")
    if voltage:
        try:
            info["voltage"] = float(voltage) / 1_000_000.0
        except ValueError:
            pass

    tech = _read("technology")
    if tech:
        info["technology"] = tech

    return info


def get_cpu_info() -> dict:
    per_core = psutil.cpu_percent(interval=0.3, percpu=True)
    overall = psutil.cpu_percent(interval=0)
    freq = psutil.cpu_freq(percpu=False)
    count_logical = psutil.cpu_count(logical=True)
    count_physical = psutil.cpu_count(logical=False)
    return {
        "overall": overall,
        "per_core": per_core,
        "freq_current": freq.current if freq else None,
        "freq_max": freq.max if freq else None,
        "count_logical": count_logical or 0,
        "count_physical": count_physical or 0,
    }


def get_ram_info() -> dict:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": vm.total,
        "available": vm.available,
        "used": vm.used,
        "percent": vm.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
    }


def get_storage_info() -> list[dict]:
    partitions = []
    seen = set()
    for part in psutil.disk_partitions(all=False):
        mp = part.mountpoint
        if mp in seen:
            continue
        skip_fs = {"tmpfs", "devtmpfs", "sysfs", "proc", "devpts",
                   "cgroup", "cgroup2", "pstore", "securityfs", "debugfs",
                   "tracefs", "configfs", "binder", "bpf"}
        if part.fstype in skip_fs:
            continue
        try:
            usage = psutil.disk_usage(mp)
            seen.add(mp)
            label = "Internal"
            if "sdcard" in mp.lower() or "external" in mp.lower() or "/storage/" in mp:
                if mp.rstrip("/").endswith("emulated/0") or mp == "/sdcard":
                    label = "Internal"
                else:
                    label = "External SD"
            partitions.append({
                "mountpoint": mp,
                "fstype": part.fstype,
                "label": label,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except (PermissionError, OSError):
            continue
    partitions.sort(key=lambda x: x["total"], reverse=True)
    return partitions


def get_network_info() -> dict:
    try:
        before = psutil.net_io_counters()
        time.sleep(0.5)
        after = psutil.net_io_counters()
        sent_rate = (after.bytes_sent - before.bytes_sent) * 2
        recv_rate = (after.bytes_recv - before.bytes_recv) * 2
        return {
            "bytes_sent_total": after.bytes_sent,
            "bytes_recv_total": after.bytes_recv,
            "sent_rate": sent_rate,
            "recv_rate": recv_rate,
        }
    except Exception:
        return {"bytes_sent_total": 0, "bytes_recv_total": 0, "sent_rate": 0, "recv_rate": 0}


def get_uptime() -> float:
    return time.time() - psutil.boot_time()


def render_battery(info: dict) -> str:
    level = info.get("level")
    status = info.get("status", "Unknown")
    health = info.get("health", "Unknown")
    temp = info.get("temperature")
    voltage = info.get("voltage")

    if level is None:
        bar_str = f"{GRAY}N/A{RESET}"
        level_str = "N/A"
    else:
        bar_str = draw_bar(level, 100, 20)
        color = percentage_color(100 - level)
        level_str = f"{colored(f'{level:.0f}%', percentage_color(100 - level), bold=True)}"

    status_color = GREEN if "Charg" in status else YELLOW
    lines = [
        section_title("Baterai"),
        f"  Level    : {bar_str} {level_str}",
        f"  Status   : {status_color}{status}{RESET}",
        f"  Health   : {GREEN if health == 'Good' else YELLOW}{health}{RESET}",
    ]
    if temp is not None:
        temp_color = RED if temp > 45 else (YELLOW if temp > 38 else GREEN)
        lines.append(f"  Suhu     : {temp_color}{temp:.1f}°C{RESET}")
    if voltage is not None:
        lines.append(f"  Voltage  : {CYAN}{voltage:.2f} V{RESET}")
    return "\n".join(lines)


def render_cpu(info: dict) -> str:
    cols, _ = get_terminal_size()
    bar_width = max(10, min(25, (cols - 30) // 2))
    lines = [section_title("CPU")]
    overall = info["overall"]
    lines.append(
        f"  Overall  : {draw_bar(overall, 100, bar_width)} "
        f"{colored(f'{overall:.1f}%', percentage_color(overall), bold=True)}"
    )
    if info["freq_current"]:
        lines.append(
            f"  Frekuensi: {CYAN}{info['freq_current']:.0f} MHz{RESET} "
            f"(max {info['freq_max']:.0f} MHz)" if info["freq_max"] else ""
        )
    lines.append(f"  Core     : {info['count_physical']} fisik / {info['count_logical']} logis")
    lines.append("")
    per_core = info["per_core"]
    half = (len(per_core) + 1) // 2
    for i, val in enumerate(per_core):
        b = draw_bar(val, 100, 10)
        label = f"Core{i:<2}"
        pct = f"{colored(f'{val:5.1f}%', percentage_color(val))}"
        lines.append(f"  {label}: {b} {pct}")
    return "\n".join(lines)


def render_ram(info: dict) -> str:
    lines = [section_title("RAM")]
    used = info["used"]
    total = info["total"]
    avail = info["available"]
    pct = info["percent"]
    bar = draw_bar(pct, 100, 20)
    lines.append(
        f"  Dipakai  : {bar} {colored(f'{pct:.1f}%', percentage_color(pct), bold=True)}"
    )
    lines.append(f"  Total    : {CYAN}{format_bytes(total)}{RESET}")
    lines.append(f"  Digunakan: {YELLOW}{format_bytes(used)}{RESET}")
    lines.append(f"  Tersedia : {GREEN}{format_bytes(avail)}{RESET}")
    if info["swap_total"] > 0:
        sb = draw_bar(info["swap_percent"], 100, 15)
        lines.append(
            f"  Swap     : {sb} {format_bytes(info['swap_used'])} / {format_bytes(info['swap_total'])}"
        )
    return "\n".join(lines)


def render_storage(partitions: list[dict]) -> str:
    lines = [section_title("Penyimpanan")]
    if not partitions:
        lines.append(f"  {GRAY}Tidak ada partisi yang terdeteksi{RESET}")
        return "\n".join(lines)
    for p in partitions:
        bar = draw_bar(p["percent"], 100, 18)
        lines.append(f"\n  {BOLD}{p['label']}{RESET} ({p['mountpoint']})")
        lines.append(
            f"    {bar} {colored(str(round(p['percent'], 1)) + '%', percentage_color(p['percent']), bold=True)}"
        )
        lines.append(
            f"    {format_bytes(p['used'])} digunakan / {format_bytes(p['total'])} total"
            f"  —  {GREEN}{format_bytes(p['free'])}{RESET} bebas"
        )
    return "\n".join(lines)


def render_network(info: dict) -> str:
    lines = [section_title("Jaringan")]
    lines.append(f"  ↑ Upload  : {YELLOW}{format_bytes(info['sent_rate'])}/s{RESET}  "
                 f"(total: {format_bytes(info['bytes_sent_total'])})")
    lines.append(f"  ↓ Download: {GREEN}{format_bytes(info['recv_rate'])}/s{RESET}  "
                 f"(total: {format_bytes(info['bytes_recv_total'])})")
    return "\n".join(lines)


async def snapshot_async() -> dict:
    loop = asyncio.get_event_loop()
    cpu_task = loop.run_in_executor(None, get_cpu_info)
    net_task = loop.run_in_executor(None, get_network_info)
    cpu_info, net_info = await asyncio.gather(cpu_task, net_task)
    return {
        "cpu": cpu_info,
        "ram": get_ram_info(),
        "storage": get_storage_info(),
        "battery": get_battery_info(),
        "network": net_info,
        "uptime": get_uptime(),
    }


def render_full_snapshot(snap: dict) -> str:
    uptime_str = format_uptime(snap["uptime"])
    parts = [
        f"\n  {BOLD}Uptime{RESET}: {CYAN}{uptime_str}{RESET}",
        render_cpu(snap["cpu"]),
        render_ram(snap["ram"]),
        render_storage(snap["storage"]),
        render_battery(snap["battery"]),
        render_network(snap["network"]),
    ]
    return "\n".join(parts)
