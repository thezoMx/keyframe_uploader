"""Batch upload Roblox audio assets from a local folder.

Reads the Roblox Open Cloud API key from ROBLOX_OPEN_CLOUD_KEY by default.
Uploads .mp3, .ogg, .wav, and .flac files, then writes CSV and JSON results.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path


ASSETS_URL = "https://apis.roblox.com/assets/v1/assets"
OPERATIONS_URL = "https://apis.roblox.com/assets/v1/operations/"
SUPPORTED_EXTENSIONS = {
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class UploadError(Exception):
    pass


def read_secret(env_name: str) -> str:
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


def clean_display_name(path: Path) -> str:
    name = path.stem.strip()
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name[:50] or "Sound Effect"


def iter_audio_files(folder: Path, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    files = [
        p
        for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda p: str(p).lower())


def build_multipart(request_json: dict, file_bytes: bytes, filename: str, content_type: str):
    boundary = "----RobloxSoundUploader" + uuid.uuid4().hex
    crlf = "\r\n"
    request_part = (
        "--" + boundary + crlf
        + 'Content-Disposition: form-data; name="request"' + crlf
        + "Content-Type: application/json" + crlf
        + crlf
        + json.dumps(request_json)
        + crlf
    )
    file_part = (
        "--" + boundary + crlf
        + 'Content-Disposition: form-data; name="fileContent"; filename="%s"' % filename + crlf
        + "Content-Type: %s" % content_type + crlf
        + crlf
    )
    tail = crlf + "--" + boundary + "--" + crlf
    body = request_part.encode("utf-8") + file_part.encode("utf-8") + file_bytes + tail.encode("utf-8")
    return body, "multipart/form-data; boundary=" + boundary


def request_json(url: str, api_key: str, method: str = "GET", body: bytes | None = None, content_type: str | None = None):
    headers = {"x-api-key": api_key}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise UploadError("HTTP %s: %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise UploadError("Network error: %s" % e.reason)


def poll_operation(operation_id: str, api_key: str, timeout: float, interval: float) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, data = request_json(OPERATIONS_URL + operation_id, api_key)
        if data.get("done"):
            if data.get("error"):
                raise UploadError("Operation failed: %s" % json.dumps(data["error"]))
            response = data.get("response") or {}
            asset_id = response.get("assetId")
            if asset_id:
                return str(asset_id)
            raise UploadError("Operation finished without assetId: %s" % json.dumps(data))
        time.sleep(interval)
    raise UploadError("Timed out waiting for operation %s" % operation_id)


def upload_audio(path: Path, api_key: str, creator: dict, description: str, timeout: float, interval: float) -> str:
    size = path.stat().st_size
    if size > MAX_AUDIO_BYTES:
        raise UploadError("File is larger than 20 MB")

    content_type = SUPPORTED_EXTENSIONS.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
    if not content_type:
        raise UploadError("Unsupported audio type")

    request_payload = {
        "assetType": "Audio",
        "displayName": clean_display_name(path),
        "description": description,
        "creationContext": {
            "creator": creator,
            "expectedPrice": 0,
        },
    }
    file_bytes = path.read_bytes()
    body, multipart_type = build_multipart(request_payload, file_bytes, path.name, content_type)
    _, data = request_json(ASSETS_URL, api_key, method="POST", body=body, content_type=multipart_type)

    if data.get("done") and data.get("response", {}).get("assetId"):
        return str(data["response"]["assetId"])

    operation_id = data.get("operationId")
    if not operation_id and isinstance(data.get("path"), str):
        operation_id = data["path"].split("/")[-1]
    if not operation_id:
        raise UploadError("Upload accepted but no operation id was returned: %s" % json.dumps(data))
    return poll_operation(operation_id, api_key, timeout, interval)


def write_results(results: list[dict], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / ("sound_upload_results_%s.csv" % stamp)
    json_path = output_dir / ("sound_upload_results_%s.json" % stamp)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "name", "status", "assetId", "error"])
        writer.writeheader()
        writer.writerows(results)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    return csv_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a folder of SFX to Roblox audio assets.")
    parser.add_argument("folder", help="Folder containing .mp3, .ogg, .wav, or .flac files.")
    creator = parser.add_mutually_exclusive_group(required=True)
    creator.add_argument("--group-id", type=int, help="Roblox group ID that will own the audio assets.")
    creator.add_argument("--user-id", type=int, help="Roblox user ID that will own the audio assets.")
    parser.add_argument("--env", default="ROBLOX_OPEN_CLOUD_KEY", help="Environment variable containing the API key.")
    parser.add_argument("--description", default="Uploaded by Roblox Sound Uploader", help="Asset description.")
    parser.add_argument("--recursive", action="store_true", help="Include audio files in subfolders.")
    parser.add_argument("--output", default="output", help="Folder where CSV/JSON result files are written.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Seconds to wait for each upload operation.")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between operation status checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print("Folder not found: %s" % folder, file=sys.stderr)
        return 2

    api_key = read_secret(args.env)
    if not api_key:
        print("Missing API key. Set %s first." % args.env, file=sys.stderr)
        return 2

    creator = {"groupId": args.group_id} if args.group_id else {"userId": args.user_id}
    files = iter_audio_files(folder, args.recursive)
    if not files:
        print("No supported audio files found in %s" % folder)
        return 0

    results = []
    print("Found %d audio file(s). Uploading..." % len(files))
    for index, path in enumerate(files, start=1):
        row = {
            "file": str(path),
            "name": clean_display_name(path),
            "status": "error",
            "assetId": "",
            "error": "",
        }
        try:
            print("[%d/%d] %s" % (index, len(files), path.name))
            row["assetId"] = upload_audio(path, api_key, creator, args.description, args.timeout, args.interval)
            row["status"] = "ok"
            print("      -> %s" % row["assetId"])
        except Exception as e:  # noqa: BLE001 - continue with the rest of the batch
            row["error"] = str(e)
            print("      !! %s" % e)
        results.append(row)

    csv_path, json_path = write_results(results, Path(args.output).resolve())
    ok_count = sum(1 for r in results if r["status"] == "ok")
    print("\nDone. Uploaded %d/%d file(s)." % (ok_count, len(results)))
    print("CSV:  %s" % csv_path)
    print("JSON: %s" % json_path)
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
