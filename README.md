# FreeRTOS 车载边缘计算驾驶员监测系统（DMS）

> 周期：2025.03 - 2025.04  
> 架构：端（STM32 + FreeRTOS）—边（融合分析）—云（告警存储/远程管理）+ Qt 上位机

## 1. 项目目标

本仓库实现了一个完整的端—边—云协同 DMS 参考工程，覆盖：

- **设备端（MCU）**：视频采集、IMU 采集、异常触发和状态上报。
- **边缘端（Edge）**：视觉特征 + IMU 融合，输出主判断告警。
- **云端（Cloud）**：告警/状态落库、查询接口与远程管理入口。
- **Qt 上位机**：实时拉取云端告警并展示。

对应关键指标：

- QVGA 视频采集目标 **30FPS**（通过 DMA 双缓冲 + 多任务解耦）。
- 端到端告警响应控制目标 **< 300ms**（告警里回传 `latency_ms`）。
- 支持长期运行验证（可用模拟器跑稳定性压力测试）。

---

## 2. 目录结构

```text
.
├── firmware/                 # STM32 + FreeRTOS 设备端核心代码
│   └── Core/
│       ├── Inc/dms_device.h
│       └── Src/dms_device.c
├── edge_service/             # 边缘融合服务（Python asyncio）
│   └── edge_server.py
├── cloud_service/            # 云端存储/管理服务（FastAPI + SQLite）
│   └── app.py
├── qt_host/                  # Qt 上位机（C++/Qt6 Widgets）
│   ├── CMakeLists.txt
│   └── main.cpp
├── proto/                    # 端-边-云共享消息协议
│   └── messages.py
├── tools/
│   └── device_simulator.py   # 设备端行为模拟器（30FPS+100Hz）
└── tests/
    └── test_fusion.py        # 融合逻辑测试
```

---

## 3. 设备端（STM32 + FreeRTOS）设计

`firmware/Core/Src/dms_device.c` 实现了面向 MCU 的核心调度框架：

- **DMA 双缓冲**：`g_frame_dma_buf[2][DMS_FRAME_BYTES]` + `DMS_OnFrameComplete()` 轮转。
- **5 个核心任务**：
  1. `CaptureTask`：消费帧队列、提取特征/触发告警。
  2. `ImuTask`：100Hz IMU 采样。
  3. `EventTask`：状态机切换（`CAPTURE/ALERT/FAULT`）。
  4. `MqttTask`：告警与状态通过 MQTT/TCP 上报（预留接口）。
  5. `HealthTask`：1Hz 健康巡检（温度、帧率、积压）。

> 说明：该部分为可移植工程骨架，需要和你的 HAL、驱动、网络栈工程（如 CubeMX 生成项目）集成。

---

## 4. 边缘端融合算法

`edge_service/edge_server.py` 负责接收设备上报：

- 输入流：`frame`（视觉统计特征）+ `imu`（惯性数据）+ `status`。
- 融合策略：
  - `fatigue_score`（闭眼率/打哈欠/俯仰角）
  - `distraction_score`（角速度峰值/加速度突变）
  - 取两者最大值为主风险评分。
- 告警生成：
  - 阈值默认 `0.68`。
  - 冷却窗口 `1200ms` 防止重复报警风暴。
- 输出：推送到云端 `/alerts` 与 `/status`，或通过 MQTT（阿里云 IoT）上报。

---

## 5. 云端管理与存储

`cloud_service/app.py` 提供 FastAPI 接口：

- `POST /alerts`：保存告警事件。
- `GET /alerts?limit=50`：查询最近告警。
- `POST /status`：保存状态数据。
- `GET /status/latest`：获取每个设备最新状态。
- `GET /health`：健康检查。

数据库使用本地 SQLite（`cloud_service/dms_cloud.db`），方便联调和演示。
同时支持启用 MQTT worker 直接消费 `/dms/alerts` 与 `/dms/status` 主题。

---

## 6. Qt 上位机

`qt_host/main.cpp` 提供基础监控台：

- 每 1s 拉取云端 `/alerts?limit=30`。
- 表格展示时间、设备、级别、类型、评分、时延、原因。
- 支持工程化编译（`qt_host/CMakeLists.txt`）。

---

## 7. 快速启动（本地联调）

### 7.1 Python 环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 7.2 启动云端

```bash
uvicorn cloud_service.app:app --host 0.0.0.0 --port 8000
```

### 7.3 启动边缘端

```bash
python edge_service/edge_server.py
```

如需 MQTT 上报：

```bash
EDGE_UPLINK=mqtt MQTT_HOST=<broker> MQTT_PORT=1883 python edge_service/edge_server.py
```

### 7.4 启动设备模拟器

```bash
python tools/device_simulator.py
```

启动后可查看：

- `http://127.0.0.1:8000/alerts`
- `http://127.0.0.1:8000/status/latest`

---

## 11. 实装部署与架构图

见 `docs/deployment_zh.md`，包含：

- 项目实例图（端-边-云）
- 云端图（阿里云 MQTT + 云端入库）
- Qt 图（拉取与渲染链路）

---

## 8. 测试

```bash
pytest -q
```

包含融合告警触发和低分抑制单测。

---

## 9. 与目标指标的对应关系

- **30FPS 稳定采集**：
  - 设备端采用 DMA 双缓冲和队列异步解耦，避免采集与发送互相阻塞。
- **<300ms 告警响应**：
  - 边缘端直接融合并输出，告警中记录 `latency_ms` 用于验收。
- **72h 稳定运行验证**：
  - 可使用 `tools/device_simulator.py` 长时间压测，结合云端日志评估丢帧/超时。
- **PCB 样片联调**：
  - 设备端已提供任务/队列/状态机骨架，可直接嫁接到板级工程。

---

## 10. 后续可扩展

- 接入真实摄像头特征提取模型（边缘端 ONNX/TensorRT）。
- 设备端增加看门狗复位与断线重连策略。
- 云端补充多租户、鉴权和远程配置下发。
- Qt 上位机加入告警声音、历史回放与导出报表。
