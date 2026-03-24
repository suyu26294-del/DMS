"""Cloud storage + remote management for DMS alerts."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel
import json
import os

DB_PATH = Path(__file__).with_name("dms_cloud.db")
MQTT_ENABLE = os.getenv("MQTT_ENABLE", "0") == "1"
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_ALERT_TOPIC = os.getenv("MQTT_ALERT_TOPIC", "/dms/alerts")
MQTT_STATUS_TOPIC = os.getenv("MQTT_STATUS_TOPIC", "/dms/status")

app = FastAPI(title="DMS Cloud", version="1.0.0")
mqtt_worker: "MqttWorker | None" = None


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


def store_alert(payload: Dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO alerts(device_id, ts_ms, level, code, reason, score, latency_ms)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                payload["device_id"],
                payload["ts_ms"],
                payload["level"],
                payload["code"],
                payload["reason"],
                payload["score"],
                payload["latency_ms"],
            ),
        )


def store_status(payload: Dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO status(device_id, ts_ms, fps, imu_hz, temperature_c, dropped_frames)
            VALUES(?,?,?,?,?,?)
            """,
            (
                payload["device_id"],
                payload["ts_ms"],
                payload["fps"],
                payload["imu_hz"],
                payload["temperature_c"],
                payload["dropped_frames"],
            ),
        )


class MqttWorker:
    def __init__(self) -> None:
        self._thread: "threading.Thread | None" = None
        self._client = None

    def start(self) -> None:
        import paho.mqtt.client as mqtt

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USERNAME:
            self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)

        self._thread = threading.Thread(target=self._client.loop_forever, daemon=True)
        self._thread.start()
        print(f"[cloud] MQTT worker started: {MQTT_HOST}:{MQTT_PORT}")

    def stop(self) -> None:
        if self._client is not None:
            self._client.disconnect()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        print("[cloud] MQTT worker stopped")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, reason_code, properties
        client.subscribe([(MQTT_ALERT_TOPIC, 1), (MQTT_STATUS_TOPIC, 1)])

    def _on_message(self, client, userdata, msg) -> None:
        del client, userdata
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if msg.topic == MQTT_ALERT_TOPIC:
                store_alert(payload)
            elif msg.topic == MQTT_STATUS_TOPIC:
                store_status(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[cloud] MQTT parse error: {exc}")


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
    if MQTT_ENABLE:
        global mqtt_worker
        mqtt_worker = MqttWorker()
        mqtt_worker.start()


@app.on_event("shutdown")
def stop_worker() -> None:
    if mqtt_worker is not None:
        mqtt_worker.stop()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "db": str(DB_PATH), "mqtt_enabled": MQTT_ENABLE}


@app.post("/alerts")
def post_alert(payload: AlertIn) -> Dict[str, Any]:
    store_alert(payload.model_dump())
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
    store_status(payload.model_dump())
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
