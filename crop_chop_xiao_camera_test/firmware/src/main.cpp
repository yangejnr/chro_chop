#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"
#include "esp_chip_info.h"
#include "esp_system.h"
#include "camera_config.h"

WebServer server(80);

struct Metrics {
  uint32_t framesCaptured = 0;
  uint32_t captureFailures = 0;
  uint32_t latestCaptureMs = 0;
  uint32_t minCaptureMs = UINT32_MAX;
  uint32_t maxCaptureMs = 0;
  uint64_t totalCaptureMs = 0;
  uint32_t minJpegBytes = UINT32_MAX;
  uint32_t maxJpegBytes = 0;
  uint64_t totalJpegBytes = 0;
  uint32_t minFreeHeap = UINT32_MAX;
  uint32_t resetTimeMs = 0;
};

Metrics metrics;
bool cameraInitialised = false;
esp_err_t cameraInitResult = ESP_OK;
bool psramDetected = false;
String cameraModel = "unknown";
uint16_t cameraPid = 0;
framesize_t activeFrameSize = FRAMESIZE_VGA;
const char *activeResolutionName = "VGA";

struct ResolutionOption {
  const char *name;
  framesize_t frameSize;
  uint16_t width;
  uint16_t height;
};

const ResolutionOption RESOLUTIONS[] = {
  {"QVGA", FRAMESIZE_QVGA, 320, 240},
  {"VGA", FRAMESIZE_VGA, 640, 480},
  {"SVGA", FRAMESIZE_SVGA, 800, 600},
};

const ResolutionOption *currentResolution() {
  for (const auto &option : RESOLUTIONS) {
    if (option.frameSize == activeFrameSize) {
      return &option;
    }
  }
  return &RESOLUTIONS[1];
}

String escapeJson(const String &value) {
  String out;
  for (size_t index = 0; index < value.length(); index++) {
    char character = value[index];
    if (character == '"' || character == '\\') {
      out += '\\';
    }
    out += character;
  }
  return out;
}

String resetReasonName(esp_reset_reason_t reason) {
  switch (reason) {
    case ESP_RST_POWERON: return "power_on";
    case ESP_RST_EXT: return "external";
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT: return "interrupt_watchdog";
    case ESP_RST_TASK_WDT: return "task_watchdog";
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_DEEPSLEEP: return "deep_sleep";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_SDIO: return "sdio";
    default: return "unknown";
  }
}

String identifyCameraModel(uint16_t pid) {
  if (pid == OV2640_PID) {
    return "OV2640";
  }
  if (pid == OV3660_PID) {
    return "OV3660";
  }
  return "unknown";
}

void resetMetrics() {
  metrics = Metrics();
  metrics.minFreeHeap = ESP.getFreeHeap();
  metrics.resetTimeMs = millis();
}

void updateMetrics(uint32_t elapsedMs, size_t jpegBytes) {
  metrics.framesCaptured++;
  metrics.latestCaptureMs = elapsedMs;
  metrics.totalCaptureMs += elapsedMs;
  metrics.minCaptureMs = min(metrics.minCaptureMs, elapsedMs);
  metrics.maxCaptureMs = max(metrics.maxCaptureMs, elapsedMs);
  metrics.totalJpegBytes += jpegBytes;
  metrics.minJpegBytes = min(metrics.minJpegBytes, static_cast<uint32_t>(jpegBytes));
  metrics.maxJpegBytes = max(metrics.maxJpegBytes, static_cast<uint32_t>(jpegBytes));
  metrics.minFreeHeap = min(metrics.minFreeHeap, ESP.getFreeHeap());
}

camera_fb_t *captureFrame() {
  if (!cameraInitialised) {
    metrics.captureFailures++;
    return nullptr;
  }

  uint32_t started = millis();
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) {
    metrics.captureFailures++;
    metrics.minFreeHeap = min(metrics.minFreeHeap, ESP.getFreeHeap());
    return nullptr;
  }

  updateMetrics(millis() - started, frame->len);
  return frame;
}

String healthJson() {
  String status = cameraInitialised ? "ok" : "fault";
  String json = "{";
  json += "\"status\":\"" + status + "\",";
  json += "\"camera_initialised\":" + String(cameraInitialised ? "true" : "false") + ",";
  json += "\"camera_model\":\"" + cameraModel + "\",";
  json += "\"camera_product_id\":" + String(cameraPid) + ",";
  json += "\"psram_detected\":" + String(psramDetected ? "true" : "false") + ",";
  json += "\"free_heap_bytes\":" + String(ESP.getFreeHeap()) + ",";
  json += "\"uptime_ms\":" + String(millis()) + ",";
  json += "\"frames_captured\":" + String(metrics.framesCaptured) + ",";
  json += "\"capture_failures\":" + String(metrics.captureFailures);
  json += "}";
  return json;
}

