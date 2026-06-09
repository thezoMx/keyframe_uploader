"""Local server for the KeyframeUploader plugin.

Takes serialized KeyframeSequences over localhost HTTP, rebuilds each as .rbxmx,
uploads via the Open Cloud Assets API, returns the asset ids. Stdlib only.
"""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import rbxm
from . import converter
from . import opencloud


# Set this once you publish the plugin to Roblox; `rpx setup` shows it to users.
PLUGIN_URL = "https://create.roblox.com/store/asset/130692548377874/Roblox-Uploader"

DEFAULT_CONFIG = {
    "port": 34567,
    "api_key_env": "ROBLOX_OPEN_CLOUD_KEY",
    "creator": {"userId": 0},
    "asset_type": "Animation",
    "file_extension": "rbxm",
    "file_content_type": "model/x-rbxm",
    "rojo_path": "",
}


def data_dir() -> str:
    """Per-user folder that holds config.json."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base, "KeyframeUploader")
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_PATH = os.path.join(data_dir(), "config.json")


def ensure_config() -> None:
    """Write a default config.json on first run."""
    if os.path.exists(CONFIG_PATH):
        return
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
        f.write("\n")


def read_secret(env_name: str) -> str:
    """Read a secret from the environment.

    Falls back to the saved Windows User variable, so a terminal opened before the
    variable was set still finds it.
    """
    value = os.environ.get(env_name)
    if value:
        return value
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, env_name)
                return value or ""
        except OSError:
            return ""
    return ""


def write_secret(env_name: str, value: str) -> None:
    """Save a secret to the Windows User environment (HKCU\\Environment).

    Uses winreg, not setx (setx truncates at 1024 chars). Updates the live process too.
    """
    if os.name != "nt":
        raise RuntimeError("write_secret currently supports Windows only.")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, env_name, 0, winreg.REG_SZ, value)
    os.environ[env_name] = value


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    env_name = cfg.get("api_key_env", "ROBLOX_OPEN_CLOUD_KEY")
    cfg["api_key"] = read_secret(env_name)
    if not cfg["api_key"]:
        print('[ERROR] No API key found. Set the %s environment variable:' % env_name)
        print('        PowerShell:  [Environment]::SetEnvironmentVariable("%s","YOUR_KEY","User")' % env_name)
    creator = cfg.get("creator") or {}
    if not (creator.get("userId") or creator.get("groupId")):
        print("[WARN] No creator userId/groupId set in config.json -- uploads will fail.")
    cfg["_rojo_path"] = converter.find_rojo(cfg)
    if cfg["_rojo_path"]:
        print("[INFO] Using rojo at: %s" % cfg["_rojo_path"])
    else:
        print("[WARN] rojo not found -- needed to build binary .rbxm. "
              "Install it or set \"rojo_path\" in config.json.")
    return cfg


def process_batch(payload: dict, config: dict) -> dict:
    """Upload every animation in the payload, returning per-animation results."""
    animations = payload.get("animations", [])
    results = []
    for anim in animations:
        name = anim.get("name", "Animation")
        try:
            rbxmx_bytes = rbxm.build_rbxmx(anim)
            file_bytes = converter.rbxmx_to_rbxm(rbxmx_bytes, config.get("_rojo_path"))
            asset_id = opencloud.upload_asset(file_bytes, name, config)
            results.append({"name": name, "assetId": asset_id})
            print("[OK] %s -> %s" % (name, asset_id))
        except Exception as e:  # noqa: BLE001 - report any failure per-animation
            results.append({"name": name, "error": str(e)})
            print("[FAIL] %s -> %s" % (name, e))
    return {"results": results}


class Handler(BaseHTTPRequestHandler):
    config = None  # injected before serving

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_json(200, {"status": "ok", "service": "KeyframeUploader"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/upload":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            self._send_json(400, {"error": "bad request body: %s" % e})
            return
        try:
            result = process_batch(payload, self.config)
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        # Quieter, single-line logging.
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    config = load_config()

    # Fail fast on missing essentials instead of a confusing 401 mid-upload.
    creator = config.get("creator") or {}
    problems = []
    if not config["api_key"]:
        problems.append("missing API key (set the %s env var)"
                        % config.get("api_key_env", "ROBLOX_OPEN_CLOUD_KEY"))
    if not (creator.get("userId") or creator.get("groupId")):
        problems.append("missing creator userId/groupId in config.json")
    if not config["_rojo_path"]:
        problems.append("rojo not found (needed to build .rbxm)")
    if problems:
        print("\n[ABORT] Cannot start the server:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    Handler.config = config
    port = int(config.get("port", 34567))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("KeyframeUploader server listening on http://127.0.0.1:%d" % port)
    print("Asset type: %s | creator: %s" % (config.get("asset_type"), config.get("creator")))
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
