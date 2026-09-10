"""
Shared low-level client for the ModelRunner queue API.

One hosted catalog addressed by "owner/alias" — no per-model deployment. Used by
both image_modelrunner and video_modelrunner.

Measured against the live API, because the docs do not say any of this:
  1. The model id is in the URL PATH and the body is the input object itself —
     there is no {"input": ...} envelope and no "model" body field.
  2. A job reports IN_QUEUE for its whole cold start and may never report
     IN_PROGRESS. Only COMPLETED / FAILED / CANCELLED are terminal.
  3. The per-model /status url never carries the output. Read the result from
     GET /requests/{id}, which needs no model id.
  4. `output` is a list of urls for image models and a bare url string for most
     video models. Normalize both.
  5. Unknown input fields are forwarded to the model rather than rejected here,
     so filter against the model's public schema before spending anything.
"""
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests

from config import Config

logger = logging.getLogger(__name__)

QUEUE_BASE = "https://queue.modelrunner.run"
CATALOG_BASE = "https://modelrunner.run"

_SCHEMA_CACHE: Dict[str, set] = {}


class ModelRunnerError(RuntimeError):
    pass


def _base_url() -> str:
    return (Config.MODELRUNNER_BASE_URL or QUEUE_BASE).rstrip("/")


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    key = api_key or Config.MODELRUNNER_API_KEY
    if not key:
        raise ModelRunnerError(
            "ModelRunner api_key is not set (api_providers.modelrunner.api_key)."
        )
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def _proxies():
    return Config.requests_proxies("modelrunner")


def input_fields(model: str) -> set:
    """Field names the model declares, from the PUBLIC catalog (no key needed).

    An empty set means the schema was unavailable and is treated as "do not
    filter" by filter_params.
    """
    if model in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[model]
    fields: set = set()
    try:
        r = requests.get(f"{CATALOG_BASE}/models/{model}", timeout=20, proxies=_proxies())
        if r.status_code == 200:
            schemas = ((r.json().get("schema") or {}).get("components") or {}).get("schemas") or {}
            fields = set((schemas.get("Input") or {}).get("properties") or {})
    except requests.exceptions.RequestException as exc:
        logger.debug("ModelRunner schema fetch failed for %s: %s", model, exc)
    _SCHEMA_CACHE[model] = fields
    return fields


def filter_params(model: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Drop params the model does not declare, logging what went."""
    declared = input_fields(model)
    if not declared:
        return dict(params)
    dropped = sorted(k for k in params if k not in declared)
    if dropped:
        logger.info("ModelRunner %s: dropping undeclared param(s) %s", model, ", ".join(dropped))
    return {k: v for k, v in params.items() if k in declared}


def submit(model: str, params: Dict[str, Any], api_key: Optional[str] = None) -> str:
    """Submit a job; return the request id."""
    body = filter_params(model, params)
    r = requests.post(f"{_base_url()}/{model}", json=body, headers=_headers(api_key),
                      timeout=60, proxies=_proxies())
    if r.status_code not in (200, 201):
        raise ModelRunnerError(f"submit {model} failed (HTTP {r.status_code}): {r.text[:300]}")
    request_id = r.json().get("request_id")
    if not request_id:
        raise ModelRunnerError(f"submit {model} returned no request_id: {r.text[:200]}")
    return request_id


def first_url(output: Any) -> Optional[str]:
    """Normalize `output` — list of urls, bare url string, or nothing (note 4)."""
    if isinstance(output, list):
        return output[0] if output else None
    if isinstance(output, str):
        return output or None
    return None


def wait(request_id: str, timeout: int = 900, poll_interval: int = 5,
         api_key: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """Poll until terminal; return (output_url, full record).

    Reads GET /requests/{id} rather than the per-model status url, which never
    carries the output (note 3).
    """
    deadline = time.time() + timeout
    headers = _headers(api_key)
    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            r = requests.get(f"{_base_url()}/requests/{request_id}", headers=headers,
                             timeout=30, proxies=_proxies())
        except requests.exceptions.RequestException as exc:
            logger.debug("ModelRunner poll error (retrying): %s", exc)
            continue
        if r.status_code != 200:
            continue                      # transient; keep polling until the deadline
        record = r.json()
        status = record.get("status")
        if status == "COMPLETED":
            url = first_url(record.get("output"))
            if not url:
                raise ModelRunnerError(f"request {request_id} completed with no output")
            return url, record
        if status in ("FAILED", "CANCELLED"):
            raise ModelRunnerError(
                f"request {request_id} {str(status).lower()}: {record.get('error') or status}")
        # IN_QUEUE covers the whole cold start; there may be no IN_PROGRESS (note 2).
    raise ModelRunnerError(f"request {request_id} timed out after {timeout}s")


def run(model: str, params: Dict[str, Any], timeout: int = 900,
        poll_interval: int = 5, api_key: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """submit + wait."""
    return wait(submit(model, params, api_key=api_key), timeout=timeout,
                poll_interval=poll_interval, api_key=api_key)


def upload(path: str, api_key: Optional[str] = None) -> str:
    """Upload a local file and return its public url.

    Hosted models take urls, while this codebase works in local paths, so every
    image input has to go through here first. Two steps: ask for a presigned PUT
    url, then send the bytes straight to storage.
    """
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    content_type = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".mp4": "video/mp4", ".mp3": "audio/mpeg",
        ".wav": "audio/wav", ".m4a": "audio/mp4",
    }.get(ext, "application/octet-stream")

    r = requests.post(f"{_base_url()}/storage/upload/initiate",
                      json={"file_name": name, "content_type": content_type},
                      headers=_headers(api_key), timeout=60, proxies=_proxies())
    if r.status_code != 200:
        raise ModelRunnerError(f"upload initiate failed (HTTP {r.status_code}): {r.text[:200]}")
    data = r.json()
    put_url, file_url = data.get("upload_url"), data.get("file_url")
    if not put_url or not file_url:
        raise ModelRunnerError(f"upload initiate returned no url: {str(data)[:200]}")

    with open(path, "rb") as fh:
        put = requests.put(put_url, data=fh, headers={"Content-Type": content_type},
                           timeout=300, proxies=_proxies())
    if put.status_code != 200:
        raise ModelRunnerError(f"upload PUT failed (HTTP {put.status_code})")
    return file_url


def to_url(path_or_url: str, api_key: Optional[str] = None) -> str:
    """Pass a url through; upload a local path."""
    if str(path_or_url).startswith(("http://", "https://")):
        return path_or_url
    return upload(path_or_url, api_key=api_key)


def download(url: str, dest: str) -> str:
    """Stream a generated asset to `dest`."""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with requests.get(url, stream=True, timeout=300, proxies=_proxies()) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    fh.write(chunk)
    return dest