String metricsJson() {
  const ResolutionOption *resolution = currentResolution();
  uint32_t measuredSeconds = max<uint32_t>((millis() - metrics.resetTimeMs) / 1000, 1);
  float averageCaptureMs = metrics.framesCaptured ? static_cast<float>(metrics.totalCaptureMs) / metrics.framesCaptured : 0.0f;
  float meanJpegBytes = metrics.framesCaptured ? static_cast<float>(metrics.totalJpegBytes) / metrics.framesCaptured : 0.0f;
  float currentFps = metrics.latestCaptureMs ? 1000.0f / metrics.latestCaptureMs : 0.0f;
  float averageFps = static_cast<float>(metrics.framesCaptured) / measuredSeconds;
  uint32_t minCapture = metrics.framesCaptured ? metrics.minCaptureMs : 0;
  uint32_t minJpeg = metrics.framesCaptured ? metrics.minJpegBytes : 0;

  String json = "{";
  json += "\"active_resolution\":\"" + String(activeResolutionName) + "\",";
  json += "\"frame_width\":" + String(resolution->width) + ",";
  json += "\"frame_height\":" + String(resolution->height) + ",";
  json += "\"frames_captured\":" + String(metrics.framesCaptured) + ",";
  json += "\"capture_failures\":" + String(metrics.captureFailures) + ",";
  json += "\"current_fps\":" + String(currentFps, 3) + ",";
  json += "\"average_fps\":" + String(averageFps, 3) + ",";
  json += "\"latest_capture_time_ms\":" + String(metrics.latestCaptureMs) + ",";
  json += "\"mean_capture_time_ms\":" + String(averageCaptureMs, 3) + ",";
  json += "\"minimum_capture_time_ms\":" + String(minCapture) + ",";
  json += "\"maximum_capture_time_ms\":" + String(metrics.maxCaptureMs) + ",";
  json += "\"mean_jpeg_size_bytes\":" + String(meanJpegBytes, 3) + ",";
  json += "\"minimum_free_heap\":" + String(metrics.minFreeHeap) + ",";
  json += "\"device_uptime_ms\":" + String(millis());
  json += "}";
  return json;
}

void handleRoot() {
  String html = "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Crop Chop Camera Test</title></head><body>";
  html += "<h1>Crop Chop XIAO Camera Test</h1>";
  html += "<p>Status: " + String(cameraInitialised ? "camera initialised" : "camera fault") + "</p>";
  html += "<p>Camera model: " + cameraModel + "</p>";
  html += "<p><a href='/stream'>Live stream</a> | <a href='/capture'>Capture JPEG</a> | <a href='/health'>Health JSON</a> | <a href='/metrics'>Metrics JSON</a> | <a href='/config'>Config</a></p>";
  html += "<p>Resolution: <a href='/set-resolution?value=QVGA'>QVGA</a> <a href='/set-resolution?value=VGA'>VGA</a> <a href='/set-resolution?value=SVGA'>SVGA</a></p>";
  html += "<img src='/stream' style='max-width:100%;height:auto'>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleHealth() {
  server.send(200, "application/json", healthJson());
}

void handleMetrics() {
  server.send(200, "application/json", metricsJson());
}

void handleConfig() {
  const ResolutionOption *resolution = currentResolution();
  String json = "{";
  json += "\"board\":\"" CROP_CHOP_BOARD_TYPE "\",";
  json += "\"ap_ssid\":\"" CAMERA_AP_SSID "\",";
  json += "\"active_resolution\":\"" + String(activeResolutionName) + "\",";
  json += "\"frame_width\":" + String(resolution->width) + ",";
  json += "\"frame_height\":" + String(resolution->height) + ",";
  json += "\"jpeg_quality\":12,";
  json += "\"psram_detected\":" + String(psramDetected ? "true" : "false") + ",";
  json += "\"frame_buffers\":" + String(psramDetected ? 2 : 1);
  json += "}";
  server.send(200, "application/json", json);
}

void handleCapture() {
  camera_fb_t *frame = captureFrame();
  if (!frame) {
    server.send(503, "application/json", "{\"status\":\"fault\",\"error\":\"camera_capture_failed\"}");
    return;
  }

  server.sendHeader("Cache-Control", "no-store");
  server.send_P(200, "image/jpeg", reinterpret_cast<const char *>(frame->buf), frame->len);
  esp_camera_fb_return(frame);
}

void handleStream() {
  WiFiClient client = server.client();
  String response = "HTTP/1.1 200 OK\r\n";
  response += "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n";
  response += "Cache-Control: no-store\r\n\r\n";
  client.print(response);

  while (client.connected()) {
    camera_fb_t *frame = captureFrame();
    if (!frame) {
      client.print("--frame\r\nContent-Type: text/plain\r\n\r\ncapture failed\r\n");
      delay(500);
      continue;
    }

    client.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", frame->len);
    client.write(frame->buf, frame->len);
    client.print("\r\n");
    esp_camera_fb_return(frame);
    delay(20);
  }
}

