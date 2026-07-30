#pragma once

#include <Arduino.h>
#include "esp_camera.h"

#define CROP_CHOP_TEST_NAME "Crop Chop XIAO ESP32S3 Sense Camera Test"
#define CROP_CHOP_FIRMWARE_VERSION "0.1.0"
#define CROP_CHOP_BOARD_TYPE "Seeed Studio XIAO ESP32S3 Sense"

#define CAMERA_AP_SSID "CropChop-Camera-Test"
#define CAMERA_AP_PASSWORD "CropChopTest123"

// Official XIAO ESP32S3 Sense camera pin mapping from the installed Arduino
// ESP32 CameraWebServer example, CAMERA_MODEL_XIAO_ESP32S3.
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

static camera_config_t makeCameraConfig(bool psramDetected) {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // PSRAM allows two frame buffers and PSRAM-backed storage; without it, keep
  // the buffer count and starting resolution conservative.
  config.frame_size = psramDetected ? FRAMESIZE_VGA : FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = psramDetected ? 2 : 1;
  config.fb_location = psramDetected ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  return config;
}
