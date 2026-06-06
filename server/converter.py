"""Convert a reconstructed KeyframeSequence .rbxmx (XML) into a binary .rbxm.

Open Cloud's animation upload only accepts the *binary* .rbxm format -- it rejects
.rbxmx with "Creating Animation from a model/x-rbxmx file is not supported yet". We build
the XML in rbxm.py, then use `rojo build` to emit a proper binary .rbxm that Studio-style
processing accepts.

rojo is located automatically: explicit config path -> rokit/aftman tool-storage ->
rokit bin link -> PATH.
"""

import glob
import os
import shutil
import subprocess
import tempfile


def find_rojo(config: dict) -> str:
    """Return a path to a runnable rojo executable, or None if not found.

    Prefers the real rokit/aftman tool-storage binary over a PATH trampoline, because the
    trampoline refuses to run unless a manifest lists the tool.
    """
    explicit = config.get("rojo_path")
    if explicit and os.path.exists(explicit):
        return explicit

    home = os.path.expanduser("~")

    # rokit (preferred) and aftman keep the real binary under tool-storage.
    for manager in (".rokit", ".aftman"):
        pattern = os.path.join(home, manager, "tool-storage", "rojo-rbx", "rojo", "*", "rojo*")
        matches = [p for p in glob.glob(pattern) if p.lower().endswith((".exe", "rojo"))]
        if matches:
            # newest version folder wins
            return sorted(matches)[-1]

    # rokit's global bin link works too, since the global manifest lists rojo.
    for name in ("rojo.exe", "rojo"):
        link = os.path.join(home, ".rokit", "bin", name)
        if os.path.exists(link):
            return link

    on_path = shutil.which("rojo")
    if on_path:
        return on_path
    return None


def rbxmx_to_rbxm(rbxmx_bytes: bytes, rojo_path: str) -> bytes:
    """Build a binary .rbxm from the given .rbxmx bytes using rojo."""
    if not rojo_path:
        raise RuntimeError(
            "rojo not found. Install it (e.g. `aftman add rojo-rbx/rojo`) or set "
            '"rojo_path" in config.json.'
        )
    workdir = tempfile.mkdtemp(prefix="ku_conv_")
    try:
        with open(os.path.join(workdir, "model.rbxmx"), "wb") as f:
            f.write(rbxmx_bytes)
        # BOM-free project file -- rojo fails to find a BOM-prefixed project.
        with open(os.path.join(workdir, "default.project.json"), "w", encoding="utf-8") as f:
            f.write('{ "name": "KeyframeUpload", "tree": { "$path": "model.rbxmx" } }')

        out_path = os.path.join(workdir, "model.rbxm")
        result = subprocess.run(
            [rojo_path, "build", ".", "--output", "model.rbxm"],
            cwd=workdir, capture_output=True, text=True,
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            raise RuntimeError("rojo build failed: " + (result.stderr or result.stdout or "?"))
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