void handleSetResolution() {
  if (!cameraInitialised) {
    server.send(503, "application/json", "{\"status\":\"fault\",\"error\":\"camera_not_initialised\"}");
    return;
  }
  if (!server.hasArg("value")) {
    server.send(400, "application/json", "{\"status\":\"fault\",\"error\":\"missing_value\"}");
    return;
  }

  String requested = server.arg("value");
  requested.toUpperCase();
  for (const auto &option : RESOLUTIONS) {
    if (requested == option.name) {
      sensor_t *sensor = esp_camera_sensor_get();
      int result = sensor->set_framesize(sensor, option.frameSize);
      if (result != 0) {
        server.send(500, "application/json", "{\"status\":\"fault\",\"error\":\"set_framesize_failed\"}");
        return;
      }
      activeFrameSize = option.frameSize;
      activeResolutionName = option.name;
      resetMetrics();
      server.send(200, "application/json", "{\"status\":\"ok\",\"active_resolution\":\"" + String(activeResolutionName) + "\"}");
      return;
    }
  }

  server.send(400, "application/json", "{\"status\":\"fault\",\"error\":\"unsupported_resolution\"}");
}

void handleResetMetrics() {
  resetMetrics();
  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void printDeviceInfo() {
  esp_chip_info_t chipInfo;
  esp_chip_info(&chipInfo);
  Serial.println("BEGIN_DEVICE_INFO");
  Serial.printf("test_name: %s\n", CROP_CHOP_TEST_NAME);
  Serial.printf("firmware_version: %s\n", CROP_CHOP_FIRMWARE_VERSION);
  Serial.printf("compile_date_time: %s %s\n", __DATE__, __TIME__);
  Serial.printf("board_type: %s\n", CROP_CHOP_BOARD_TYPE);
  Serial.printf("chip_model: %s\n", ESP.getChipModel());
  Serial.printf("chip_revision: %d\n", chipInfo.revision);
  Serial.printf("cpu_frequency_mhz: %u\n", ESP.getCpuFreqMHz());
  Serial.printf("flash_size_bytes: %u\n", ESP.getFlashChipSize());
  Serial.printf("available_heap_bytes: %u\n", ESP.getFreeHeap());
  Serial.printf("psram_detected: %s\n", psramDetected ? "true" : "false");
  Serial.printf("psram_total_size_bytes: %u\n", ESP.getPsramSize());
  Serial.printf("camera_initialisation_result: 0x%08x\n", cameraInitResult);
  Serial.printf("camera_product_id: %u\n", cameraPid);
  Serial.printf("camera_model: %s\n", cameraModel.c_str());
  Serial.printf("mac_address: %s\n", WiFi.macAddress().c_str());
  Serial.printf("reset_reason: %s\n", resetReasonName(esp_reset_reason()).c_str());
  Serial.println("END_DEVICE_INFO");
}

void setupCamera() {
  psramDetected = psramFound();

  // Camera initialisation uses the official XIAO pin map and conservative JPEG
  // settings so that first measurements are stable and reproducible.
  camera_config_t config = makeCameraConfig(psramDetected);
  cameraInitResult = esp_camera_init(&config);
  cameraInitialised = (cameraInitResult == ESP_OK);
  if (!cameraInitialised) {
    Serial.printf("CAMERA_INIT_ERROR: 0x%08x\n", cameraInitResult);
    return;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor) {
    cameraPid = sensor->id.PID;
    cameraModel = identifyCameraModel(cameraPid);
    activeFrameSize = config.frame_size;
    activeResolutionName = psramDetected ? "VGA" : "QVGA";
  }
}

void setupServer() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP(CAMERA_AP_SSID, CAMERA_AP_PASSWORD);
  Serial.printf("access_point_ssid: %s\n", CAMERA_AP_SSID);
  Serial.printf("access_point_ip: %s\n", WiFi.softAPIP().toString().c_str());

  // HTTP endpoints expose live capture, health, configuration and measured
  // performance data for the Python runner and browser checks.
  server.on("/", HTTP_GET, handleRoot);
  server.on("/stream", HTTP_GET, handleStream);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/metrics", HTTP_GET, handleMetrics);
  server.on("/config", HTTP_GET, handleConfig);
  server.on("/set-resolution", HTTP_GET, handleSetResolution);
  server.on("/reset-metrics", HTTP_GET, handleResetMetrics);
  server.begin();
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  resetMetrics();
  setupCamera();
  setupServer();
  printDeviceInfo();
  if (!cameraInitialised) {
    Serial.println("Camera fault mode active; HTTP health/config endpoints remain available.");
  }
}

void loop() {
  server.handleClient();
  if (!cameraInitialised) {
    delay(1000);
  }
}
