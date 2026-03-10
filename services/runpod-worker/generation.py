from __future__ import annotations

import copy
import gc
import os
import random
import shutil
import subprocess
import tempfile
import warnings
from dataclasses import dataclass

import numpy as np
import torch
from PIL import Image
from diffusers import (
    DEISMultistepScheduler,
    DPMSolverMultistepInverseScheduler,
    DPMSolverMultistepScheduler,
    DPMSolverSinglestepScheduler,
    FlowMatchEulerDiscreteScheduler,
    SASolverScheduler,
    UniPCMultistepScheduler,
)
from diffusers.pipelines.wan.pipeline_wan_i2v import WanImageToVideoPipeline
from diffusers.utils.export_utils import export_to_video
from torch.nn import functional as F
from torchao.quantization import (
    Float8DynamicActivationFloat8WeightConfig,
    Int8WeightOnlyConfig,
    quantize_,
)
from tqdm import tqdm

import aoti

os.environ["TOKENIZERS_PARALLELISM"] = "true"
warnings.filterwarnings("ignore")

# RunPod base images may set HF_HUB_ENABLE_HF_TRANSFER=1.
# If hf_transfer isn't available, force standard download mode instead of crashing.
if os.getenv("HF_HUB_ENABLE_HF_TRANSFER") == "1":
    try:
        import hf_transfer  # noqa: F401
    except Exception:  # noqa: BLE001
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

MODEL_ID = "TestOrganizationPleaseIgnore/WAMU_v2_WAN2.2_I2V_LIGHTNING"
CACHE_DIR = os.path.expanduser("~/.cache/huggingface/")

MAX_DIM = 832
MIN_DIM = 480
SQUARE_DIM = 640
MULTIPLE_OF = 16
MAX_SEED = np.iinfo(np.int32).max

FIXED_FPS = 16
MIN_FRAMES_MODEL = 8
MAX_FRAMES_MODEL = 160

MIN_DURATION = round(MIN_FRAMES_MODEL / FIXED_FPS, 1)
MAX_DURATION = round(MAX_FRAMES_MODEL / FIXED_FPS, 1)

DEFAULT_PROMPT_I2V = "make this image come alive, cinematic motion, smooth animation"
DEFAULT_NEGATIVE_PROMPT = (
    "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, "
    "整体发灰, 最差质量, 低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, "
    "画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, 形态畸形的肢体, 手指融合, "
    "静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走"
)

SCHEDULER_MAP = {
    "FlowMatchEulerDiscrete": FlowMatchEulerDiscreteScheduler,
    "SASolver": SASolverScheduler,
    "DEISMultistep": DEISMultistepScheduler,
    "DPMSolverMultistepInverse": DPMSolverMultistepInverseScheduler,
    "UniPCMultistep": UniPCMultistepScheduler,
    "DPMSolverMultistep": DPMSolverMultistepScheduler,
    "DPMSolverSinglestep": DPMSolverSinglestepScheduler,
}


@dataclass(frozen=True)
class GenerationResult:
    video_path: str
    seed: int
    fps: int
    width: int
    height: int
    duration_seconds: float


def clear_vram() -> None:
    gc.collect()
    torch.cuda.empty_cache()


