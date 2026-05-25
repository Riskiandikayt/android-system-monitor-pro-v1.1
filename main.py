#!/usr/bin/env python3
"""
Android System Monitor Pro
==========================
Tool monitoring & optimasi Android secara real-time.
Dijalankan di Termux tanpa root.

Penggunaan:
    python main.py
"""

import sys
import os

MIN_PYTHON = (3, 8)
if sys.version_info < MIN_PYTHON:
    sys.exit(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ diperlukan. Versi saat ini: {sys.version}")


def check_dependencies() -> list[str]:
    missing = []
    try:
        import psutil
    except ImportError:
        missing.append("psutil")
    return missing


def install_prompt(missing: list[str]):
    print("\n╔══════════════════════════════════════════╗")
    print("║   Android System Monitor Pro — Setup    ║")
    print("╚══════════════════════════════════════════╝\n")
    print("Library berikut belum terinstall:\n")
    for pkg in missing:
        print(f"  - {pkg}")
    print("\nJalankan perintah berikut untuk menginstall:\n")
    print(f"  pip install {' '.join(missing)}\n")
    print("Atau:\n")
    print("  pip install -r requirements.txt\n")
    sys.exit(1)


def main():
    missing = check_dependencies()
    if missing:
        install_prompt(missing)

    # Tambahkan direktori project ke sys.path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    try:
        from modules.dashboard import show_main_menu
        show_main_menu()
    except KeyboardInterrupt:
        print("\n\n  Dihentikan oleh pengguna. Sampai jumpa!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n  Error tidak terduga: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
