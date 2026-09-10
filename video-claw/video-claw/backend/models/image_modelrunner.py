"""ModelRunner image generation client (text-to-image and image-to-image)."""
import logging
import os
import uuid
from math import gcd
from typing import List, Optional

try:
    from models import modelrunner_api as mr
except ImportError:
    from . import modelrunner_api as mr

logger = logging.getLogger(__name__)


class ModelRunnerImageClient:
    """Generates images through a hosted catalog model.

    Field names differ across this catalog: text-to-image models take one
    `image_size` rather than a width and height, and reference images are
    `image_url` on some models and `image_urls` on others. Rather than branch per
    model, every plausible spelling is offered and modelrunner_api.filter_params
    drops the ones the model does not declare — the schema read is free and
    unauthenticated, so this costs nothing and cannot send an unknown field.

    `image_size` needs one extra step, because models in this catalog disagree
    on how it is spelled: some take an object {width, height}, others reject
    that and require a preset string ("must be string"). The object is tried
    FIRST because it carries the exact size the caller asked for; the preset is
    only an approximation of it. Trying is safe and free — input validation
    happens BEFORE the request is created, so a rejected encoding bills nothing
    — and the encoding that worked is remembered per model so the probe happens
    at most once per process.
    """

    #: model id -> "object" | "preset", learned on first use
    _ENCODING: dict = {}

    #: aspects this catalog spells as a preset, "<w>_<h>_<res>"
    _PRESET_ASPECTS = {
        (1, 1): "1_1", (16, 9): "16_9", (9, 16): "9_16", (4, 3): "4_3",
        (3, 4): "3_4", (3, 2): "3_2", (2, 3): "2_3", (21, 9): "21_9", (9, 21): "9_21",
    }

    def __init__(self, api_key: Optional[str] = None, base_save_dir: Optional[str] = None):
        self.api_key = api_key
        self.base_save_dir = base_save_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "code", "result", "image_client")

    @classmethod
    def _size_to_preset(cls, image_size: Optional[dict]) -> Optional[str]:
        """{"width": 1920, "height": 1080} -> "16_9_1k", when the ratio has one."""
        if not image_size:
            return None
        w, h = image_size["width"], image_size["height"]
        divisor = gcd(w, h) or 1
        ratio = cls._PRESET_ASPECTS.get((w // divisor, h // divisor))
        if not ratio:
            return None
        longest = max(w, h)
        bucket = min((("512", 512), ("1k", 1024), ("2k", 2048), ("4k", 4096)),
                     key=lambda pair: abs(pair[1] - longest))[0]
        return f"{ratio}_{bucket}"

    @staticmethod
    def _size_to_image_size(size: Optional[str]) -> Optional[dict]:
        """"1280*720" -> {"width": 1280, "height": 720}."""
        if not size or "*" not in str(size):
            return None
        try:
            w, h = str(size).split("*", 1)
            return {"width": int(w), "height": int(h)}
        except (TypeError, ValueError):
            return None

    def generate_image(self,
                       prompt: str,
                       model: str,
                       session_id: str = "default",
                       size: Optional[str] = None,
                       image_paths: Optional[List[str]] = None,
                       save_dir: Optional[str] = None,
                       timeout: int = 600) -> List[str]:
        params = {"prompt": prompt}

        image_size = self._size_to_image_size(size)
        candidates: List[Optional[object]] = [None]
        if image_size:
            # a couple of models take width/height instead; the filter keeps one
            params["width"] = image_size["width"]
            params["height"] = image_size["height"]
            preset = self._size_to_preset(image_size)
            # exact first, approximate second; skip straight to the one that
            # worked last time for this model
            ordered = [image_size] + ([preset] if preset else [])
            if self._ENCODING.get(model) == "preset" and preset:
                ordered = [preset]
            candidates = ordered

        if image_paths:
            urls = [mr.to_url(p, api_key=self.api_key) for p in image_paths]
            params["image_url"] = urls[0]
            params["image_urls"] = urls

        url = record = None
        last_error = None
        for candidate in candidates:
            attempt = dict(params)
            if candidate is not None:
                attempt["image_size"] = candidate
            try:
                url, record = mr.run(model, attempt, timeout=timeout, api_key=self.api_key)
                self._ENCODING[model] = "object" if isinstance(candidate, dict) else "preset"
                if isinstance(candidate, str):
                    logger.info("ModelRunner %s took the preset %s, an approximation of %sx%s",
                                model, candidate, image_size["width"], image_size["height"])
                break
            except mr.ModelRunnerError as exc:
                # Only an image_size encoding mismatch is worth retrying, and only
                # because it is rejected at validation time, before anything bills.
                if "/image_size" not in str(exc) or candidate is candidates[-1]:
                    raise
                logger.info("ModelRunner %s rejected this image_size encoding, trying the other: %s",
                            model, str(exc)[:160])
                last_error = exc
        if url is None:
            raise last_error or mr.ModelRunnerError(f"{model} produced no output")

        target_dir = save_dir or os.path.join(self.base_save_dir, session_id)
        ext = os.path.splitext(url.split("?")[0])[1] or ".png"
        dest = os.path.join(target_dir, f"modelrunner_{uuid.uuid4().hex[:12]}{ext}")
        mr.download(url, dest)
        logger.info("ModelRunner image %s -> %s (request %s)", model, dest, record.get("id"))
        return [os.path.abspath(dest)]
