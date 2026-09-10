"""
统一视频生成客户端
根据 model 名称自动路由到对应后端：
  - wan*      → DashscopeVideoClient (DashScope VideoSynthesis)
  - kling*    → KlingVideoClient (可灵 AI)
"""

import os
import sys

models_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(models_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import logging
from typing import Optional
from config import Config
from models.config_model import model_provider

try:
    from models.video_dashscope import DashscopeVideoClient
    from models.video_kling import KlingVideoClient
    from models.video_modelrunner import ModelRunnerVideoClient
    from models.video_seedance import SeedanceVideoClient
except ImportError:
    from video_dashscope import DashscopeVideoClient
    from video_kling import KlingVideoClient
    from video_modelrunner import ModelRunnerVideoClient
    from video_seedance import SeedanceVideoClient

logger = logging.getLogger(__name__)


class VideoClient:
    """
    统一视频生成客户端
    参照 ImageClient 模式，按模型名路由到不同后端
    """

    def __init__(
        self,
        dashscope_api_key: Optional[str] = None,
        dashscope_base_url: Optional[str] = None,
        kling_api_key: Optional[str] = None,
        kling_base_url: Optional[str] = None,
        ark_api_key: Optional[str] = None,
        ark_base_url: Optional[str] = None,
    ):
        self._dashscope_api_key = dashscope_api_key or Config.DASHSCOPE_API_KEY
        self._dashscope_base_url = dashscope_base_url or Config.DASHSCOPE_BASE_URL
        self._kling_api_key = kling_api_key or Config.KLING_API_KEY
        self._kling_base_url = kling_base_url or Config.KLING_BASE_URL
        self._ark_api_key = ark_api_key or Config.ARK_API_KEY
        self._ark_base_url = ark_base_url or Config.ARK_BASE_URL

        self._dashscope_client = None
        self._kling_client = None
        self._seedance_client = None
        self._modelrunner_client = None

    @property
    def modelrunner_client(self):
        if self._modelrunner_client is None:
            self._modelrunner_client = ModelRunnerVideoClient(
                api_key=Config.MODELRUNNER_API_KEY,
            )
        return self._modelrunner_client

    @property
    def Dashscope_client(self):
        if self._dashscope_client is None:
            self._dashscope_client = DashscopeVideoClient(
                api_key=self._dashscope_api_key,
                base_url=self._dashscope_base_url,
            )
        return self._dashscope_client

    @property
    def kling_client(self):
        if self._kling_client is None:
            self._kling_client = KlingVideoClient(
                api_key=self._kling_api_key,
                base_url=self._kling_base_url,
            )
        return self._kling_client

    @property
    def seedance_client(self):
        if self._seedance_client is None:
            self._seedance_client = SeedanceVideoClient(
                api_key=self._ark_api_key,
                base_url=self._ark_base_url,
            )
        return self._seedance_client

    def generate_video(
        self,
        prompt: str,
        image_path: Optional[str],
        save_path: str,
        model: str = "wan2.7-i2v",
        duration: int = 5,
        shot_type: str = "multi",
        sound: str = "",
        video_ratio: str = "16:9",
        resolution: Optional[str] = None,
        last_image_path: Optional[str] = None,
        first_clip_path: Optional[str] = None,
        reference_image_path: Optional[str] = None,
        reference_image_paths: Optional[list[str]] = None,
        reference_video_paths: Optional[list[str]] = None,
        reference_audio_path: Optional[str] = None,
        audio_path: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        mode: str = "pro",
        cfg_scale: float = 0.5,
        generate_audio: Optional[bool] = None,
        audio: Optional[bool] = None,
    ) -> str:
        """
        生成视频

        Args:
            prompt: 视频描述提示词
            image_path: 输入图片本地路径；DashScope wan2.7 视频续写可为空并使用 first_clip_path
            save_path: 输出视频保存路径
            model: 模型名，决定使用哪个后端
            duration: 视频时长（秒）
            shot_type: 镜头类型 "single" / "multi"

        Returns:
            video_url: 远端视频 URL

        Raises:
            FileNotFoundError: 输入图片不存在
            RuntimeError: 生成或下载失败
        """
        if not model:
            model = "wan2.7-i2v"

        # 确保 duration 是整数,视频模型通常要求整数秒
        duration = int(duration)

        if Config.PRINT_MODEL_INPUT:
            lines = [
                "---- VIDEO GENERATION REQUEST ----",
                f"Prompt: {prompt}",
                "Image: [Base64图片]" if image_path and str(image_path).startswith("data:") else f"Image: {image_path}",
                f"Model: {model}",
                f"Duration: {duration}s",
                f"Shot Type: {shot_type}",
                f"Video Ratio: {video_ratio}",
            ]
            if resolution:
                lines.append(f"Resolution: {resolution}")
            if last_image_path:
                lines.append(f"Last Image: {last_image_path}")
            if first_clip_path:
                lines.append(f"First Clip: {first_clip_path}")
            if reference_image_path:
                lines.append(f"Reference Image: {reference_image_path}")
            if reference_image_paths:
                lines.append(f"Reference Images: {reference_image_paths}")
            if reference_video_paths:
                lines.append(f"Reference Videos: {reference_video_paths}")
            if reference_audio_path:
                lines.append(f"Reference Audio: {reference_audio_path}")
            if audio_path:
                lines.append(f"Audio: {audio_path}")
            if negative_prompt:
                lines.append(f"Negative Prompt: {negative_prompt}")
            if sound:
                lines.append(f"Sound: {sound}")
            lines.extend([
                f"Save: {save_path}",
                "-" * 30,
            ])
            logger.info("\n%s", "\n".join(lines))

        model_lower = model.lower()

        # An exactly-registered ModelRunner model wins before the substring
        # tests: a catalog id like "kuaishou/kling-video/v2.6/image-to-video"
        # would otherwise be captured by the "kling" test below and sent to the
        # wrong backend.
        if model_provider(model) == "modelrunner":
            return self.modelrunner_client.generate_video(
                prompt=prompt,
                image_path=image_path,
                save_path=save_path,
                model=model,
                duration=duration,
                video_ratio=video_ratio,
                resolution=resolution,
                last_image_path=last_image_path,
                seed=seed,
            )

        if "kling" in model_lower:
            return self._generate_kling(
                prompt,
                image_path,
                save_path,
                model,
                duration,
                sound,
                video_ratio,
                resolution,
                mode,
                cfg_scale,
                negative_prompt or "",
            )
        elif "seedance" in model_lower:
            return self._generate_seedance(
                prompt,
                image_path,
                save_path,
                model,
                duration,
                video_ratio,
                resolution,
                seed,
                watermark,
                generate_audio,
            )
        elif "wan" in model_lower or "happyhorse" in model_lower:
            return self._generate_wan(
                prompt,
                image_path,
                save_path,
                model,
                duration,
                shot_type,
                video_ratio,
                last_image_path,
                first_clip_path,
                reference_image_path,
                reference_image_paths,
                reference_video_paths,
                reference_audio_path,
                audio_path,
                negative_prompt,
                resolution,
                prompt_extend,
                watermark if watermark is not None else False,
                seed,
                audio,
            )
        else:
            raise ValueError(f"未知的视频生成模型: {model}")

    @staticmethod
    def _normalize_seedance_resolution(resolution: Optional[str]) -> str:
        value = (resolution or "720p").strip().lower()
        return value if value in {"720p", "1080p"} else "720p"

    def _generate_wan(
        self,
        prompt: str,
        image_path: Optional[str],
        save_path: str,
        model: str,
        duration: int,
        shot_type: str,
        video_ratio: str,
        last_image_path: Optional[str],
        first_clip_path: Optional[str],
        reference_image_path: Optional[str],
        reference_image_paths: Optional[list[str]],
        reference_video_paths: Optional[list[str]],
        reference_audio_path: Optional[str],
        audio_path: Optional[str],
        negative_prompt: Optional[str],
        resolution: Optional[str],
        prompt_extend: Optional[bool],
        watermark: bool,
        seed: Optional[int],
        audio: Optional[bool],
    ) -> str:
        """通过万象模型生成视频"""
        # 设置 Wan 和 Happyhorse 系列视频生成的默认分辨率为 720P
        resolution = resolution or "720P"
        
        logger.info("VideoClient routed to Wan: model=%s", model)
        return self.Dashscope_client.generate_video(
            prompt=prompt,
            image_path=image_path,
            save_path=save_path,
            model=model,
            duration=duration,
            shot_type=shot_type,
            video_ratio=video_ratio,
            last_image_path=last_image_path,
            first_clip_path=first_clip_path,
            reference_image_path=reference_image_path,
            reference_image_paths=reference_image_paths,
            reference_video_paths=reference_video_paths,
            reference_audio_path=reference_audio_path,
            audio_path=audio_path,
            negative_prompt=negative_prompt,
            resolution=resolution,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
            audio=audio,
        )

    def _generate_kling(
        self,
        prompt: str,
        image_path: Optional[str],
        save_path: str,
        model: str,
        duration: int = 5,
        sound: str = "",
        video_ratio: str = "16:9",
        resolution: Optional[str] = None,
        mode: str = "pro",
        cfg_scale: float = 0.5,
        negative_prompt: str = "",
    ) -> str:
        """通过可灵模型生成视频"""
        logger.info("VideoClient routed to Kling: model=%s", model)
        return self.kling_client.generate_video(
            prompt=prompt,
            image_path=image_path,
            save_path=save_path,
            model=model,
            duration=duration,
            sound=sound,
            video_ratio=video_ratio,
            resolution=resolution,
            mode=mode,
            cfg_scale=cfg_scale,
            negative_prompt=negative_prompt,
        )

    def _generate_seedance(
        self,
        prompt: str,
        image_path: Optional[str],
        save_path: str,
        model: str,
        duration: int = 5,
        video_ratio: str = "16:9",
        resolution: Optional[str] = None,
        seed: Optional[int] = None,
        watermark: Optional[bool] = None,
        generate_audio: Optional[bool] = None,
    ) -> str:
        """通过 Seedance 模型生成视频"""
        logger.info("VideoClient routed to Seedance: model=%s", model)
        return self.seedance_client.generate_video(
            prompt=prompt,
            image_path=image_path,
            save_path=save_path,
            model=model,
            duration=duration,
            ratio=video_ratio,
            resolution=self._normalize_seedance_resolution(resolution),
            seed=seed,
            watermark=watermark,
            generate_audio=generate_audio,
        )


def _split_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _str_to_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _default_save_path(model: str, generation_mode: str) -> str:
    safe_model = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in model)
    return os.path.join(Config.RESULT_DIR, "video", "test_client", f"{safe_model}_{generation_mode}.mp4")


