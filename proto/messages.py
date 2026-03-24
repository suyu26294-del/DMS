"""Shared message schema for device-edge-cloud DMS pipeline."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
import json
import time
from typing import Any, Dict, List


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(slots=True)
class DeviceStatus:
    device_id: str
    ts_ms: int
    fps: float
    imu_hz: float
    temperature_c: float
    dropped_frames: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass(slots=True)
class FramePacket:
    device_id: str
    frame_id: int
    ts_ms: int
    eye_close_ratio: float
    yawn_ratio: float
    head_pitch: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "FramePacket":
        return cls(**json.loads(raw))


@dataclass(slots=True)
class ImuPacket:
    device_id: str
    ts_ms: int
    accel_xyz: List[float]
    gyro_xyz: List[float]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "ImuPacket":
        return cls(**json.loads(raw))


@dataclass(slots=True)
class AlertEvent:
    device_id: str
    ts_ms: int
    level: AlertLevel
    code: str
    reason: str
    score: float
    latency_ms: int

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["level"] = self.level.value
        return payload



def now_ms() -> int:
    return int(time.time() * 1000)
