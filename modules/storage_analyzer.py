import os
import hashlib
import time
from collections import defaultdict
from utils.helpers import (
    format_bytes, section_title, confirm_action, truncate,
    BOLD, RESET, CYAN, GREEN, YELLOW, RED, GRAY, WHITE, MAGENTA,
    colored, spinner_frames, pause, get_terminal_size
)

DEFAULT_SCAN_DIRS = []

LARGE_FILE_THRESHOLD = 50 * 1024 * 1024   # 50 MB
EMPTY_FILE_THRESHOLD = 0                   # exactly 0 bytes

SKIP_DIRS = {
    "/proc", "/sys", "/dev", "/acct", "/d", "/vendor",
    "/system", "/apex", "/odm", "/oem", "/product",
}

COMMON_USER_DIRS = [
    os.path.expanduser("~/storage/downloads"),
    os.path.expanduser("~/storage/dcim"),
    os.path.expanduser("~/storage/documents"),
    os.path.expanduser("~/storage/pictures"),
    os.path.expanduser("~/storage/music"),
    os.path.expanduser("~/storage/movies"),
    "/sdcard/Download",
    "/sdcard/DCIM",
    "/sdcard/Documents",
    "/sdcard/Pictures",
    "/sdcard/Music",
    "/sdcard/Movies",
    "/sdcard/WhatsApp",
    os.path.expanduser("~"),
]


def get_available_dirs() -> list[str]:
    available = []
    for d in COMMON_USER_DIRS:
        if os.path.isdir(d):
            available.append(d)
    return list(dict.fromkeys(available))


def _file_hash(path: str, block_size: int = 65536) -> str | None:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(block_size):
                h.update(chunk)
        return h.hexdigest()
    except (IOError, OSError, PermissionError):
        return None


def scan_directory(
    root: str,
    progress_cb=None,
) -> dict:
    large_files: list[dict] = []
    empty_files: list[dict] = []
    all_files: list[dict] = []
    errors: list[str] = []
    total_size = 0
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and os.path.join(dirpath, d) not in SKIP_DIRS
        ]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(fpath, follow_symlinks=False)
                if not os.path.isfile(fpath):
                    continue
                size = stat.st_size
                mtime = stat.st_mtime
                entry = {
                    "path": fpath,
                    "name": fname,
                    "size": size,
                    "mtime": mtime,
                }
                all_files.append(entry)
                total_size += size
                file_count += 1
                if size >= LARGE_FILE_THRESHOLD:
                    large_files.append(entry)
                if size == EMPTY_FILE_THRESHOLD:
                    empty_files.append(entry)
                if progress_cb and file_count % 50 == 0:
                    progress_cb(file_count, total_size)
            except (OSError, PermissionError) as e:
                errors.append(str(e))

    large_files.sort(key=lambda x: x["size"], reverse=True)
    return {
        "root": root,
        "file_count": file_count,
        "total_size": total_size,
        "large_files": large_files[:50],
        "empty_files": empty_files[:100],
        "all_files": all_files,
        "errors": errors[:10],
    }


def find_duplicates(all_files: list[dict], progress_cb=None) -> list[list[dict]]:
    by_size: dict[int, list[dict]] = defaultdict(list)
    for f in all_files:
        if f["size"] > 0:
            by_size[f["size"]].append(f)

    candidate_groups = [g for g in by_size.values() if len(g) > 1]
    duplicates: list[list[dict]] = []
    processed = 0

    for group in candidate_groups:
        by_hash: dict[str, list[dict]] = defaultdict(list)
        for f in group:
            h = _file_hash(f["path"])
            if h:
                by_hash[h].append(f)
            processed += 1
            if progress_cb and processed % 20 == 0:
                progress_cb(processed)
        for h_group in by_hash.values():
            if len(h_group) > 1:
                duplicates.append(h_group)

    duplicates.sort(key=lambda g: g[0]["size"] * len(g), reverse=True)
    return duplicates