def _build_cli_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Test VideoClient with a selected generation mode and model.")
    parser.add_argument("--generation-mode", choices=["first_frame", "start_end_frame", "reference"], default="first_frame")
    parser.add_argument("--model", default="wan2.7-i2v", help="Video model id, e.g. wan2.7-i2v / wan2.7-r2v / happyhorse-1.0-r2v")
    parser.add_argument("--prompt", default="电影感画面，人物自然移动，镜头稳定推进，不要字幕或水印。")
    parser.add_argument("--image", help="First-frame image path for first_frame/start_end_frame, or an extra reference image for reference mode.")
    parser.add_argument("--last-image", help="Last-frame image path for start_end_frame mode.")
    parser.add_argument("--reference-images", help="Comma-separated reference image paths for reference mode.")
    parser.add_argument("--reference-videos", help="Comma-separated reference video paths for reference mode.")
    parser.add_argument("--reference-audio", help="Reference audio path for supported reference-to-video models.")
    parser.add_argument("--audio", help="Driving audio path for supported image-to-video models.")
    parser.add_argument("--first-clip", help="First clip path for supported video continuation models.")
    parser.add_argument("--save-path", help="Output mp4 path. Defaults to code/result/video/test_client/<model>_<mode>.mp4")
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--ratio", default="16:9")
    parser.add_argument("--resolution", default="720P")
    parser.add_argument("--shot-type", default="multi")
    parser.add_argument("--sound", default="")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--prompt-extend", choices=["true", "false"])
    parser.add_argument("--watermark", choices=["true", "false"])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--mode", default="pro", help="Kling mode fallback: std/pro.")
    parser.add_argument("--cfg-scale", type=float, default=0.5)
    parser.add_argument("--generate-audio", choices=["true", "false"])
    parser.add_argument("--audio-enabled", choices=["true", "false"], help="Pass DashScope audio boolean for supported models.")
    return parser


