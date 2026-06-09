# KeyframeUploader

Batch-upload selected `KeyframeSequence` animations to Roblox and drop the resulting
`Animation` instances into a folder structure you pick.

A Studio plugin can't write files or upload a raw `KeyframeSequence`. So the plugin
serializes each selected animation and sends it to a local server. The server rebuilds it
as XML, converts that to a binary `.rbxm` with `rojo`, and uploads it through the Open
Cloud Assets API.

---

## Quick start with `rpx`

Install it once; `rpx` drives the rest:

```powershell
pip install keyframe-uploader   # creates the `rpx` command on PATH
rpx setup                       # API key, creator id, auto-install rojo, install the plugin
rpx                             # run the server (leave it running while you upload)
```

Working from a clone instead? `cd server` then `pip install -e .`.

| Command | What it does |
| --- | --- |
| `rpx` | Run the server. If anything is unconfigured it points you to `rpx setup`. |
| `rpx setup` | Interactive: store the API key (env var), set your creator id, auto-install rojo (via rokit) if it's missing, and link you to the plugin. |
| `rpx where` | Status check: shows every path and whether the key, creator, rojo, and plugin are configured. |
| `rpx help` | Show usage. |

`rpx setup` opens the API-key page
(<https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab>). If rojo is
missing, it downloads [rokit](https://github.com/rojo-rbx/rokit) and runs
`rokit add rojo-rbx/rojo --global` for you.

> If `pip` warns that its `Scripts` folder isn't on `PATH`, add that folder to your User
> `PATH` once so you can type `rpx` from any terminal. `rpx where` confirms the setup.

Prefer to do it by hand? The manual steps below cover the same ground, and they help when
`rpx where` flags something.

---

## 1. Prerequisites

- **Python 3.8+** to run the server.
- **rojo**, which builds the binary `.rbxm`. You don't install it yourself: `rpx setup`
  fetches it via [rokit](https://github.com/rojo-rbx/rokit) if it's missing. The server
  finds rojo in rokit's (or aftman's) tool-storage or on `PATH`; otherwise set `rojo_path`
  in `config.json`.
- An **Open Cloud API key** with the `asset:write` (Assets / write) scope. Create one at
  <https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab>:
  1. *Create API Key*.
  2. Add the **Assets** API system, enable read and write.
  3. Set the operating creator to your user (or your group).
  4. Copy the key.

## 2. Configure the server

The API key is a secret, so it never goes in `config.json`. The server reads it from an
environment variable. Set it once (PowerShell, User scope so it persists):

```powershell
[Environment]::SetEnvironmentVariable("ROBLOX_OPEN_CLOUD_KEY", "YOUR_OPEN_CLOUD_API_KEY", "User")
```

A process only sees env vars that existed before it started, so you'd normally open a new
terminal. On Windows the server also reads the saved value straight from the registry, so an
already-open terminal works too.

Everything non-secret lives in a per-user `config.json`, written on first run and filled in
by `rpx setup`. On Windows it sits at `%LOCALAPPDATA%\KeyframeUploader\config.json`, and
`rpx where` prints the exact path. Its contents:

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

- `api_key_env`: the **name** of the environment variable holding the key, not the key
  itself. Change it only if you want a different variable name.
- For a **group**, replace `"creator"` with `{ "groupId": 987654321 }`.
- `asset_type` / `file_extension` / `file_content_type` cover the case where Roblox changes
  the expected values. The defaults match the Open Cloud animation-upload contract
  (binary `.rbxm`).
- `rojo_path`: leave `""` to auto-discover, or set a path to a `rojo` executable if
  discovery fails.

## 3. Run the server

```powershell
rpx                 # or:  python -m keyframe_uploader
```

You should see `KeyframeUploader server listening on http://127.0.0.1:34567`.

## 4. Install the plugin

- In Studio, open `plugin/KeyframeUploaderPlugin.server.lua` as a `Script`, then right-click
  it and pick **Save as Local Plugin**.
- A **KeyframeUploader** button appears in the **Plugins** tab. Click it to open the panel.

## 5. Use it

1. Start the server.
2. In the panel set:
   - **Server URL**: default `http://127.0.0.1:34567`.
   - **Root**: a service (`ReplicatedStorage`) or a top-level instance name.
   - **Destination path**: e.g. `Sword/Attacks`. Leave blank to use the fallback
     `ReplicatedStorage/UPLOADED_ANIMATIONS`.
3. Select one or more `KeyframeSequence`s in the Explorer.
4. Click **Upload selected animations**.

The plugin creates any missing folders along the path and adds an `Animation` (named after
the source KeyframeSequence) with its `AnimationId` set to the uploaded asset. The whole
build collapses into one undo step.

## Notes

- A freshly uploaded animation may sit in moderation briefly, but its `AnimationId` works for
  you (the owner) right away in Studio.
- Re-upload an animation whose name already exists at the destination and the plugin updates
  that Animation's `AnimationId` instead of creating a duplicate.
- The server holds your API key; the plugin never sees it.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Could not reach the server" | Server isn't running, or the URL/port is wrong. |
| `HTTP 401/403` in the panel log | Bad/expired API key, missing `asset:write` scope, or the `ROBLOX_OPEN_CLOUD_KEY` env var isn't set in the terminal that launched the server. |
| `No API key` warning at startup | Set `ROBLOX_OPEN_CLOUD_KEY` and restart the terminal/server. |
| `HTTP 400 ... assetType` | Adjust `asset_type` / `file_content_type` in `config.json`. |
| `HTTP 400 ... model/x-rbxmx ... not supported` | Old config: set `file_extension`=`rbxm`, `file_content_type`=`model/x-rbxm`. |
| `rojo not found` / `rojo build failed` | Install rojo (`aftman add rojo-rbx/rojo`) or set `rojo_path` in `config.json`. |
| `Unknown CreatorType Invalid` | `creator.userId` is `0` or missing: set your real user (or group) id. |

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
