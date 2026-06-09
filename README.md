# KeyframeUploader

Batch-upload selected `KeyframeSequence` animations to Roblox and auto-place the resulting
`Animation` instances into a folder structure you choose.

```
Studio plugin  ──localhost HTTP──►  Python server  ──Open Cloud──►  Roblox
      ▲                                                                 │
      └──────────────── asset ids returned in the response ◄───────────┘
      │
      └─► creates Animation instances at <root>/<destination path>
```

A Studio plugin can't write files or upload a raw `KeyframeSequence`. So the plugin
serializes each selected animation, sends it to a small local server, and that server
rebuilds it as XML, converts it to a **binary `.rbxm`** with `rojo`, and uploads it
through the **Open Cloud Assets API**.

> Open Cloud animation upload requires the *binary* `.rbxm` format — it rejects XML
> `.rbxmx` ("Creating Animation from a model/x-rbxmx file is not supported yet"). The
> server uses `rojo build` to produce the binary form. `AssetService:CreateAssetAsync`
> (a pure-plugin alternative) is not enabled by Roblox yet.

---

## Quick start with the `rpx` command

Install the command once, then everything is driven by `rpx`:

```powershell
pip install keyframe-uploader   # creates the `rpx` command on PATH
rpx setup                       # API key, creator id, auto-install rojo, install the plugin
rpx                             # run the server (leave it running while you upload)
```

(To work from a clone instead: `cd server` then `pip install -e .`.)

| Command | What it does |
| --- | --- |
| `rpx` | Run the server. If anything is unconfigured it tells you to run `rpx setup`. |
| `rpx setup` | Interactive: store the API key (env var), set your creator id, **auto-install rojo** (via rokit) if it's missing, and install the plugin into Studio. |
| `rpx where` | Status/"doctor": shows every path and whether the key, creator, rojo, and plugin are configured. |
| `rpx help` | Show usage. |

`rpx setup` links you straight to the API-key page
(<https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab>) and, if rojo
isn't already installed, downloads [rokit](https://github.com/rojo-rbx/rokit) and runs
`rokit add rojo-rbx/rojo --global` for you — no manual toolchain setup needed.

> If `pip` warns that its `Scripts` folder isn't on `PATH`, add that folder to your
> User `PATH` (one time) so `rpx` is typeable from any terminal. `rpx where` confirms
> everything is wired up.

The sections below explain the same setup done manually (useful for `rpx where` red flags
or running without installing the command).

---

## 1. Prerequisites

- **Python 3.8+** installed (needed to run the server).
- **rojo** (used to build the binary `.rbxm`). You don't have to install it yourself —
  `rpx setup` installs it via [rokit](https://github.com/rojo-rbx/rokit) if it's missing.
  The server auto-discovers rojo from rokit's (or aftman's) tool-storage or `PATH`;
  otherwise set `rojo_path` in `config.json`.
- An **Open Cloud API key** with the `asset:write` (Assets / write) scope. Create one at
  <https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab>:
  1. *Create API Key*.
  2. Add the **Assets** API system, enable read & write.
  3. Set the operating creator to **your user** (or your **group**).
  4. Copy the key.

## 2. Configure the server

**The API key is a secret and is never stored in `config.json`.** It is read from an
environment variable instead. Set it once (PowerShell, User scope so it persists):

```powershell
[Environment]::SetEnvironmentVariable("ROBLOX_OPEN_CLOUD_KEY", "YOUR_OPEN_CLOUD_API_KEY", "User")
```

Normally env vars are only seen by processes started *after* you set them, so you'd open a
new terminal. On Windows the server also reads the saved value directly (from the registry),
so it works even from a terminal that was already open.

Everything non-secret lives in a per-user `config.json`, created automatically on first run
(and populated by `rpx setup`). It lives in your platform's app-data folder — on Windows that's
`%LOCALAPPDATA%\KeyframeUploader\config.json`. `rpx where` prints the exact path. Its contents:

```json
{
  "port": 34567,
  "api_key_env": "ROBLOX_OPEN_CLOUD_KEY",
  "creator": { "userId": 123456789 },
  "asset_type": "Animation",
  "file_extension": "rbxm",
  "file_content_type": "model/x-rbxm",
  "rojo_path": ""
}
```

- `api_key_env` — the **name** of the environment variable holding the key (not the key
  itself). Change it only if you want a different variable name.
- For a **group**, replace `"creator"` with `{ "groupId": 987654321 }`.
- `asset_type` / `file_extension` / `file_content_type` are exposed in case Roblox changes
  the expected values — the defaults match the Open Cloud animation-upload contract
  (binary `.rbxm`).
- `rojo_path` — leave `""` to auto-discover; set an explicit path to a `rojo` executable
  if discovery fails.

## 3. Run the server

```powershell
rpx                 # or:  python -m keyframe_uploader
```

You should see `KeyframeUploader server listening on http://127.0.0.1:34567`.

## 4. Install the plugin

- In Studio, open `plugin/KeyframeUploaderPlugin.server.lua` as a `Script`, then
  right-click it → **Save as Local Plugin**.
- A **KeyframeUploader** button appears in the **Plugins** tab. Click it to open the panel.

## 5. Use it

1. Start the server.
2. In the panel set:
   - **Server URL** — default `http://127.0.0.1:34567`.
   - **Root** — a service (`ReplicatedStorage`) or a top-level instance name.
   - **Destination path** — e.g. `Sword/Attacks`. Leave blank to use the fallback
     `ReplicatedStorage/UPLOADED_ANIMATIONS`.
3. Select one or more `KeyframeSequence`s in the Explorer.
4. Click **Upload selected animations**.

The plugin creates any missing folders along the path and adds an `Animation` (named after
the source KeyframeSequence) with its `AnimationId` set to the uploaded asset. The whole
build is a single undo step.

## Notes

- Uploaded animations may be **in moderation** briefly, but the `AnimationId` works for you
  (the owner) immediately in Studio.
- Re-uploading an animation with a name that already exists at the destination **updates**
  that Animation's `AnimationId` rather than creating a duplicate.
- The server holds your API key; the plugin never sees it.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Could not reach the server" | Server isn't running, or the URL/port is wrong. |
| `HTTP 401/403` in the panel log | Bad/expired API key, missing `asset:write` scope, or the `ROBLOX_OPEN_CLOUD_KEY` env var isn't set in the terminal that launched the server. |
| `No API key` warning at startup | Set `ROBLOX_OPEN_CLOUD_KEY` and restart the terminal/server. |
| `HTTP 400 ... assetType` | Adjust `asset_type` / `file_content_type` in `config.json`. |
| `HTTP 400 ... model/x-rbxmx ... not supported` | Old config — set `file_extension`=`rbxm`, `file_content_type`=`model/x-rbxm`. |
| `rojo not found` / `rojo build failed` | Install rojo (`aftman add rojo-rbx/rojo`) or set `rojo_path` in `config.json`. |
| `Unknown CreatorType Invalid` | `creator.userId` is `0`/missing — set your real user (or group) id. |

## Files

```
server/
  pyproject.toml                  package metadata; defines the `rpx` command
  LICENSE
  README.md
  keyframe_uploader/
    rpx.py         `rpx` CLI: run / setup / where (entry point)
    server.py      local HTTP server (POST /upload)
    rbxm.py        rebuild KeyframeSequence -> .rbxmx (XML)
    converter.py   convert .rbxmx -> binary .rbxm via rojo
    opencloud.py   Open Cloud Assets API upload + operation polling
plugin/
  KeyframeUploaderPlugin.server.lua   the Studio plugin (single file)
```
