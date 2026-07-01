"""Replicate API 轻量客户端（无需安装 replicate 包）"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def _request(method: str, url: str, token: str, data: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Replicate API 错误 ({e.code}): {detail}") from e


def upload_file(path: Path, token: str) -> str:
    """上传本地图片，返回 Replicate 可访问的 URL。"""
    import mimetypes

    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    boundary = "----DollWorldwideBoundary"
    file_bytes = path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="content"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        "https://api.replicate.com/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"上传图片失败 ({e.code}): {detail}") from e

    urls = payload.get("urls") or {}
    return urls.get("get") or payload.get("url") or ""


def run_model(
    model: str,
    input_data: dict,
    token: str,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
) -> str | list:
    """运行 Replicate 模型，返回 output（通常是图片 URL）。"""
    url = f"https://api.replicate.com/v1/models/{model}/predictions"
    pred = _request("POST", url, token, {"input": input_data})
    pred_id = pred["id"]
    status_url = f"https://api.replicate.com/v1/predictions/{pred_id}"

    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise SystemExit(f"Replicate 超时 ({timeout}s): {pred_id}")
        result = _request("GET", status_url, token)
        status = result.get("status")
        if status == "succeeded":
            return result.get("output")
        if status in ("failed", "canceled"):
            raise SystemExit(f"Replicate 失败: {result.get('error', status)}")
        time.sleep(poll_interval)


def download_url(url: str, dest: Path) -> None:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
