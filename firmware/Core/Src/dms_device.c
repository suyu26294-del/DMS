#include "dms_device.h"
#include <string.h>

static uint8_t g_frame_dma_buf[2][DMS_FRAME_BYTES];
static volatile uint8_t g_dma_index = 0;
static volatile uint32_t g_frame_counter = 0;
static volatile dms_state_t g_state = DMS_STATE_IDLE;

static osMessageQueueId_t g_frame_queue;
static osMessageQueueId_t g_imu_queue;
static osMessageQueueId_t g_alert_queue;

static void CaptureTask(void *arg);
static void ImuTask(void *arg);
static void EventTask(void *arg);
static void MqttTask(void *arg);
static void HealthTask(void *arg);

void DMS_Init(void) {
    g_frame_queue = osMessageQueueNew(4, sizeof(dms_frame_t), NULL);
    g_imu_queue = osMessageQueueNew(32, sizeof(dms_imu_sample_t), NULL);
    g_alert_queue = osMessageQueueNew(8, sizeof(uint32_t), NULL);
    g_state = DMS_STATE_CAPTURE;
}

void DMS_StartTasks(void) {
    const osThreadAttr_t high = {.priority = osPriorityHigh};
    const osThreadAttr_t normal = {.priority = osPriorityNormal};
    const osThreadAttr_t low = {.priority = osPriorityBelowNormal};

    osThreadNew(CaptureTask, NULL, &high);
    osThreadNew(ImuTask, NULL, &high);
    osThreadNew(EventTask, NULL, &normal);
    osThreadNew(MqttTask, NULL, &normal);
    osThreadNew(HealthTask, NULL, &low);
}

void DMS_OnFrameHalfComplete(void) {
    // DMA 双缓冲的半传输中断，可用于预处理或缓存切换统计
}

void DMS_OnFrameComplete(void) {
    dms_frame_t frame;
    frame.frame_id = g_frame_counter++;
    frame.ts_ms = osKernelGetTickCount();
    frame.buffer = g_frame_dma_buf[g_dma_index];
    osMessageQueuePut(g_frame_queue, &frame, 0, 0);

    g_dma_index = (uint8_t)((g_dma_index + 1) & 0x01);
}

static void CaptureTask(void *arg) {
    (void)arg;
    dms_frame_t frame;
    for (;;) {
        if (osMessageQueueGet(g_frame_queue, &frame, NULL, osWaitForever) == osOK) {
            // 将图像统计特征提取后打包上报边缘端（这里仅保留接口）
            if (g_state == DMS_STATE_ALERT) {
                uint32_t mark = frame.ts_ms;
                osMessageQueuePut(g_alert_queue, &mark, 0, 0);
            }
        }
    }
}

static void ImuTask(void *arg) {
    (void)arg;
    dms_imu_sample_t imu;
    memset(&imu, 0, sizeof(imu));

    for (;;) {
        imu.ts_ms = osKernelGetTickCount();
        // 替换为真实 I2C/SPI IMU 读取
        imu.accel[0] = 0.03f;
        imu.accel[1] = 0.01f;
        imu.accel[2] = 9.81f;
        imu.gyro[0] = 0.3f;
        imu.gyro[1] = 0.1f;
        imu.gyro[2] = 0.2f;
        osMessageQueuePut(g_imu_queue, &imu, 0, 0);
        osDelay(10); // 100Hz
    }
}

static void EventTask(void *arg) {
    (void)arg;
    dms_imu_sample_t imu;
    for (;;) {
        if (osMessageQueueGet(g_imu_queue, &imu, NULL, osWaitForever) == osOK) {
            float movement = imu.gyro[0] * imu.gyro[0] + imu.gyro[2] * imu.gyro[2];
            if (movement > 150.0f) {
                g_state = DMS_STATE_ALERT;
            } else if (g_state != DMS_STATE_FAULT) {
                g_state = DMS_STATE_CAPTURE;
            }
        }
    }
}

static void MqttTask(void *arg) {
    (void)arg;
    uint32_t alert_mark = 0;
    for (;;) {
        if (osMessageQueueGet(g_alert_queue, &alert_mark, NULL, 50) == osOK) {
            // 替换为真实 MQTT/TCP 发送
            // payload: {"type":"alert","ts":alert_mark}
        }
        osDelay(5);
    }
}

static void HealthTask(void *arg) {
    (void)arg;
    for (;;) {
        // 1Hz 健康监测：帧率、温度、队列积压、网络状态
        // 失败保护：超温/掉帧触发 DMS_STATE_FAULT
        osDelay(1000);
    }
}
