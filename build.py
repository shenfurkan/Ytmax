"""
build.py  —  PyInstaller build script for YTmax
Run:  python build.py
"""
import os
from pathlib import Path

import PyInstaller.__main__


ROOT = Path(__file__).resolve().parent


def _add_data(src: str, dest: str = ".") -> str:
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dest}"


def main() -> None:
    debug = os.environ.get("DEBUG", "").strip() not in ("", "0", "false", "False")

    common_args: list[str] = [
        str(ROOT / "main.py"),
        "--windowed",
        f"--icon={ROOT / 'ytmax.ico'}",
        f"--add-data={_add_data(str(ROOT / 'ytmax.ico'))}",
        f"--add-data={_add_data(str(ROOT / 'ytmax.png'))}",
        "--hidden-import=yt_dlp",
        "--hidden-import=yt_dlp_ejs",
        "--hidden-import=customtkinter",
        "--hidden-import=PIL",
        "--hidden-import=downloader",
        "--noupx",
        "--clean",
        "--noconfirm",
    ]

    if debug:
        PyInstaller.__main__.run([
            "--name=YTmax_debug",
            "--onedir",
            *common_args,
        ])

    PyInstaller.__main__.run([
        "--name=YTmax",
        "--onefile",
        *common_args,
    ])

    print("\n✔ Build complete! Output is in the dist/ folder.")


if __name__ == "__main__":
    main()
