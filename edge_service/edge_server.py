"""Edge DMS service: fuse visual + IMU streams, produce final judgement."""
from __future__ import annotations

import asyncio
from collections import deque
import json
import os
from typing import Deque, Dict, Optional


from proto.messages import AlertEvent, AlertLevel, FramePacket, ImuPacket, now_ms

CLOUD_URL = os.getenv("CLOUD_URL", "http://127.0.0.1:8000")
EDGE_HOST = os.getenv("EDGE_HOST", "0.0.0.0")
EDGE_PORT = int(os.getenv("EDGE_PORT", "9000"))


class FusionContext:
    def __init__(self) -> None:
        self.imu_window: Deque[ImuPacket] = deque(maxlen=60)
        self.last_alert_ts = 0

    def push_imu(self, imu: ImuPacket) -> None:
        self.imu_window.append(imu)

    def fuse(self, frame: FramePacket) -> Optional[AlertEvent]:
        if not self.imu_window:
            return None

        head_shake = max(abs(x.gyro_xyz[2]) for x in self.imu_window)
        accel_jump = max(abs(x.accel_xyz[0]) + abs(x.accel_xyz[1]) for x in self.imu_window)

        fatigue_score = (
            frame.eye_close_ratio * 0.5
            + frame.yawn_ratio * 0.3
            + min(abs(frame.head_pitch) / 25.0, 1.0) * 0.2
        )
        distraction_score = min(head_shake / 220.0, 1.0) * 0.6 + min(accel_jump / 14.0, 1.0) * 0.4
        score = max(fatigue_score, distraction_score)

        now = now_ms()
        if score < 0.68 or now - self.last_alert_ts < 1200:
            return None

        self.last_alert_ts = now
        level = AlertLevel.CRITICAL if score > 0.85 else AlertLevel.WARNING
        code = "FATIGUE" if fatigue_score >= distraction_score else "DISTRACTION"
        reason = (
            f"fatigue={fatigue_score:.2f}, distraction={distraction_score:.2f}, "
            f"eye={frame.eye_close_ratio:.2f}, yawn={frame.yawn_ratio:.2f}, gyro={head_shake:.1f}"
        )
        return AlertEvent(
            device_id=frame.device_id,
            ts_ms=now,
            level=level,
            code=code,
            reason=reason,
            score=score,
            latency_ms=max(1, now - frame.ts_ms),
        )


class EdgeServer:
    def __init__(self) -> None:
        self.device_ctx: Dict[str, FusionContext] = {}

    async def handle_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while not reader.at_eof():
            raw = await reader.readline()
            if not raw:
                break
            try:
                msg = json.loads(raw.decode("utf-8"))
                kind = msg.get("kind")
                payload = json.dumps(msg["payload"], ensure_ascii=False)
                if kind == "imu":
                    imu = ImuPacket.from_json(payload)
                    self.device_ctx.setdefault(imu.device_id, FusionContext()).push_imu(imu)
                elif kind == "frame":
                    frame = FramePacket.from_json(payload)
                    ctx = self.device_ctx.setdefault(frame.device_id, FusionContext())
                    event = ctx.fuse(frame)
                    if event:
                        await self.send_alert(event)
                elif kind == "status":
                    await self.send_status(msg["payload"])
            except Exception as exc:  # noqa: BLE001
                print(f"[edge] parse error: {exc}")

        writer.close()
        await writer.wait_closed()

    async def _post_json(self, url: str, payload: dict) -> None:
        import urllib.request

        def _post() -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0):
                return

        await asyncio.to_thread(_post)

    async def send_alert(self, event: AlertEvent) -> None:
        try:
            await self._post_json(f"{CLOUD_URL}/alerts", event.to_dict())
            print(f"[edge] alert => {event.code} latency={event.latency_ms}ms score={event.score:.2f}")
        except Exception as exc:  # noqa: BLE001
            print(f"[edge] push alert failed: {exc}")

    async def send_status(self, payload: dict) -> None:
        try:
            await self._post_json(f"{CLOUD_URL}/status", payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[edge] push status failed: {exc}")

    async def run(self) -> None:
        server = await asyncio.start_server(self.handle_conn, EDGE_HOST, EDGE_PORT)
        print(f"[edge] listening on {EDGE_HOST}:{EDGE_PORT}")
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(EdgeServer().run())
