"""Simulate STM32 + FreeRTOS device side behavior for integration testing."""
from __future__ import annotations

import asyncio
import json
import math
import random

from proto.messages import DeviceStatus, FramePacket, ImuPacket, now_ms

EDGE_HOST = "127.0.0.1"
EDGE_PORT = 9000
DEVICE_ID = "stm32-dms-001"


async def run() -> None:
    reader, writer = await asyncio.open_connection(EDGE_HOST, EDGE_PORT)

    async def send(kind: str, payload: dict) -> None:
        writer.write((json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False) + "\n").encode())
        await writer.drain()

    frame_id = 0
    dropped = 0

    async def imu_loop() -> None:
        t = 0.0
        while True:
            fatigue_spike = 1.0 if frame_id % 220 > 180 else 0.3
            accel = [
                round(math.sin(t) * 0.9 + random.random() * 0.15, 3),
                round(math.cos(t) * 0.6 + random.random() * 0.15, 3),
                9.8,
            ]
            gyro = [
                round(random.uniform(-8, 8) * fatigue_spike, 3),
                round(random.uniform(-5, 5) * fatigue_spike, 3),
                round(random.uniform(-180, 220) * fatigue_spike, 3),
            ]
            pkt = ImuPacket(device_id=DEVICE_ID, ts_ms=now_ms(), accel_xyz=accel, gyro_xyz=gyro)
            await send("imu", json.loads(pkt.to_json()))
            t += 0.1
            await asyncio.sleep(0.01)  # 100Hz

    async def frame_loop() -> None:
        nonlocal frame_id
        while True:
            fatigue_phase = (frame_id % 300) / 300.0
            eye = min(0.95, 0.35 + fatigue_phase * 0.7 + random.uniform(-0.06, 0.06))
            yawn = min(0.95, 0.2 + fatigue_phase * 0.65 + random.uniform(-0.1, 0.08))
            pitch = random.uniform(-20, 20)
            pkt = FramePacket(
                device_id=DEVICE_ID,
                frame_id=frame_id,
                ts_ms=now_ms(),
                eye_close_ratio=max(0.01, eye),
                yawn_ratio=max(0.01, yawn),
                head_pitch=pitch,
            )
            await send("frame", json.loads(pkt.to_json()))
            frame_id += 1
            await asyncio.sleep(1 / 30)  # QVGA 30FPS

    async def status_loop() -> None:
        while True:
            s = DeviceStatus(
                device_id=DEVICE_ID,
                ts_ms=now_ms(),
                fps=30.0,
                imu_hz=100.0,
                temperature_c=48.5 + random.uniform(-0.8, 1.3),
                dropped_frames=dropped,
            )
            await send("status", json.loads(s.to_json()))
            await asyncio.sleep(1.0)

    await asyncio.gather(imu_loop(), frame_loop(), status_loop())


if __name__ == "__main__":
    asyncio.run(run())
