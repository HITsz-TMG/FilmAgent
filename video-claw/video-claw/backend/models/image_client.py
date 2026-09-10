import os
import sys

models_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(models_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import re
import time
import uuid
import logging
from typing import List, Optional
from config import Config

from models.config_model import model_provider

try:
    from models.image_dashscope import DashScopeClient
    from models.image_seedream import SeedreamClient
    from models.image_gpt import ImageGPT
    from models.image_modelrunner import ModelRunnerImageClient
    from models.image_processor import ImageProcessor
except ImportError:
    from .image_dashscope import DashScopeClient
    from .image_seedream import SeedreamClient
    from .image_gpt import ImageGPT
    from .image_modelrunner import ModelRunnerImageClient
    from .image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class ImageClient:
    def __init__(self,
                 dashscope_api_key: Optional[str] = None,
                 dashscope_base_url: Optional[str] = None,
                 gpt_api_key: Optional[str] = None,
                 gpt_base_url: Optional[str] = None,
                 proxy: Optional[str] = None,
                 ark_api_key: Optional[str] = None,
                 ark_base_url: Optional[str] = None):
        """
        Unified Image Generation Client
        Routes requests to DashScope, Seedream, or GPT based on model name.
        """
        self._dashscope_api_key = dashscope_api_key
        self._dashscope_base_url = dashscope_base_url
        self._ark_api_key = ark_api_key
        self._ark_base_url = ark_base_url
        self._gpt_api_key = gpt_api_key
        self._gpt_base_url = gpt_base_url
        self._proxy = Config.provider_proxy("openai") if proxy is None else proxy

        self._dashscope_client = None
        self._seedream_client = None
        self._gpt_client = None
        self._modelrunner_client = None

        # Initialize Image Processor for downloads
        self.image_processor = ImageProcessor()

        # Default save directory
        self.base_save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code", "result", "image_client")

    @property
    def modelrunner_client(self):
        if self._modelrunner_client is None:
            self._modelrunner_client = ModelRunnerImageClient(
                api_key=Config.MODELRUNNER_API_KEY,
                base_save_dir=self.base_save_dir,
            )
        return self._modelrunner_client

    @property
    def dashscope_client(self):
        if self._dashscope_client is None:
            self._dashscope_client = DashScopeClient(
                api_key=self._dashscope_api_key,
                base_url=self._dashscope_base_url,
            )
        return self._dashscope_client

    @property
    def seedream_client(self):
        if self._seedream_client is None:
            self._seedream_client = SeedreamClient(
                api_key=self._ark_api_key,
                base_url=self._ark_base_url,
            )
        return self._seedream_client

    @property
    def gpt_client(self):
        if self._gpt_client is None:
            self._gpt_client = ImageGPT(
                api_key=self._gpt_api_key,
                base_url=self._gpt_base_url,
                proxy=self._proxy,
            )
        return self._gpt_client

    def generate_image(self,
                       prompt: str,
                       image_paths: Optional[List[str]] = None,
                       model: str = "wan2.7-image",
                       save_dir: Optional[str] = None,
                       session_id: Optional[str] = None,
                       video_ratio: Optional[str] = "16:9",
                       resolution: Optional[str] = "2K") -> List[str]:
        """
        Generate images based on prompt and optional reference images.

        Args:
            prompt: Text prompt for generation.
            image_paths: List of local file paths or URLs for reference images.
            model: Model name to determine which provider to use.
            save_dir: Custom directory to save downloaded images.
            session_id: Session ID for organizing saved files.
            video_ratio: Aspect ratio of the video, e.g., "16:9", "9:16", "4:3", "3:4", "1:1".
            resolution: Resolution string, e.g., "720P", "1080P", "2K", "4K",
                or an exact media-slot size such as "1024*1024".

        Returns:
            List of absolute file paths of the generated images.
        """
        # Determine size from video_ratio and resolution
        size_map = {
            "16:9": {
                "720P": "1280*720",
                "1080P": "1920*1080",
                "2K": "2560*1440",
                "4K": "3840*2160"
            },
            "9:16": {
                "720P": "720*1280",
                "1080P": "1080*1920",
                "2K": "1440*2560",
                "4K": "2160*3840"
            },
            "4:3": {
                "720P": "960*720",
                "1080P": "1440*1080",
                "2K": "2560*1920",
                "4K": "3840*2880"
            },
            "3:4": {
                "720P": "720*960",
                "1080P": "1080*1440",
                "2K": "1920*2560",
                "4K": "2880*3840"
            },
            "1:1": {
                "720P": "720*720",
                "1080P": "1080*1080",
                "2K": "2560*2560",
                "4K": "3840*3840"
            }
        }
        
        custom_size = None
        if isinstance(resolution, str) and re.match(r"^\d+[x*]\d+$", resolution):
            custom_size = resolution.replace("x", "*")

        # Default fallback if ratio or resolution is not found
        size = custom_size or size_map.get(video_ratio, size_map["16:9"]).get(resolution, "1920*1080")

        if not model:
            model = "wan2.7-image"  # Default model

        if Config.PRINT_MODEL_INPUT:
            lines = [
                "---- IMAGE GENERATION REQUEST ----",
                f"Prompt: {prompt}",
            ]
            if image_paths:
                lines.append(f"Refs: {len(image_paths)}")
                for p in image_paths:
                    lines.append(" - [Base64图片]" if str(p).startswith("data:") else f" - {p}")
            lines.extend([
                f"Model: {model}",
                f"Video Ratio: {video_ratio}",
                f"Resolution: {resolution}",
                f"Final Size: {size}",
            ])
            if session_id:
                lines.append(f"Session ID: {session_id}")
            lines.append("-" * 30)
            logger.info("\n%s", "\n".join(lines))
            
        # Determine backend provider. The registered provider is checked first
        # and exactly, so a catalog id like "owner/alias" is never captured by
        # the substring tests below.
        is_modelrunner = model_provider(model) == "modelrunner"
        is_seedream = not is_modelrunner and "seedream" in model.lower()
        is_sora = not is_modelrunner and ("sora" in model.lower() or "gpt" in model.lower())
        
        # Prepare save directory
        if not save_dir:
            if session_id:
                save_dir = os.path.join(self.base_save_dir, session_id)
            else:
                save_dir = self.base_save_dir
        os.makedirs(save_dir, exist_ok=True)
        
        generated_local_paths = []
        provider_errors = []

        if is_modelrunner:
            # --- ModelRunner Logic ---
            try:
                logger.info("ImageClient routed to ModelRunner: model=%s", model)
                paths = self.modelrunner_client.generate_image(
                    prompt=prompt,
                    model=model,
                    session_id=session_id or "default",
                    size=size,
                    image_paths=image_paths,
                    save_dir=save_dir,
                )
                if paths:
                    generated_local_paths.extend(paths)
                else:
                    provider_errors.append("ModelRunner returned no images")
            except Exception as e:
                logger.exception("ModelRunner generation failed: %s", e)
                provider_errors.append(f"ModelRunner: {e}")

        elif is_seedream:
            # --- Seedream Logic ---
            try:
                logger.info("ImageClient routed to Seedream: model=%s", model)

                paths = self.seedream_client.generate_image(
                    prompt=prompt,
                    model=model,
                    session_id=session_id or "default",
                    size=size or "2048*2048",
                    image_paths=image_paths
                )

                if paths:
                    generated_local_paths.extend(paths)
                else:
                    provider_errors.append("Seedream returned no images")

            except Exception as e:
                logger.exception("Seedream generation failed: %s", e)
                provider_errors.append(f"Seedream: {e}")

        elif is_sora:
            # --- GPT/Sora Logic ---
            try:
                logger.info("ImageClient routed to GPT/Sora: model=%s", model)
                if image_paths:
                    logger.warning("Sora/GPT model only supports Text-to-Image. Ignoring reference images.")
                
                # OpenAI uses 'x' separator, e.g. 1024x1024
                # Attempt to map size if needed or just replace '*'
                gpt_size = size.replace('*', 'x') if size else "1024x1024"

                path = self.gpt_client.generate_image(
                    prompt=prompt,
                    size=gpt_size,
                    model=model,
                    save_dir=save_dir
                )
                
                if path and os.path.exists(path):
                    generated_local_paths.append(path)
                else:
                    logger.error("GPT/Sora returned invalid path or download failed: %s", path)
                    provider_errors.append(f"GPT/Sora returned invalid path or download failed: {path}")

            except Exception as e:
                logger.exception("GPT/Sora generation failed: %s", e)
                provider_errors.append(f"GPT/Sora: {e}")

        else:
            # --- DashScope Logic ---
            try:
                logger.info("ImageClient routed to DashScope: model=%s", model)

                if image_paths and len(image_paths) > 0:
                    # Pre-process image paths for DashScope
                    # Convert local paths to file:// URIs if they aren't already URLs
                    # DashScope SDK (via MultiModalConversation) handles file://
                    formatted_urls = []
                    for p in image_paths:
                        if p.startswith("http") or p.startswith("file://"):
                            formatted_urls.append(p)
                        else:
                            abs_path = os.path.abspath(p)
                            formatted_urls.append(f"file://{abs_path}")
                    
                    paths = self.dashscope_client.edit_image(
                        prompt=prompt,
                        image_urls=formatted_urls,
                        model=model,
                        size=size,
                        session_id=session_id,
                        save_dir=save_dir
                    )
                else:
                    # Text to Image
                    # Assuming default size 1024*1024 or similar
                    paths = self.dashscope_client.generate_image(
                        prompt=prompt,
                        model=model,
                        size=size,
                        session_id=session_id,
                        save_dir=save_dir
                    )
                
                if paths:
                    generated_local_paths.extend(paths)
                else:
                    provider_errors.append("DashScope returned no images")
                            
            except Exception as e:
                logger.exception("DashScope generation failed: %s", e)
                provider_errors.append(f"DashScope: {e}")

        if not generated_local_paths and provider_errors:
            raise RuntimeError("Image generation failed: " + " | ".join(provider_errors))
        return generated_local_paths