def render_scan_summary(result: dict, duplicates: list[list[dict]] | None = None) -> str:
    cols, _ = get_terminal_size()
    lines = [
        section_title(f"Hasil Scan: {result['root']}"),
        f"  Total file : {CYAN}{result['file_count']:,}{RESET}",
        f"  Total ukuran: {CYAN}{format_bytes(result['total_size'])}{RESET}",
    ]

    if result["large_files"]:
        lines.append(f"\n  {BOLD}{YELLOW}File Besar (> {format_bytes(LARGE_FILE_THRESHOLD)}):{RESET}")
        for i, f in enumerate(result["large_files"][:15], 1):
            name = truncate(f["path"], cols - 20)
            lines.append(f"  {GRAY}{i:>3}.{RESET} {format_bytes(f['size']):>10}  {name}")

    if result["empty_files"]:
        lines.append(f"\n  {BOLD}{GRAY}File Kosong ({len(result['empty_files'])} file):{RESET}")
        for f in result["empty_files"][:10]:
            lines.append(f"  {GRAY}  • {truncate(f['path'], cols - 10)}{RESET}")
        if len(result["empty_files"]) > 10:
            lines.append(f"  {GRAY}  ... dan {len(result['empty_files']) - 10} file lainnya{RESET}")

    if duplicates is not None:
        dup_count = sum(len(g) - 1 for g in duplicates)
        dup_size = sum(f["size"] * (len(g) - 1) for g in duplicates for f in [g[0]])
        lines.append(f"\n  {BOLD}{MAGENTA}File Duplikat:{RESET}")
        lines.append(f"  Grup duplikat: {MAGENTA}{len(duplicates)}{RESET}")
        lines.append(f"  File redundan: {MAGENTA}{dup_count}{RESET}")
        lines.append(f"  Space bisa dihemat: {MAGENTA}{format_bytes(dup_size)}{RESET}")
        for i, group in enumerate(duplicates[:5], 1):
            lines.append(f"\n    {CYAN}Grup {i} ({format_bytes(group[0]['size'])} × {len(group)}):{RESET}")
            for f in group:
                lines.append(f"      {GRAY}{truncate(f['path'], cols - 10)}{RESET}")

    if result["errors"]:
        lines.append(f"\n  {GRAY}Error akses ({len(result['errors'])} item tidak bisa dibaca){RESET}")

    lines.append(f"\n  {BOLD}{GREEN}Rekomendasi:{RESET}")
    recs = []
    if result["large_files"]:
        top = result["large_files"][0]
        recs.append(f"  • File terbesar: {truncate(top['path'], 40)} ({format_bytes(top['size'])})")
    if result["empty_files"]:
        recs.append(f"  • Ada {len(result['empty_files'])} file kosong yang bisa dihapus")
    if duplicates:
        recs.append(f"  • Ada {len(duplicates)} grup duplikat — bisa dihemat {format_bytes(sum(f['size']*(len(g)-1) for g in duplicates for f in [g[0]]))}")
    if not recs:
        recs.append(f"  • Folder terlihat bersih!")
    lines.extend(recs)

    return "\n".join(lines)


def _spinner_scan(root: str) -> dict:
    frames = spinner_frames()
    count_holder = [0, 0]

    def progress_cb(n, size):
        count_holder[0] = n
        count_holder[1] = size
        frame = frames[n // 50 % len(frames)]
        print(f"\r  {CYAN}{frame}{RESET} Memindai... {n} file ({format_bytes(size)})", end="", flush=True)

    result = scan_directory(root, progress_cb=progress_cb)
    print(f"\r  {GREEN}✓{RESET} Scan selesai: {result['file_count']} file ({format_bytes(result['total_size'])}){' '*10}")
    return result


def show_storage_analyzer_menu():
    while True:
        available = get_available_dirs()
        print(section_title("Storage Analyzer"))
        print(f"\n  {BOLD}Direktori yang tersedia:{RESET}")
        for i, d in enumerate(available, 1):
            print(f"  {CYAN}[{i}]{RESET} {d}")
        print(f"  {CYAN}[c]{RESET} Masukkan path manual")
        print(f"  {CYAN}[q]{RESET} Kembali ke menu utama")

        try:
            choice = input(f"\n  {YELLOW}Pilih direktori untuk di-scan: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "q":
            break

        scan_root = None
        if choice == "c":
            try:
                path = input(f"  {YELLOW}Masukkan path: {RESET}").strip()
                if os.path.isdir(path):
                    scan_root = path
                else:
                    print(f"  {RED}Path tidak ditemukan.{RESET}")
                    pause()
                    continue
            except (KeyboardInterrupt, EOFError):
                continue
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    scan_root = available[idx]
                else:
                    print(f"  {RED}Pilihan tidak valid.{RESET}")
                    pause()
                    continue
            except ValueError:
                print(f"  {RED}Input tidak valid.{RESET}")
                pause()
                continue

        if scan_root:
            print(f"\n  {CYAN}Memulai scan: {scan_root}{RESET}")
            result = _spinner_scan(scan_root)

            find_dup = confirm_action("Cari file duplikat? (membutuhkan waktu lebih lama)")
            duplicates = None
            if find_dup:
                frames = spinner_frames()
                processed = [0]

                def dup_progress(n):
                    processed[0] = n
                    frame = frames[n // 20 % len(frames)]
                    print(f"\r  {CYAN}{frame}{RESET} Menghitung hash... {n} file", end="", flush=True)

                duplicates = find_duplicates(result["all_files"], progress_cb=dup_progress)
                print(f"\r  {GREEN}✓{RESET} Selesai. {len(duplicates)} grup duplikat ditemukan.{' '*15}")

            print(render_scan_summary(result, duplicates))

            print(f"\n  {CYAN}[f]{RESET} Bersihkan file dengan File Cleaner  "
                  f"{CYAN}[Enter]{RESET} Kembali")
            try:
                sub = input(f"\n  {YELLOW}Pilihan: {RESET}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                sub = ""
            if sub == "f":
                from modules.file_cleaner import show_file_cleaner_menu
                candidates = result["large_files"][:20] + result["empty_files"][:20]
                if duplicates:
                    for g in duplicates[:10]:
                        candidates.extend(g[1:])
                show_file_cleaner_menu(preset_files=candidates)
