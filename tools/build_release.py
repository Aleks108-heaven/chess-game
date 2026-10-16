"""
Build a release: a standalone, one-folder app (no Python needed to run it), zipped with a
SHA-256 checksum.

    python tools/build_release.py              # build, self-test, zip, checksum
    python tools/build_release.py --skip-tests # skip the pytest run (not recommended)

Output goes to ``dist/`` (git-ignored):
    ChessGame-v<version>-<os>-<arch>.zip
    SHA256SUMS.txt

The build refuses to produce an artifact unless (1) the test suite passes and (2) the built
program can start, draw every screen and play a move against the computer (``--self-test``).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import __version__  # noqa: E402

APP_NAME = "ChessGame"
DIST = ROOT / "dist"
BUILD = ROOT / "build"

README_TEXT = """\
Chess Game {version}
=====================

Run {exe} (no installation, no Python needed).

* Play vs the computer at five levels, Junior to Senior, or against a friend.
* Keys: Z undo, R new game, V 2D/3D view, F flip board, M mute, Esc menu.

Windows may show a "Windows protected your PC" (SmartScreen) or an application-control
warning the first time: this build is not code-signed. To check the download, compare the
SHA-256 of the zip with SHA256SUMS.txt from the release page:

    Get-FileHash ChessGame-v{version}-windows-x64.zip -Algorithm SHA256

Set CHESS_REDUCED_MOTION=1 to turn off the move animation and the pulsing indicator.
"""

VERSION_FILE_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0), mask=0x3f,
                    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', 'Chess Game'),
      StringStruct('FileVersion', '{version}.0'),
      StringStruct('InternalName', '{name}'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', 'Chess Game'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def run(command, **kwargs) -> None:
    print("$", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--skip-tests", action="store_true", help="do not run pytest first")
    args = parser.parse_args()

    system = platform.system().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower())
    exe_name = f"{APP_NAME}.exe" if system == "windows" else APP_NAME
    artifact = f"{APP_NAME}-v{__version__}-{system}-{arch}"

    if not args.skip_tests:
        run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)

    for folder in (BUILD, DIST):
        shutil.rmtree(folder, ignore_errors=True)
    BUILD.mkdir()
    DIST.mkdir()

    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", APP_NAME, "--distpath", str(DIST), "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--exclude-module", "pytest", "--exclude-module", "tkinter",
    ]
    icon = ROOT / "assets" / "icon.ico"
    if system == "windows":
        a, b, c = (int(part) for part in __version__.split("."))
        version_file = BUILD / "version_info.txt"
        version_file.write_text(VERSION_FILE_TEMPLATE.format(a=a, b=b, c=c, version=__version__,
                                                             name=APP_NAME), encoding="utf-8")
        command += ["--version-file", str(version_file)]
        if icon.exists():
            command += ["--icon", str(icon)]
    command.append(str(ROOT / "main.py"))
    run(command, cwd=ROOT)

    app_dir = DIST / APP_NAME
    exe = app_dir / exe_name
    if not exe.exists():
        sys.exit(f"build failed: {exe} was not produced")

    # Prove the packaged program works, not just the source tree.
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    print(f"self-testing {exe} ...", flush=True)
    result = subprocess.run([str(exe), "--self-test"], env=env, timeout=180)
    if result.returncode != 0:
        sys.exit(f"the built program failed its self-test (exit code {result.returncode})")
    print("self-test of the built program passed", flush=True)

    (app_dir / "README.txt").write_text(README_TEXT.format(version=__version__, exe=exe_name),
                                        encoding="utf-8")

    zip_path = DIST / f"{artifact}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(APP_NAME) / path.relative_to(app_dir))
    (DIST / "SHA256SUMS.txt").write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="utf-8")
    print(f"\nbuilt {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")
    print(f"sha256 {sha256(zip_path)}")


if __name__ == "__main__":
    main()
