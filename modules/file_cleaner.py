import os
import time
from utils.helpers import (
    format_bytes, section_title, confirm_action, truncate,
    BOLD, RESET, CYAN, GREEN, YELLOW, RED, GRAY, WHITE, MAGENTA,
    colored, pause, get_terminal_size
)

PROTECTED_PATHS = {
    "/system", "/vendor", "/apex", "/odm", "/oem", "/product",
    "/proc", "/sys", "/dev", "/data/data", "/data/system",
    "/bin", "/sbin", "/lib", "/lib64", "/etc",
}

SAFE_EXTENSIONS = {
    ".tmp", ".temp", ".log", ".bak", ".old", ".cache",
    ".thumb", ".thumbnails",
}


def _is_protected(path: str) -> bool:
    abs_path = os.path.abspath(path)
    for p in PROTECTED_PATHS:
        if abs_path.startswith(p):
            return True
    parts = abs_path.split(os.sep)
    if "data" in parts and "data" in parts:
        idx = parts.index("data")
        if idx + 1 < len(parts) and parts[idx + 1] == "data":
            return True
    return False


def _format_file_row(idx: int, f: dict, cols: int) -> str:
    name = truncate(f["path"], cols - 20)
    size_str = format_bytes(f["size"])
    mark = f"{GREEN}✓{RESET}" if f.get("selected") else f"{GRAY}○{RESET}"
    protected = f"{RED}[PROTECTED]{RESET} " if f.get("protected") else ""
    return (
        f"  {mark} {GRAY}{idx:>3}.{RESET} {protected}"
        f"{size_str:>10}  {WHITE}{name}{RESET}"
    )


