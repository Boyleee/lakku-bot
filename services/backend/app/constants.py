"""Constants mirrored from HF Space defaults for Wan2.2 I2V."""

DEFAULT_PROMPT_I2V = "make this image come alive, cinematic motion, smooth animation"
DEFAULT_NEGATIVE_PROMPT = (
    "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, "
    "整体发灰, 最差质量, 低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, "
    "画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, 形态畸形的肢体, 手指融合, "
    "静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走"
)

FIXED_FPS = 16
FPS_CHOICES = (FIXED_FPS, FIXED_FPS * 2, FIXED_FPS * 4)
MIN_FRAMES_MODEL = 8
MAX_FRAMES_MODEL = 160
MIN_DURATION_SECONDS = round(MIN_FRAMES_MODEL / FIXED_FPS, 1)
MAX_DURATION_SECONDS = round(MAX_FRAMES_MODEL / FIXED_FPS, 1)

DEFAULT_DURATION_SECONDS = 3.5
DEFAULT_INFERENCE_STEPS = 6
DEFAULT_VIDEO_QUALITY = 6

MIN_INFERENCE_STEPS = 1
MAX_INFERENCE_STEPS = 30
MIN_VIDEO_QUALITY = 1
MAX_VIDEO_QUALITY = 10

DEFAULT_SCHEDULER = "UniPCMultistep"
DEFAULT_FLOW_SHIFT = 3.0
DEFAULT_GUIDANCE_SCALE = 1.0
DEFAULT_GUIDANCE_SCALE_2 = 1.0
