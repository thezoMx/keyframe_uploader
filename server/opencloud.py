"""Open Cloud Assets API client (stdlib only).

Uploads a single asset file (e.g. a rebuilt KeyframeSequence .rbxmx) to Roblox via
the Open Cloud Assets API and polls the long-running operation until the asset id is
available.

Reference: POST https://apis.roblox.com/assets/v1/assets  (multipart/form-data)
           GET  https://apis.roblox.com/assets/v1/operations/{operationId}
The exact assetType string and file content-type are passed in from config so they can
be adjusted without touching code if Roblox changes them.
"""

import json
import time
import uuid
import urllib.request
import urllib.error

ASSETS_URL = "https://apis.roblox.com/assets/v1/assets"
OPERATIONS_URL = "https://apis.roblox.com/assets/v1/operations/"


class UploadError(Exception):
    pass


def _build_multipart(request_json: dict, file_bytes: bytes, filename: str,
                     file_content_type: str):
    """Construct a multipart/form-data body with `request` (JSON) and `fileContent` parts."""
    boundary = "----KeyframeUploader" + uuid.uuid4().hex
    crlf = "\r\n"
    parts = []

    parts.append("--" + boundary)
    parts.append('Content-Disposition: form-data; name="request"')
    parts.append("Content-Type: application/json")
    parts.append("")
    parts.append(json.dumps(request_json))

    head = crlf.join(parts) + crlf
    file_head = (
        "--" + boundary + crlf
        + 'Content-Disposition: form-data; name="fileContent"; filename="%s"' % filename + crlf
        + "Content-Type: %s" % file_content_type + crlf
        + crlf
    )
    tail = crlf + "--" + boundary + "--" + crlf

    body = head.encode("utf-8") + file_head.encode("utf-8") + file_bytes + tail.encode("utf-8")
    content_type = "multipart/form-data; boundary=" + boundary
    return body, content_type


def _request(url: str, api_key: str, method: str = "GET", body: bytes = None,
             content_type: str = None):
    headers = {"x-api-key": api_key}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise UploadError("HTTP %s from %s: %s" % (e.code, url, detail))
    except urllib.error.URLError as e:
        raise UploadError("Network error contacting %s: %s" % (url, e.reason))


def upload_asset(file_bytes: bytes, display_name: str, config: dict,
                 description: str = "Uploaded by KeyframeUploader",
                 poll_timeout: float = 60.0, poll_interval: float = 1.5) -> str:
    """Upload one file and return the resulting assetId (as a string).

    Raises UploadError on failure.
    """
    api_key = config["api_key"]
    request_json = {
        "assetType": config.get("asset_type", "Animation"),
        "displayName": display_name,
        "description": description,
        "creationContext": {"creator": config["creator"]},
    }
    filename = display_name + "." + config.get("file_extension", "rbxmx")
    body, content_type = _build_multipart(
        request_json, file_bytes, filename, config.get("file_content_type", "model/x-rbxmx")
    )

    status, data = _request(ASSETS_URL, api_key, method="POST", body=body,
                            content_type=content_type)

    # The create call returns a long-running operation.
    operation_id = data.get("operationId")
    if not operation_id and isinstance(data.get("path"), str):
        operation_id = data["path"].split("/")[-1]
    if data.get("done") and data.get("response", {}).get("assetId"):
        return str(data["response"]["assetId"])
    if not operation_id:
        raise UploadError("Upload accepted but no operationId returned: %s" % json.dumps(data))

    return _poll_operation(operation_id, api_key, poll_timeout, poll_interval)


def _poll_operation(operation_id: str, api_key: str, poll_timeout: float,
                    poll_interval: float) -> str:
    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        status, data = _request(OPERATIONS_URL + operation_id, api_key)
        if data.get("done"):
            response = data.get("response") or {}
            asset_id = response.get("assetId")
            if asset_id:
                return str(asset_id)
            raise UploadError("Operation done but no assetId: %s" % json.dumps(data))
        time.sleep(poll_interval)
    raise UploadError("Timed out waiting for upload operation %s" % operation_id)
