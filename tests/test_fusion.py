from edge_service.edge_server import FusionContext
from proto.messages import FramePacket, ImuPacket


def test_fusion_triggers_alert_under_fatigue_and_shake() -> None:
    ctx = FusionContext()
    for i in range(30):
        ctx.push_imu(
            ImuPacket(
                device_id="dev1",
                ts_ms=1000 + i,
                accel_xyz=[2.0, 2.0, 9.8],
                gyro_xyz=[5.0, 1.0, 240.0],
            )
        )

    frame = FramePacket(
        device_id="dev1",
        frame_id=1,
        ts_ms=500,
        eye_close_ratio=0.95,
        yawn_ratio=0.9,
        head_pitch=19.0,
    )
    event = ctx.fuse(frame)
    assert event is not None
    assert event.code in {"FATIGUE", "DISTRACTION"}
    assert event.latency_ms >= 1


def test_fusion_suppresses_low_score() -> None:
    ctx = FusionContext()
    for i in range(20):
        ctx.push_imu(
            ImuPacket(
                device_id="dev1",
                ts_ms=1000 + i,
                accel_xyz=[0.1, 0.1, 9.8],
                gyro_xyz=[0.1, 0.1, 2.0],
            )
        )

    frame = FramePacket(
        device_id="dev1",
        frame_id=2,
        ts_ms=900,
        eye_close_ratio=0.22,
        yawn_ratio=0.12,
        head_pitch=2.0,
    )
    assert ctx.fuse(frame) is None