def show_file_cleaner_menu(preset_files: list[dict] | None = None):
    files: list[dict] = []
    cols, _ = get_terminal_size()

    def _load_preset():
        nonlocal files
        files = []
        for f in (preset_files or []):
            path = f.get("path", "")
            if not os.path.isfile(path):
                continue
            protected = _is_protected(path)
            files.append({
                "path": path,
                "name": os.path.basename(path),
                "size": f.get("size", 0),
                "protected": protected,
                "selected": not protected,
            })

    if preset_files:
        _load_preset()

    while True:
        print(section_title("File Cleaner (Safe Mode)"))
        print(
            f"\n  {YELLOW}⚠  PERINGATAN KEAMANAN:{RESET}\n"
            f"  File Cleaner HANYA bekerja pada folder yang Anda pilih sendiri.\n"
            f"  Semua penghapusan memerlukan konfirmasi manual.\n"
            f"  File sistem/Android tidak akan pernah disentuh.\n"
        )

        if not files:
            print(f"  {GRAY}Belum ada file yang dimuat.{RESET}\n")
            print(f"  {CYAN}[1]{RESET} Muat file dari Storage Analyzer")
            print(f"  {CYAN}[2]{RESET} Pilih folder untuk dibersihkan manual")
            print(f"  {CYAN}[q]{RESET} Kembali")
            try:
                c = input(f"\n  {YELLOW}Pilihan: {RESET}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if c == "q":
                break
            elif c == "1" and preset_files:
                _load_preset()
            elif c == "2":
                _manual_folder_select(files, cols)
            continue

        total_selected = sum(f["size"] for f in files if f.get("selected"))
        print(f"\n  {BOLD}Daftar File:{RESET} ({len(files)} total, "
              f"{GREEN}{sum(1 for f in files if f.get('selected'))} dipilih{RESET}, "
              f"akan hapus: {YELLOW}{format_bytes(total_selected)}{RESET})\n")

        for i, f in enumerate(files, 1):
            print(_format_file_row(i, f, cols))

        print(f"\n  {CYAN}[a]{RESET} Pilih semua  "
              f"{CYAN}[n]{RESET} Batal semua  "
              f"{CYAN}[t]{RESET} Toggle nomor  "
              f"{CYAN}[p]{RESET} Preview  "
              f"{CYAN}[d]{RESET} Hapus yang dipilih  "
              f"{CYAN}[c]{RESET} Tambah folder  "
              f"{CYAN}[q]{RESET} Kembali")

        try:
            choice = input(f"\n  {YELLOW}Pilihan: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "q":
            break
        elif choice == "a":
            for f in files:
                if not f["protected"]:
                    f["selected"] = True
        elif choice == "n":
            for f in files:
                f["selected"] = False
        elif choice == "t":
            try:
                nums = input(f"  {YELLOW}Nomor (misal: 1 3 5-8): {RESET}").strip()
                indices = _parse_indices(nums, len(files))
                for idx in indices:
                    f = files[idx]
                    if not f["protected"]:
                        f["selected"] = not f["selected"]
            except (ValueError, KeyboardInterrupt):
                print(f"  {RED}Input tidak valid.{RESET}")
                pause()
        elif choice == "p":
            _preview_deletion(files, cols)
        elif choice == "d":
            _execute_deletion(files)
            files = [f for f in files if os.path.isfile(f["path"])]
            if not files:
                print(f"\n  {GREEN}Semua file yang dipilih telah dihapus.{RESET}")
                pause()
                break
        elif choice == "c":
            _manual_folder_select(files, cols)


def _parse_indices(s: str, max_n: int) -> list[int]:
    indices = []
    for part in s.split():
        if "-" in part:
            a, b = part.split("-", 1)
            for n in range(int(a), int(b) + 1):
                if 1 <= n <= max_n:
                    indices.append(n - 1)
        else:
            n = int(part)
            if 1 <= n <= max_n:
                indices.append(n - 1)
    return indices


def _preview_deletion(files: list[dict], cols: int):
    selected = [f for f in files if f.get("selected")]
    if not selected:
        print(f"\n  {GRAY}Tidak ada file yang dipilih.{RESET}")
        pause()
        return
    total = sum(f["size"] for f in selected)
    print(f"\n  {BOLD}{YELLOW}Preview Penghapusan — {len(selected)} file, {format_bytes(total)} total:{RESET}\n")
    for f in selected:
        print(f"  {RED}✗{RESET}  {format_bytes(f['size']):>10}  {truncate(f['path'], cols - 20)}")
    print(f"\n  {BOLD}Total dibebaskan: {YELLOW}{format_bytes(total)}{RESET}")
    pause()


def _execute_deletion(files: list[dict]):
    selected = [f for f in files if f.get("selected") and not f.get("protected")]
    if not selected:
        print(f"\n  {GRAY}Tidak ada file yang dipilih.{RESET}")
        pause()
        return

    total = sum(f["size"] for f in selected)
    print(f"\n  {BOLD}{RED}KONFIRMASI PENGHAPUSAN FINAL{RESET}")
    print(f"  Akan menghapus {len(selected)} file ({format_bytes(total)} total).")
    print(f"  {RED}Tindakan ini TIDAK BISA DIBATALKAN!{RESET}")

    if not confirm_action(f"Lanjutkan penghapusan {len(selected)} file?"):
        print(f"  {YELLOW}Penghapusan dibatalkan.{RESET}")
        return

    success, failed = 0, 0
    freed = 0
    for f in selected:
        try:
            sz = f["size"]
            os.remove(f["path"])
            f["selected"] = False
            success += 1
            freed += sz
            print(f"  {GREEN}✓{RESET} Dihapus: {truncate(f['path'], 55)}")
        except OSError as e:
            failed += 1
            print(f"  {RED}✗{RESET} Gagal: {truncate(f['path'], 40)}  — {e}")

    print(f"\n  {GREEN}Selesai:{RESET} {success} file dihapus ({format_bytes(freed)} dibebaskan).")
    if failed:
        print(f"  {RED}{failed} file gagal dihapus.{RESET}")
    pause()


def _manual_folder_select(files: list[dict], cols: int):
    try:
        folder = input(f"\n  {YELLOW}Masukkan path folder: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        return
    if not os.path.isdir(folder):
        print(f"  {RED}Folder tidak ditemukan.{RESET}")
        pause()
        return
    if _is_protected(folder):
        print(f"  {RED}Folder ini dilindungi dan tidak bisa dibersihkan.{RESET}")
        pause()
        return

    new_files = []
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if os.path.isfile(fpath):
            try:
                sz = os.path.getsize(fpath)
                protected = _is_protected(fpath)
                new_files.append({
                    "path": fpath,
                    "name": fname,
                    "size": sz,
                    "protected": protected,
                    "selected": not protected,
                })
            except OSError:
                continue

    existing_paths = {f["path"] for f in files}
    added = 0
    for nf in new_files:
        if nf["path"] not in existing_paths:
            files.append(nf)
            added += 1

    print(f"  {GREEN}+{added} file baru dimuat dari {folder}{RESET}")
    pause()
