"""ModelRunner video generation client (text-to-video and image-to-video)."""
import logging
import os
from typing import Optional

try:
    from models import modelrunner_api as mr
except ImportError:
    from . import modelrunner_api as mr

logger = logging.getLogger(__name__)


class ModelRunnerVideoClient:
    """Generates video through a hosted catalog model.

    Hosted models take urls while this codebase passes local paths, so every
    image input is uploaded first. As in the image client, alternative spellings
    for the same idea (image / image_url, resolution / video_resolution) are all
    offered and filtered against the model's declared schema rather than
    branching per model.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def generate_video(self,
                       prompt: str,
                       image_path: Optional[str],
                       save_path: str,
                       model: str,
                       duration: int = 5,
                       video_ratio: str = "16:9",
                       resolution: Optional[str] = None,
                       last_image_path: Optional[str] = None,
                       seed: Optional[int] = None,
                       timeout: int = 1800) -> str:
        params = {"prompt": prompt, "duration": duration, "aspect_ratio": video_ratio}

        if resolution:
            # catalogs spell this either way; the filter keeps whichever exists
            params["resolution"] = str(resolution).lower()
            params["video_resolution"] = str(resolution).lower()
        if seed is not None:
            params["seed"] = seed

        if image_path:
            url = mr.to_url(image_path, api_key=self.api_key)
            params["image"] = url
            params["image_url"] = url
        if last_image_path:
            end = mr.to_url(last_image_path, api_key=self.api_key)
            params["end_image_url"] = end
            params["tail_image_url"] = end

        url, record = mr.run(model, params, timeout=timeout, api_key=self.api_key)
        mr.download(url, save_path)
        logger.info("ModelRunner video %s -> %s (request %s)", model, save_path, record.get("id"))
        return os.path.abspath(save_path)
