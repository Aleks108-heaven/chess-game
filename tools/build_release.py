"""
Build a release: a standalone, one-folder app (no Python needed to run it), zipped, plus (on
Windows) a setup installer, with SHA-256 checksums.

    python tools/build_release.py                  # build, self-test, zip, installer, checksums
    python tools/build_release.py --skip-tests     # skip the pytest run (not recommended)
    python tools/build_release.py --no-installer   # portable zip only

Output goes to ``dist/`` (git-ignored):
    ChessGame-v<version>-<os>-<arch>.zip
    ChessGame-v<version>-windows-x64-setup.exe     (Windows, needs Inno Setup 6)
    SHA256SUMS.txt

The build refuses to produce an artifact unless (1) the test suite passes and (2) the built
program can start, draw every screen and play a move against the computer (``--self-test``).
The installer is then installed silently into a temporary folder, the installed program is
self-tested, and it is uninstalled again.

The installer needs Inno Setup 6 (``winget install JRSoftware.InnoSetup``).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import __version__  # noqa: E402

APP_NAME = "ChessGame"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
INSTALLER_SCRIPT = ROOT / "installer" / "ChessGame.iss"
# Uninstall registry key Inno Setup writes: "<AppId>_is1" (AppId is set in ChessGame.iss).
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{77095F83-B76B-45F3-AB55-E06CF7B9F6A0}_is1"

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


def find_iscc() -> Path | None:
    """Locate the Inno Setup compiler (PATH, then the per-user and machine-wide installs)."""
    found = shutil.which("iscc")
    if found:
        return Path(found)
    for variable, folder in (("LOCALAPPDATA", "Programs"), ("ProgramFiles", ""), ("ProgramFiles(x86)", "")):
        base = os.environ.get(variable)
        if base:
            candidate = Path(base, folder, "Inno Setup 6", "ISCC.exe")
            if candidate.exists():
                return candidate
    return None


def installed_copy_registered() -> bool:
    """True if a copy of the game is already installed (so a test install would clobber it)."""
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            winreg.CloseKey(winreg.OpenKey(hive, UNINSTALL_KEY))
            return True
        except OSError:
            continue
    return False


def build_installer(iscc: Path, app_dir: Path, setup_path: Path) -> None:
    command = [str(iscc), "/Q", f"/DAppVersion={__version__}", f"/DSourceDir={app_dir}",
               f"/DOutputDir={setup_path.parent}", str(INSTALLER_SCRIPT)]
    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():
        command.insert(-1, f"/DIconFile={icon}")
    run(command, cwd=ROOT)
    if not setup_path.exists():
        sys.exit(f"installer build failed: {setup_path} was not produced")


def smoke_test_installer(setup_path: Path, exe_name: str) -> None:
    """Install silently into a temp folder, self-test the installed program, uninstall."""
    if installed_copy_registered():
        print("WARNING: Chess Game is already installed on this machine; skipping the installer "
              "smoke test so the existing installation is left alone.", flush=True)
        return
    target = Path(tempfile.mkdtemp(prefix="chess-setup-test-")) / "ChessGame"
    log = BUILD / "setup-install.log"
    silent = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    print(f"smoke-testing {setup_path.name} (install to {target}) ...", flush=True)
    try:
        run([str(setup_path), *silent, "/CURRENTUSER", f"/DIR={target}", f"/LOG={log}"], timeout=300)
        exe = target / exe_name
        uninstaller = target / "unins000.exe"
        if not exe.exists() or not uninstaller.exists():
            sys.exit(f"installer smoke test failed: {exe} or its uninstaller is missing (see {log})")
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        result = subprocess.run([str(exe), "--self-test"], env=env, timeout=180)
        if result.returncode != 0:
            sys.exit(f"the installed program failed its self-test (exit code {result.returncode})")
        print("self-test of the installed program passed", flush=True)
    finally:
        uninstaller = target / "unins000.exe"
        if uninstaller.exists():
            subprocess.run([str(uninstaller), *silent], timeout=300)
            for _ in range(60):  # the uninstaller finishes from a temp copy of itself
                if not target.exists():
                    break
                time.sleep(0.5)
        leftover = target.exists()
        shutil.rmtree(target.parent, ignore_errors=True)
        if leftover:
            print("WARNING: the uninstaller left files behind; removed them from the temp folder.", flush=True)
        elif installed_copy_registered():
            print("WARNING: the test install is still registered in Add/Remove Programs.", flush=True)
    print("installer smoke test passed (install, run, uninstall)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--skip-tests", action="store_true", help="do not run pytest first")
    parser.add_argument("--no-installer", action="store_true", help="build the portable zip only")
    args = parser.parse_args()

    system = platform.system().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower())
    exe_name = f"{APP_NAME}.exe" if system == "windows" else APP_NAME
    artifact = f"{APP_NAME}-v{__version__}-{system}-{arch}"

    iscc = None
    if system == "windows" and not args.no_installer:
        iscc = find_iscc()
        if iscc is None:
            sys.exit("Inno Setup 6 was not found, so the setup installer cannot be built.\n"
                     "Install it with `winget install JRSoftware.InnoSetup`, or pass --no-installer "
                     "for the portable zip only.")

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
    artifacts = [zip_path]

    if iscc is not None:
        setup_path = DIST / f"{APP_NAME}-v{__version__}-windows-{arch}-setup.exe"
        build_installer(iscc, app_dir, setup_path)
        smoke_test_installer(setup_path, exe_name)
        artifacts.append(setup_path)

    (DIST / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts), encoding="utf-8")
    for path in artifacts:
        print(f"\nbuilt {path} ({path.stat().st_size / 1e6:.1f} MB)")
        print(f"sha256 {sha256(path)}")


if __name__ == "__main__":
    main()
