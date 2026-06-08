# Roblox SFX Upload System

Convert `.opus` sound effects to `.mp3`, then batch upload Roblox-compatible audio
files through Open Cloud and save the resulting audio asset IDs to CSV and JSON.

## Folder layout

```text
Roblox SFX Upload System/
  convert_opus_to_mp3.bat   double-click converter for .opus files
  upload_sfx.bat            double-click uploader
  upload_sfx.py             upload engine
  converted/                converted .mp3 files go here
  output/                   upload result CSV/JSON files go here
```

## API key

Create a Roblox Open Cloud API key in Creator Hub:

https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab

The key needs access to the **Assets API** with permission to create/write assets.
For group-owned audio, create the key from an account that has the correct role in the
group, then use `--group-id`.

Store the key locally in Windows:

```powershell
[Environment]::SetEnvironmentVariable("ROBLOX_OPEN_CLOUD_KEY", "PASTE_YOUR_KEY_HERE", "User")
```

Open a new terminal after setting it.

## Convert .opus files first

If your SFX are `.opus`, double-click:

```text
convert_opus_to_mp3.bat
```

Then:

1. Drag the folder with `.opus` files into the window.
2. Choose whether to include subfolders.
3. Use the generated `.mp3` files from the `converted` folder when uploading.

This requires FFmpeg. If it is missing, install it with:

```powershell
winget install Gyan.FFmpeg
```

## Upload a folder

Easiest option:

1. Double-click `upload_sfx.bat`.
2. Drag your SFX folder, or the `converted` folder, into the window, then press Enter.
3. Choose `1` for group-owned audio or `2` for user-owned audio.
4. Enter the group ID or user ID.
5. Choose whether to include subfolders.

Command-line option:

Group-owned audio:

```powershell
cd "C:\Eden AI\roblox_sound_uploader"
.\upload_sfx.bat "C:\Path\To\SFX Folder" --group-id YOUR_GROUP_ID
```

User-owned audio:

```powershell
cd "C:\Eden AI\roblox_sound_uploader"
.\upload_sfx.bat "C:\Path\To\SFX Folder" --user-id YOUR_USER_ID
```

Include subfolders:

```powershell
.\upload_sfx.bat "C:\Path\To\SFX Folder" --group-id YOUR_GROUP_ID --recursive
```

## Output

Each run writes files like these:

```text
output/sound_upload_results_YYYYMMDD_HHMMSS.csv
output/sound_upload_results_YYYYMMDD_HHMMSS.json
```

The CSV contains:

```text
file,name,status,assetId,error
```

## Supported files

- `.mp3`
- `.ogg`
- `.wav`
- `.flac`

The uploader skips files over 20 MB before upload. Roblox also enforces moderation,
duration, rights, and monthly upload limits.

## Notes

- The API key is never stored in this folder.
- The script uploads one file at a time so failures do not stop the whole batch.
- Audio asset updates are not supported by Roblox Open Cloud, so this tool creates new
  audio assets.
- `upload_sfx.bat` uses normal `python` if available, otherwise it falls back to the
  bundled Codex Python runtime on this machine.
