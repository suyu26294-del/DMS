"""Cloud storage + remote management for DMS alerts."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

DB_PATH = Path(__file__).with_name("dms_cloud.db")

app = FastAPI(title="DMS Cloud", version="1.0.0")


class AlertIn(BaseModel):
    device_id: str
    ts_ms: int
    level: str
    code: str
    reason: str
    score: float
    latency_ms: int


class StatusIn(BaseModel):
    device_id: str
    ts_ms: int
    fps: float
    imu_hz: float
    temperature_c: float
    dropped_frames: int


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                level TEXT NOT NULL,
                code TEXT NOT NULL,
                reason TEXT NOT NULL,
                score REAL NOT NULL,
                latency_ms INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                fps REAL NOT NULL,
                imu_hz REAL NOT NULL,
                temperature_c REAL NOT NULL,
                dropped_frames INTEGER NOT NULL
            )
            """
        )


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "db": str(DB_PATH)}


@app.post("/alerts")
def post_alert(payload: AlertIn) -> Dict[str, Any]:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO alerts(device_id, ts_ms, level, code, reason, score, latency_ms)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                payload.device_id,
                payload.ts_ms,
                payload.level,
                payload.code,
                payload.reason,
                payload.score,
                payload.latency_ms,
            ),
        )
    return {"stored": True}


@app.get("/alerts")
def get_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY ts_ms DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(x) for x in rows]


@app.post("/status")
def post_status(payload: StatusIn) -> Dict[str, Any]:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO status(device_id, ts_ms, fps, imu_hz, temperature_c, dropped_frames)
            VALUES(?,?,?,?,?,?)
            """,
            (
                payload.device_id,
                payload.ts_ms,
                payload.fps,
                payload.imu_hz,
                payload.temperature_c,
                payload.dropped_frames,
            ),
        )
    return {"stored": True}


@app.get("/status/latest")
def latest_status() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT s.* FROM status s
            INNER JOIN (
                SELECT device_id, MAX(ts_ms) AS mx
                FROM status GROUP BY device_id
            ) t ON s.device_id=t.device_id AND s.ts_ms=t.mx
            ORDER BY s.device_id
            """
        ).fetchall()
    return [dict(x) for x in rows]