def _cli_generate(args) -> str:
    reference_image_paths = _split_csv(args.reference_images)
    reference_video_paths = _split_csv(args.reference_videos)
    image_path = args.image
    last_image_path = None

    if args.generation_mode == "first_frame":
        if not image_path and not args.first_clip:
            raise ValueError("first_frame mode requires --image or --first-clip.")
    elif args.generation_mode == "start_end_frame":
        if not image_path or not args.last_image:
            raise ValueError("start_end_frame mode requires --image and --last-image.")
        last_image_path = args.last_image
    elif args.generation_mode == "reference":
        if image_path:
            reference_image_paths.append(image_path)
        image_path = None
        if not reference_image_paths and not reference_video_paths:
            raise ValueError("reference mode requires --reference-images, --reference-videos, or --image.")

    save_path = args.save_path or _default_save_path(args.model, args.generation_mode)
    client = VideoClient()
    return client.generate_video(
        prompt=args.prompt,
        image_path=image_path,
        save_path=save_path,
        model=args.model,
        duration=args.duration,
        shot_type=args.shot_type,
        sound=args.sound,
        video_ratio=args.ratio,
        resolution=args.resolution,
        last_image_path=last_image_path,
        first_clip_path=args.first_clip,
        reference_image_paths=reference_image_paths or None,
        reference_video_paths=reference_video_paths or None,
        reference_audio_path=args.reference_audio,
        audio_path=args.audio,
        negative_prompt=args.negative_prompt or None,
        prompt_extend=_str_to_bool(args.prompt_extend),
        watermark=_str_to_bool(args.watermark),
        seed=args.seed,
        mode=args.mode,
        cfg_scale=args.cfg_scale,
        generate_audio=_str_to_bool(args.generate_audio),
        audio=_str_to_bool(args.audio_enabled),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = _build_cli_parser()
    cli_args = parser.parse_args()
    try:
        remote_url = _cli_generate(cli_args)
        output_path = cli_args.save_path or _default_save_path(cli_args.model, cli_args.generation_mode)
        print("✓ Video generation completed")
        print(f"  Remote URL: {remote_url}")
        print(f"  Local file: {os.path.abspath(output_path)}")
    except Exception as exc:
        print(f"✗ Video generation failed: {exc}", file=sys.stderr)
        sys.exit(1)
