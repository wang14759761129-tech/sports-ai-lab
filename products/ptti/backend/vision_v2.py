"""Evidence contracts and lightweight video sampling for Vision Lab v2.

All scene results are candidates. This module does not rewrite BallTrack v1
outputs or claim semantic scene understanding.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil, sqrt
from typing import Iterable, Sequence


class ModuleState(str, Enum):
    NOT_INSTALLED = "NOT_INSTALLED"
    AVAILABLE = "AVAILABLE"
    READY = "READY"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class ModuleAvailability:
    dependencies: bool
    checkpoint: bool = False
    integrated: bool = True


@dataclass(frozen=True)
class VisionModule:
    id: str
    name: str
    state: ModuleState
    product_status: str
    license: str
    version: str | None
    message: str
    runtime: str


@dataclass(frozen=True)
class _ModuleSpec:
    id: str
    name: str
    product_status: str
    license: str
    version: str | None
    runtime: str
    requires_checkpoint: bool
    default_message: str
    disabled: bool = False


_MODULES = (
    _ModuleSpec("balltrack", "RacketVision BallTrack", "PRODUCT", "MIT; model asset terms tracked separately", "v1 frozen RAW", "shared GPU worker", True, "Official RAW observations remain the default."),
    _ModuleSpec("scene-detector", "镜头变化候选", "EXPERIMENTAL", "OpenCV Apache-2.0", "histogram-v1", "isolated vision-v2 worker", False, "镜头变化只触发重新抽帧，不代表比赛 / 回放分类。"),
    _ModuleSpec("grounding-dino", "Grounding DINO", "EXPERIMENTAL", "Apache-2.0 code and checkpoint", "IDEA-Research/grounding-dino-base", "isolated vision-v2 worker", True, "真实研究视频候选已生成；所有框需人工复核。"),
    _ModuleSpec("grounding-dino-person", "Grounding DINO · 人物基线", "RESEARCH_ONLY", "Apache-2.0 code; exact checkpoint terms tracked separately", "GROUNDING_DINO_PLAYER_BASELINE", "isolated vision-v2 worker", True, "冻结的 20 帧人物候选基线；不作为默认人物检测器。"),
    _ModuleSpec("rtmdet-person", "RTMDet Tiny · 运行环境受阻", "RESEARCH_ONLY", "Apache-2.0 code; checkpoint terms require per-artifact review", "rtmdet_tiny_8xb32-300e_coco", "isolated vision-v2-openmmlab worker", True, "RTMDET_RUNTIME_BLOCKED：保留实验记录，当前不继续安装。"),
    _ModuleSpec("rtdetr-person", "RT-DETR R18 · 人物识别", "EXPERIMENTAL", "Apache-2.0 model card; pinned safetensors", "ac77a11ff0170a41b771c03264987f8ce2b0d753", "existing isolated Transformers worker", True, "真实开发与新增比赛帧已推理；复杂画面角色分配仍需人工审核。"),
    _ModuleSpec("scoreboard-module", "记分牌模块", "NOT_IMPLEMENTED", "TTI module boundary only", None, "future isolated ROI/OCR worker", False, "从场景检测 Gate 中拆出；当前没有记分牌检测或 OCR。", True),
    _ModuleSpec("video-segmenter", "SAM 2 视频分割", "EXPERIMENTAL", "Apache-2.0 code and checkpoints", None, "isolated vision-v2 worker", True, "尚未安装；需先实测漂移与场景切换恢复。"),
    _ModuleSpec("player-pose", "RTMPose / MMPose", "EXPERIMENTAL", "Apache-2.0 code; per-checkpoint terms required", None, "isolated vision-v2 worker", True, "尚未安装姿态模型或检查点。"),
    _ModuleSpec("scoreboard-ocr", "PaddleOCR", "EXPERIMENTAL", "Apache-2.0 code; per-model terms required", None, "isolated CPU/GPU worker", True, "尚未安装；比分只能作为候选观测。"),
    _ModuleSpec("scene-classifier", "MMAction2 场景分类", "RESEARCH_ONLY", "Apache-2.0 code; per-checkpoint terms required", None, "isolated research worker", True, "未安装；当前镜头变化不等于 PLAY / NON-PLAY 分类。"),
    _ModuleSpec("co-tracker", "CoTracker", "RESEARCH_ONLY", "CC-BY-NC majority; separate component terms apply", None, "isolated research worker", True, "非商业研究用途；默认关闭。", True),
)


class VisionModuleManager:
    """Build a truthful module snapshot from injected runtime evidence."""

    def __init__(self, availability=None, *, running=(), failed=None):
        self.availability = availability or {}
        self.running = set(running)
        self.failed = dict(failed or {})

    def snapshot(self) -> list[VisionModule]:
        result = []
        for spec in _MODULES:
            available = self.availability.get(spec.id, ModuleAvailability(False))
            if spec.id in self.failed:
                state, message = ModuleState.FAILED, str(self.failed[spec.id])
            elif spec.id in self.running:
                state, message = ModuleState.RUNNING, "模块正在处理任务。"
            elif spec.disabled:
                state, message = ModuleState.DISABLED, spec.default_message
            elif not available.dependencies:
                state, message = ModuleState.NOT_INSTALLED, spec.default_message
            elif spec.requires_checkpoint and not available.checkpoint:
                state, message = ModuleState.AVAILABLE, "运行代码可用，模型权重尚未配置。"
            elif not available.integrated:
                state, message = ModuleState.AVAILABLE, "基础代码可用，尚未接入视频处理流程。"
            else:
                state, message = ModuleState.READY, spec.default_message
            result.append(VisionModule(
                id=spec.id,
                name=spec.name,
                state=state,
                product_status=spec.product_status,
                license=spec.license,
                version=spec.version,
                message=message,
                runtime=spec.runtime,
            ))
        return result


@dataclass(frozen=True)
class Keyframe:
    frame: int
    timestamp_ms: int
    reasons: tuple[str, ...]


class KeyframeSampler:
    """Sample sparse scene-bootstrap frames plus explicit evidence triggers."""

    def __init__(self, interval_seconds: float = 10.0):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = float(interval_seconds)

    def sample(
        self,
        frame_count: int,
        fps: float,
        *,
        scene_cut_frames: Iterable[int] = (),
        tracking_failure_frames: Iterable[int] = (),
        requested_frames: Iterable[int] = (),
    ) -> list[Keyframe]:
        if frame_count < 0:
            raise ValueError("frame_count cannot be negative")
        if fps <= 0:
            raise ValueError("fps must be positive")
        if frame_count == 0:
            return []
        reasons: dict[int, list[str]] = {}

        def add(frame: int, reason: str):
            if 0 <= frame < frame_count:
                reasons.setdefault(int(frame), [])
                if reason not in reasons[int(frame)]:
                    reasons[int(frame)].append(reason)

        add(0, "VIDEO_START")
        last_frame = frame_count - 1
        add(last_frame, "VIDEO_END")
        interval_frames = max(1, round(self.interval_seconds * fps))
        for frame in range(interval_frames, frame_count, interval_frames):
            add(frame, "PERIODIC")
        for frame in scene_cut_frames:
            add(int(frame), "SCENE_CHANGE")
        for frame in tracking_failure_frames:
            add(int(frame), "TRACKER_FAILURE")
        for frame in requested_frames:
            add(int(frame), "USER_REQUEST")
        return [
            Keyframe(frame, round(frame * 1000 / fps), tuple(reasons[frame]))
            for frame in sorted(reasons)
        ]


@dataclass(frozen=True)
class SceneEvidence:
    type: str
    value: float
    threshold: float
    reference_frame: int


@dataclass(frozen=True)
class SceneBoundaryCandidate:
    frame: int
    timestamp_ms: int
    status: str
    evidence: tuple[SceneEvidence, ...]


class SceneBoundaryDetector:
    """Lightweight RGB histogram cut proposal; never classifies scene meaning."""

    def __init__(self, threshold: float = 0.48, minimum_gap_frames: int = 10, bins: int = 16):
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if minimum_gap_frames < 0:
            raise ValueError("minimum_gap_frames cannot be negative")
        if bins < 2:
            raise ValueError("bins must be at least 2")
        self.threshold = float(threshold)
        self.minimum_gap_frames = int(minimum_gap_frames)
        self.bins = int(bins)
        self._previous: tuple[int, int, tuple[tuple[float, ...], ...]] | None = None
        self._last_candidate_frame = -self.minimum_gap_frames

    def observe(self, frame: int, timestamp_ms: int, image) -> SceneBoundaryCandidate | None:
        current = self._histograms(image)
        previous = self._previous
        self._previous = (int(frame), int(timestamp_ms), current)
        if previous is None:
            return None
        reference_frame, _, previous_hist = previous
        distance = sum(self._distance(a, b) for a, b in zip(previous_hist, current)) / 3
        if distance < self.threshold or frame - self._last_candidate_frame < self.minimum_gap_frames:
            return None
        self._last_candidate_frame = int(frame)
        return SceneBoundaryCandidate(
            frame=int(frame),
            timestamp_ms=int(timestamp_ms),
            status="SUGGESTED",
            evidence=(SceneEvidence("HISTOGRAM_CHANGE", round(distance, 6), self.threshold, reference_frame),),
        )

    def _histograms(self, image) -> tuple[tuple[float, ...], ...]:
        if hasattr(image, "tolist"):
            image = image.tolist()
        rows = list(image)
        if not rows:
            raise ValueError("frame image is empty")
        height = len(rows)
        first_row = rows[0]
        width = len(first_row)
        if width == 0:
            raise ValueError("frame image is empty")
        stride_y = max(1, height // 48)
        stride_x = max(1, width // 48)
        counts = [[0] * self.bins for _ in range(3)]
        samples = 0
        for y in range(0, height, stride_y):
            row = rows[y]
            for x in range(0, width, stride_x):
                pixel = row[x]
                if len(pixel) < 3:
                    raise ValueError("frame must have at least three color channels")
                for channel in range(3):
                    value = max(0, min(255, int(pixel[channel])))
                    counts[channel][min(self.bins - 1, value * self.bins // 256)] += 1
                samples += 1
        if samples == 0:
            raise ValueError("frame image has no pixels")
        return tuple(tuple(count / samples for count in channel) for channel in counts)

    @staticmethod
    def _distance(left: Sequence[float], right: Sequence[float]) -> float:
        coefficient = sum(sqrt(a * b) for a, b in zip(left, right))
        return sqrt(max(0.0, 1.0 - min(1.0, coefficient)))
