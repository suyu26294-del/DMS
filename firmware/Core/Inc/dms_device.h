#ifndef DMS_DEVICE_H
#define DMS_DEVICE_H

#include "cmsis_os.h"
#include <stdint.h>

#define DMS_FRAME_W 320
#define DMS_FRAME_H 240
#define DMS_FRAME_BYTES (DMS_FRAME_W * DMS_FRAME_H)

typedef enum {
    DMS_STATE_IDLE = 0,
    DMS_STATE_CAPTURE,
    DMS_STATE_ALERT,
    DMS_STATE_FAULT,
} dms_state_t;

typedef struct {
    uint32_t ts_ms;
    float accel[3];
    float gyro[3];
} dms_imu_sample_t;

typedef struct {
    uint32_t frame_id;
    uint32_t ts_ms;
    uint8_t *buffer;
} dms_frame_t;

void DMS_Init(void);
void DMS_StartTasks(void);
void DMS_OnFrameHalfComplete(void);
void DMS_OnFrameComplete(void);

#endif