def resize_image(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width == height:
        return image.resize((SQUARE_DIM, SQUARE_DIM), Image.LANCZOS)

    aspect_ratio = width / height
    max_aspect_ratio = MAX_DIM / MIN_DIM
    min_aspect_ratio = MIN_DIM / MAX_DIM

    image_to_resize = image
    if aspect_ratio > max_aspect_ratio:
        target_w, target_h = MAX_DIM, MIN_DIM
        crop_width = int(round(height * max_aspect_ratio))
        left = (width - crop_width) // 2
        image_to_resize = image.crop((left, 0, left + crop_width, height))
    elif aspect_ratio < min_aspect_ratio:
        target_w, target_h = MIN_DIM, MAX_DIM
        crop_height = int(round(width / min_aspect_ratio))
        top = (height - crop_height) // 2
        image_to_resize = image.crop((0, top, width, top + crop_height))
    else:
        if width > height:
            target_w = MAX_DIM
            target_h = int(round(target_w / aspect_ratio))
        else:
            target_h = MAX_DIM
            target_w = int(round(target_h * aspect_ratio))

    final_w = round(target_w / MULTIPLE_OF) * MULTIPLE_OF
    final_h = round(target_h / MULTIPLE_OF) * MULTIPLE_OF
    final_w = max(MIN_DIM, min(MAX_DIM, final_w))
    final_h = max(MIN_DIM, min(MAX_DIM, final_h))
    return image_to_resize.resize((final_w, final_h), Image.LANCZOS)


def resize_and_crop_to_match(target_image: Image.Image, reference_image: Image.Image) -> Image.Image:
    ref_width, ref_height = reference_image.size
    target_width, target_height = target_image.size
    scale = max(ref_width / target_width, ref_height / target_height)
    new_width, new_height = int(target_width * scale), int(target_height * scale)
    resized = target_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left, top = (new_width - ref_width) // 2, (new_height - ref_height) // 2
    return resized.crop((left, top, left + ref_width, top + ref_height))


def get_num_frames(duration_seconds: float) -> int:
    return 1 + int(
        np.clip(
            int(round(duration_seconds * FIXED_FPS)),
            MIN_FRAMES_MODEL,
            MAX_FRAMES_MODEL,
        )
    )


class Wan22Generator:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.rife_model = self._load_rife_model()
        self.pipe = self._load_pipeline()
        self.original_scheduler = copy.deepcopy(self.pipe.scheduler)

    def _load_rife_model(self):
        if not os.path.exists("RIFEv4.26_0921.zip"):
            subprocess.run(
                [
                    "wget",
                    "-q",
                    "https://huggingface.co/r3gm/RIFE/resolve/main/RIFEv4.26_0921.zip",
                    "-O",
                    "RIFEv4.26_0921.zip",
                ],
                check=True,
            )

        if not os.path.exists("train_log"):
            subprocess.run(["unzip", "-o", "RIFEv4.26_0921.zip"], check=True)

        from train_log.RIFE_HDv3 import Model

        rife_model = Model()
        rife_model.load_model("train_log", -1)
        rife_model.eval()
        return rife_model

    def _load_pipeline(self) -> WanImageToVideoPipeline:
        pipe = WanImageToVideoPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
        ).to("cuda")

        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)

        quantize_(pipe.text_encoder, Int8WeightOnlyConfig())
        quantize_(pipe.transformer, Float8DynamicActivationFloat8WeightConfig())
        quantize_(pipe.transformer_2, Float8DynamicActivationFloat8WeightConfig())

        aoti.aoti_blocks_load(pipe.transformer, "zerogpu-aoti/Wan2", variant="fp8da")
        aoti.aoti_blocks_load(pipe.transformer_2, "zerogpu-aoti/Wan2", variant="fp8da")

        return pipe

    @torch.no_grad()
    def _interpolate_bits(self, frames_np: np.ndarray, multiplier: int = 2, scale: float = 1.0) -> list[np.ndarray]:
        if isinstance(frames_np, list):
            t = len(frames_np)
            h, w, _ = frames_np[0].shape
        else:
            t, h, w, _ = frames_np.shape

        if multiplier < 2:
            if isinstance(frames_np, np.ndarray):
                return list(frames_np)
            return frames_np

        n_interp = multiplier - 1

        tmp = max(128, int(128 / scale))
        ph = ((h - 1) // tmp + 1) * tmp
        pw = ((w - 1) // tmp + 1) * tmp
        padding = (0, pw - w, 0, ph - h)

        def to_tensor(frame_np: np.ndarray) -> torch.Tensor:
            tensor = torch.from_numpy(frame_np).to(self.device)
            tensor = tensor.permute(2, 0, 1).unsqueeze(0)
            return F.pad(tensor, padding).half()

        def from_tensor(tensor: torch.Tensor) -> np.ndarray:
            out = tensor[0, :, :h, :w]
            out = out.permute(1, 2, 0)
            return out.float().cpu().numpy()

        def make_inference(i0: torch.Tensor, i1: torch.Tensor, n: int) -> list[torch.Tensor]:
            if self.rife_model.version >= 3.9:
                res: list[torch.Tensor] = []
                for i in range(n):
                    res.append(self.rife_model.inference(i0, i1, (i + 1) * 1.0 / (n + 1), scale))
                return res

            middle = self.rife_model.inference(i0, i1, scale)
            if n == 1:
                return [middle]
            first_half = make_inference(i0, middle, n=n // 2)
            second_half = make_inference(middle, i1, n=n // 2)
            if n % 2:
                return [*first_half, middle, *second_half]
            return [*first_half, *second_half]

        output_frames: list[np.ndarray] = []
        i1 = to_tensor(frames_np[0])
        total_steps = t - 1

        with tqdm(total=total_steps, desc="Interpolating", unit="frame"):
            for i in range(total_steps):
                i0 = i1
                output_frames.append(from_tensor(i0))

                i1 = to_tensor(frames_np[i + 1])
                mid_tensors = make_inference(i0, i1, n_interp)
                for mid in mid_tensors:
                    output_frames.append(from_tensor(mid))

            output_frames.append(from_tensor(i1))

        clear_vram()
        return output_frames

    def _run_inference(
        self,
        *,
        resized_image: Image.Image,
        processed_last_image: Image.Image | None,
        prompt: str,
        steps: int,
        negative_prompt: str,
        num_frames: int,
        guidance_scale: float,
        guidance_scale_2: float,
        seed: int,
        scheduler_name: str,
        flow_shift: float,
        frame_multiplier: int,
        quality: int,
    ) -> tuple[str, int]:
        scheduler_class = SCHEDULER_MAP.get(scheduler_name)
        if scheduler_class is None:
            raise ValueError(f"Unsupported scheduler: {scheduler_name}")

        if (
            scheduler_class.__name__ != self.pipe.scheduler.config._class_name
            or flow_shift != self.pipe.scheduler.config.get("flow_shift", "shift")
        ):
            config = copy.deepcopy(self.original_scheduler.config)
            if scheduler_class == FlowMatchEulerDiscreteScheduler:
                config["shift"] = flow_shift
            else:
                config["flow_shift"] = flow_shift
            self.pipe.scheduler = scheduler_class.from_config(config)

        clear_vram()

        result = self.pipe(
            image=resized_image,
            last_image=processed_last_image,
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=resized_image.height,
            width=resized_image.width,
            num_frames=num_frames,
            guidance_scale=float(guidance_scale),
            guidance_scale_2=float(guidance_scale_2),
            num_inference_steps=int(steps),
            generator=torch.Generator(device="cuda").manual_seed(seed),
            output_type="np",
        )

        raw_frames_np = result.frames[0]
        self.pipe.scheduler = self.original_scheduler

        frame_factor = frame_multiplier // FIXED_FPS
        if frame_factor > 1:
            self.rife_model.device()
            self.rife_model.flownet = self.rife_model.flownet.half()
            final_frames = self._interpolate_bits(raw_frames_np, multiplier=int(frame_factor))
        else:
            final_frames = list(raw_frames_np)

        final_fps = FIXED_FPS * int(frame_factor)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
            video_path = tmpfile.name

        export_to_video(final_frames, video_path, fps=final_fps, quality=quality)
        return video_path, final_fps

    def generate(
        self,
        *,
        input_image: Image.Image,
        last_image: Image.Image | None,
        prompt: str,
        steps: int,
        duration_seconds: float,
        quality: int,
        frame_multiplier: int,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        guidance_scale: float = 1.0,
        guidance_scale_2: float = 1.0,
        scheduler: str = "UniPCMultistep",
        flow_shift: float = 3.0,
        seed: int | None = None,
    ) -> GenerationResult:
        if input_image is None:
            raise ValueError("input_image is required")

        num_frames = get_num_frames(duration_seconds)
        current_seed = random.randint(0, MAX_SEED) if seed is None else int(seed)
        resized_image = resize_image(input_image)

        processed_last_image = None
        if last_image:
            processed_last_image = resize_and_crop_to_match(last_image, resized_image)

        video_path, final_fps = self._run_inference(
            resized_image=resized_image,
            processed_last_image=processed_last_image,
            prompt=prompt,
            steps=steps,
            negative_prompt=negative_prompt,
            num_frames=num_frames,
            guidance_scale=guidance_scale,
            guidance_scale_2=guidance_scale_2,
            seed=current_seed,
            scheduler_name=scheduler,
            flow_shift=flow_shift,
            frame_multiplier=frame_multiplier,
            quality=quality,
        )

        return GenerationResult(
            video_path=video_path,
            seed=current_seed,
            fps=final_fps,
            width=resized_image.width,
            height=resized_image.height,
            duration_seconds=duration_seconds,
        )
