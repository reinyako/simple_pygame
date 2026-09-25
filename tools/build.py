"""Membuat versi GEMA yang bisa dimainkan tanpa Python, memakai PyInstaller.

Jalankan di sistem operasi tujuan (file .exe Windows harus dibuat di Windows):
    pip install pyinstaller
    python tools/build.py

Hasilnya ada di dist/: zip siap kirim (GEMA-windows.zip, GEMA-macos.zip, atau GEMA-linux.zip).
"""

import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

README = {
    "windows": """GEMA, oleh v.obscura

Cara main:
1. Ekstrak zip ini.
2. Klik dua kali GEMA.exe.

Kalau muncul "Windows protected your PC", klik "More info" lalu "Run anyway".
Itu muncul karena game ini belum punya tanda tangan digital, bukan karena berbahaya.

Pakai earphone.
""",
    "macos": """GEMA, oleh v.obscura

Cara main:
1. Ekstrak zip ini.
2. Klik kanan GEMA.app, pilih Open, lalu Open lagi.

Kalau macOS tetap menolak: buka System Settings > Privacy & Security,
gulir ke bawah, lalu klik "Open Anyway" di bagian GEMA.
Itu muncul karena game ini belum ditandatangani Apple, bukan karena berbahaya.

Pakai earphone.
""",
    "linux": """GEMA, oleh v.obscura

Cara main:
1. Ekstrak zip ini.
2. Jalankan ./GEMA (kalau tidak bisa, jalankan dulu: chmod +x GEMA).

Pakai earphone.
""",
}


def target():
    return {"Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")


def pyinstaller(os_name):
    args = [
        sys.executable, "-m", "PyInstaller", "main.py",
        "--name", "GEMA", "--windowed", "--noconfirm", "--clean",
    ]
    # Windows & Linux: satu file saja, supaya tetap jalan walau dibuka langsung dari dalam zip.
    # macOS: bundle .app biasa.
    args.append("--onedir" if os_name == "macos" else "--onefile")
    subprocess.run(args, check=True, cwd=ROOT)


def package(os_name):
    out = DIST / f"GEMA-{os_name}.zip"
    out.unlink(missing_ok=True)
    readme = README[os_name].encode("utf-8")
    if os_name == "macos":
        # ditto menjaga izin eksekusi dan symlink di dalam .app.
        staging = DIST / "GEMA-macos"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        subprocess.run(["ditto", str(DIST / "GEMA.app"), str(staging / "GEMA.app")], check=True)
        (staging / "BACA DULU.txt").write_bytes(readme)
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(staging), str(out)], check=True)
        return out
    exe = DIST / ("GEMA.exe" if os_name == "windows" else "GEMA")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(f"GEMA/{exe.name}")
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o755 << 16  # izin eksekusi di Linux/macOS
        z.writestr(info, exe.read_bytes())
        z.writestr("GEMA/BACA DULU.txt", readme)
    return out


def main():
    os_name = target()
    pyinstaller(os_name)
    out = package(os_name)
    print(f"Selesai: {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
