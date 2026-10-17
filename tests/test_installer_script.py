"""The Windows installer cannot be run in CI (it needs elevation), so pin what it promises.

tools/build_release.py compiles installer/ChessGame.iss and smoke-tests the result with a
per-user install; these checks guard the settings that smoke test cannot see.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "installer" / "ChessGame.iss").read_text(encoding="utf-8")
BUILD_SCRIPT = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")


def setup_value(name):
    match = re.search(rf"^{name}=(.*)$", SCRIPT, re.MULTILINE)
    assert match, f"{name} is not set in the [Setup] section"
    return match.group(1).strip()


def test_the_game_installs_for_all_users_into_program_files():
    assert setup_value("PrivilegesRequired") == "admin"
    assert setup_value("DefaultDirName").startswith("{autopf}\\"), "must resolve to Program Files"
    # Without 64-bit mode {autopf} would be "Program Files (x86)".
    assert setup_value("ArchitecturesInstallIn64BitMode") == "x64compatible"


def test_a_per_user_install_stays_available_from_the_command_line_only():
    assert setup_value("PrivilegesRequiredOverridesAllowed") == "commandline", \
        "no wizard dialog: the default is Program Files, /CURRENTUSER is for tests and no-admin users"
    assert '"/CURRENTUSER"' in BUILD_SCRIPT, "the build's smoke test installs without elevation"


def test_the_launch_after_install_does_not_run_the_game_as_administrator():
    run_section = SCRIPT.split("[Run]", 1)[1].split("[Code]", 1)[0]
    launch = [line for line in run_section.splitlines() if "postinstall" in line]
    assert len(launch) == 1 and "runasoriginaluser" in launch[0]


def test_the_app_id_never_changes():
    """It is how upgrades and the uninstaller recognise the program (see the script)."""
    assert setup_value("AppId") == "{{77095F83-B76B-45F3-AB55-E06CF7B9F6A0}"
    assert '#define AppGuid "{77095F83-B76B-45F3-AB55-E06CF7B9F6A0}"' in SCRIPT
    assert "77095F83-B76B-45F3-AB55-E06CF7B9F6A0" in BUILD_SCRIPT


def test_the_old_per_user_copy_is_removed_only_when_installing_for_all_users():
    assert "(CurStep = ssInstall) and IsAdminInstallMode" in SCRIPT
    assert "HKEY_CURRENT_USER" in SCRIPT and "_is1" in SCRIPT


def test_the_installer_adds_nothing_that_runs_by_itself():
    """No Run keys, scheduled tasks or services: it copies files, adds shortcuts, nothing more."""
    for forbidden in ("[Registry]", "[Services]", "schtasks", "Run\\", "RunOnce"):
        assert forbidden not in SCRIPT, forbidden
