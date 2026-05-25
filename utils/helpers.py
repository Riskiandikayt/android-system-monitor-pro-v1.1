import os
import sys
import time
import shutil
from datetime import timedelta

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"
GRAY    = "\033[90m"

BG_RED    = "\033[41m"
BG_GREEN  = "\033[42m"
BG_BLUE   = "\033[44m"
BG_DARK   = "\033[40m"


def colored(text: str, color: str, bold: bool = False) -> str:
    prefix = BOLD if bold else ""
    return f"{prefix}{color}{text}{RESET}"


def clear_screen():
    os.system("clear")


def get_terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.columns, size.lines


def format_bytes(byte_val: float, precision: int = 2) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(byte_val) < 1024.0:
            return f"{byte_val:.{precision}f} {unit}"
        byte_val /= 1024.0
    return f"{byte_val:.{precision}f} PB"


def format_uptime(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def draw_bar(
    value: float,
    max_val: float = 100.0,
    width: int = 20,
    filled_char: str = "█",
    empty_char: str = "░",
    color_thresholds: tuple = (60, 85),
) -> str:
    ratio = max(0.0, min(1.0, value / max_val)) if max_val else 0.0
    filled = int(ratio * width)
    empty = width - filled
    bar = filled_char * filled + empty_char * empty

    low, high = color_thresholds
    if ratio * 100 < low:
        color = GREEN
    elif ratio * 100 < high:
        color = YELLOW
    else:
        color = RED

    return f"{color}{bar}{RESET}"


def header_line(title: str, width: int = 0) -> str:
    if not width:
        width, _ = get_terminal_size()
    line = "─" * width
    side = max(0, (width - len(title) - 2) // 2)
    return (
        f"{CYAN}{line}{RESET}\n"
        f"{BOLD}{CYAN}{'─' * side} {title} {'─' * side}{RESET}\n"
        f"{CYAN}{line}{RESET}"
    )


def section_title(title: str) -> str:
    return f"\n{BOLD}{BLUE}◈ {title}{RESET}\n{'─' * (len(title) + 4)}"


def confirm_action(prompt: str) -> bool:
    while True:
        try:
            ans = input(f"\n{YELLOW}⚠  {prompt} [y/N]: {RESET}").strip().lower()
            return ans in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False


def pause(msg: str = "Tekan Enter untuk lanjut..."):
    try:
        input(f"\n{GRAY}{msg}{RESET}")
    except (KeyboardInterrupt, EOFError):
        pass


def truncate(text: str, max_len: int, ellipsis: str = "…") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(ellipsis)] + ellipsis


def percentage_color(val: float) -> str:
    if val < 60:
        return GREEN
    if val < 85:
        return YELLOW
    return RED


def safe_read_file(path: str) -> str | None:
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return None


def spinner_frames() -> list[str]:
    return ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
