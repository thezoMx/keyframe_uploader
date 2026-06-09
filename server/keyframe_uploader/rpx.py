"""rpx -- command-line launcher for the KeyframeUploader server.

Commands:
    rpx           Run the server.
    rpx setup     One-time interactive setup (API key, creator, rojo, plugin).
    rpx where     Show where everything lives and whether it's configured.
    rpx help      Show this help.

Installed as a console script via pyproject.toml (`pip install -e .`).
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

from . import server
from . import converter

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_INSTALL_NAME = "KeyframeUploader.lua"

API_KEYS_URL = "https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab"


def _plugins_dir() -> str:
    local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    return os.path.join(local, "Roblox", "Plugins")


def _installed_plugin_path() -> str:
    return os.path.join(_plugins_dir(), PLUGIN_INSTALL_NAME)


def _load_config() -> dict:
    """Read config.json quietly (without server.load_config's status prints)."""
    with open(server.CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(cfg: dict) -> None:
    with open(server.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


# --------------------------------------------------------------------------- #
# rojo auto-install (via rokit)
# --------------------------------------------------------------------------- #

def _rokit_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".rokit")


def _rokit_bin() -> str:
    exe = "rokit.exe" if os.name == "nt" else "rokit"
    return os.path.join(_rokit_home(), "bin", exe)


def _find_rokit() -> str:
    """Return a path to a runnable rokit, or None."""
    installed = _rokit_bin()
    if os.path.exists(installed):
        return installed
    return shutil.which("rokit")


def _rokit_asset_suffix() -> str:
    """The `<os>-<arch>` half of a rokit release asset name for this machine."""
    if os.name == "nt":
        os_part = "windows"
    elif sys.platform == "darwin":
        os_part = "macos"
    else:
        os_part = "linux"
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    return "%s-%s" % (os_part, arch)


def _install_rokit() -> str:
    """Download the latest rokit release and run `rokit self-install`.

    Returns the path to the installed rokit binary.
    """
    import urllib.request
    import zipfile

    def _open(url):
        req = urllib.request.Request(url, headers={"User-Agent": "KeyframeUploader"})
        return urllib.request.urlopen(req)

    print("  rokit (Rojo's toolchain manager) not found -- installing it...")
    with _open("https://api.github.com/repos/rojo-rbx/rokit/releases/latest") as r:
        release = json.load(r)
    version = release["tag_name"].lstrip("v")
    asset_name = "rokit-%s-%s.zip" % (version, _rokit_asset_suffix())
    url = next((a["browser_download_url"] for a in release.get("assets", [])
                if a.get("name") == asset_name), None)
    if not url:
        raise RuntimeError("no rokit release asset named %s for this platform" % asset_name)

    tmp = tempfile.mkdtemp(prefix="ku_rokit_")
    try:
        zip_path = os.path.join(tmp, "rokit.zip")
        print("    downloading %s" % asset_name)
        with _open(url) as r, open(zip_path, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        exe = "rokit.exe" if os.name == "nt" else "rokit"
        extracted = os.path.join(tmp, exe)
        if not os.path.exists(extracted):
            raise RuntimeError("rokit binary missing from the downloaded archive")
        if os.name != "nt":
            os.chmod(extracted, 0o755)
        print("    running `rokit self-install`")
        subprocess.run([extracted, "self-install"], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return _rokit_bin()


def _install_rojo(cfg: dict) -> str:
    """Ensure rojo is installed (installing rokit first if needed). Returns its path."""
    rokit = _find_rokit() or _install_rokit()
    print("  installing rojo (`rokit add rojo-rbx/rojo --global`)...")
    subprocess.run([rokit, "add", "rojo-rbx/rojo", "--global"], check=True)
    return converter.find_rojo(cfg)


# --------------------------------------------------------------------------- #
# rpx setup
# --------------------------------------------------------------------------- #

def cmd_setup() -> None:
    import getpass

    cfg = _load_config()
    env_name = cfg.get("api_key_env", "ROBLOX_OPEN_CLOUD_KEY")
    print("KeyframeUploader setup. Press Enter to skip any step.\n")

    # 1) API key -> user env var
    print("1) Open Cloud API key")
    print("   Create one (enable the Assets API with read+write, and set the operating")
    print("   creator to your account) at:")
    print("   %s\n" % API_KEYS_URL)
    existing = server.read_secret(env_name)
    prompt = "   Paste API key [%s]: " % ("keep current" if existing else "not set")
    key = getpass.getpass(prompt).strip()
    if key:
        server.write_secret(env_name, key)
        print("   -> stored in %s (User scope).\n" % env_name)
    else:
        print("   -> kept %s.\n" % ("existing key" if existing else "blank"))

    # 2) Creator id -> config.json
    print("2) Creator id")
    print("   For a user, fill in your Roblox userId -- it must match the operating")
    print("   creator on the API key above. Find it on your profile URL")
    print("   (roblox.com/users/<userId>/profile).")
    ctype = input("   Creator type (user/group) [user]: ").strip().lower() or "user"
    label = "group id" if ctype.startswith("g") else "userId"
    cid = input("   %s (numeric): " % label).strip()
    if cid.isdigit():
        cfg["creator"] = {"groupId" if ctype.startswith("g") else "userId": int(cid)}
        _save_config(cfg)
        print("   -> creator set to %s.\n" % cfg["creator"])
    elif cid:
        print("   -> '%s' is not numeric; left creator unchanged.\n" % cid)
    else:
        print("   -> creator unchanged (%s).\n" % cfg.get("creator"))

    # 3) rojo (auto-install via rokit if missing)
    print("3) rojo (builds the binary .rbxm)")
    rojo = converter.find_rojo(cfg)
    if rojo:
        print("   found at %s\n" % rojo)
    else:
        try:
            rojo = _install_rojo(cfg)
        except Exception as e:  # noqa: BLE001 - surface a clear manual fallback
            print("   automatic install failed: %s" % e)
            print("   Install manually: https://github.com/rojo-rbx/rokit then")
            print("   `rokit add rojo-rbx/rojo --global`.\n")
        else:
            if rojo:
                print("   installed at %s\n" % rojo)
            else:
                print("   install ran but the binary wasn't found; open a new terminal")
                print("   and run `rpx where` to re-check.\n")

    # 4) Plugin lives on Roblox; the user installs it in Studio themselves.
    print("4) Studio plugin")
    print("   Install it from Roblox: %s\n" % server.PLUGIN_URL)

    print("Setup done. Run `rpx where` to check status, then `rpx` to start the server.")


# --------------------------------------------------------------------------- #
# rpx where
# --------------------------------------------------------------------------- #

def _row(ok: bool, label: str, detail: str) -> str:
    mark = "[ ok ]" if ok else "[ -- ]"
    return "%s %-18s %s" % (mark, label, detail)


def cmd_where() -> None:
    try:
        cfg = _load_config()
    except OSError:
        cfg = {}
    env_name = cfg.get("api_key_env", "ROBLOX_OPEN_CLOUD_KEY")
    key = server.read_secret(env_name)
    creator = cfg.get("creator") or {}
    rojo = converter.find_rojo(cfg)
    port = cfg.get("port", 34567)
    installed = _installed_plugin_path()

    print("KeyframeUploader -- status\n")
    print(_row(True, "server folder", SERVER_DIR))
    print(_row(os.path.exists(server.CONFIG_PATH), "config.json", server.CONFIG_PATH))
    print(_row(os.path.exists(installed), "plugin in Studio", installed))
    print(_row(True, "server url", "http://127.0.0.1:%s" % port))
    print(_row(bool(key), "api key (%s)" % env_name,
               "set (%d chars)" % len(key) if key else "NOT SET -- run `rpx setup`"))
    print(_row(bool(creator), "creator",
               str(creator) if creator else "NOT SET -- run `rpx setup`"))
    print(_row(bool(rojo), "rojo", rojo or "NOT found -- `aftman add rojo-rbx/rojo`"))


# --------------------------------------------------------------------------- #
# rpx help / run / dispatch
# --------------------------------------------------------------------------- #

def cmd_help() -> None:
    print(__doc__.strip())


def cmd_run() -> None:
    # Preflight: if essentials are missing, point the user at `rpx setup` rather than
    # letting server.main() fail mid-startup with a terse abort.
    try:
        cfg = _load_config()
    except OSError:
        cfg = {}
    env_name = cfg.get("api_key_env", "ROBLOX_OPEN_CLOUD_KEY")
    creator = cfg.get("creator") or {}
    missing = []
    if not server.read_secret(env_name):
        missing.append("Open Cloud API key")
    if not (creator.get("userId") or creator.get("groupId")):
        missing.append("creator userId/groupId")
    if not converter.find_rojo(cfg):
        missing.append("rojo")
    if missing:
        print("KeyframeUploader isn't set up yet -- missing:")
        for m in missing:
            print("  - " + m)
        print("\nRun `rpx setup` to fix this, then `rpx where` to confirm.")
        sys.exit(1)
    server.main()


def main() -> None:
    server.ensure_config()

    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if cmd in (None, "run", "start"):
        cmd_run()
    elif cmd == "setup":
        cmd_setup()
    elif cmd in ("where", "status", "doctor"):
        cmd_where()
    elif cmd in ("help", "-h", "--help"):
        cmd_help()
    else:
        print("Unknown command: %s\n" % cmd)
        cmd_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
