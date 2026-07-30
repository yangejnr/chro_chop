#include <SoftwareSerial.h>

const unsigned long BAUD_RATE = 115200;
const char *FIRMWARE_VERSION = "0.4.0";
const size_t LINE_BUFFER_SIZE = 96;
const unsigned long DANGER_BLINK_INTERVAL_MS = 250;
const unsigned long SERIAL_STATUS_INTERVAL_MS = 1000;
const unsigned long SERVO_REPLY_TIMEOUT_MS = 40;

const byte SERVO_BUS_RX_PIN = 2;
const byte SERVO_BUS_TX_PIN = 3;
const byte XIAO_D1_INPUT_PIN = 9;
const byte XIAO_D2_INPUT_PIN = 8;
const byte GREEN_SAFE_LED_PIN = 7;
const byte YELLOW_DANGER_LED_PIN = 6;
const byte RED_POWER_DANGER_LED_PIN = 5;

const int SERVO_SAFE_MIN_POSITION = 1800;
const int SERVO_SAFE_MAX_POSITION = 2300;
const int SERVO_SAFE_MAX_SPEED = 300;

const byte SERVO_INST_PING = 0x01;
const byte SERVO_INST_READ = 0x02;
const byte SERVO_INST_WRITE = 0x03;
const byte SERVO_REG_TORQUE_ENABLE = 40;
const byte SERVO_REG_GOAL_POSITION = 42;
const byte SERVO_REG_GOAL_TIME = 44;
const byte SERVO_REG_GOAL_SPEED = 46;
const byte SERVO_REG_PRESENT_POSITION = 56;

char lineBuffer[LINE_BUFFER_SIZE];
size_t lineLength = 0;

bool logicArmed = false;
unsigned long detectionCount = 0;
float confidenceThreshold = 0.50;
char lastLabel[24] = "none";
float lastConfidence = 0.0;
float lastCenterX = 0.0;
float lastCenterY = 0.0;
float lastWidth = 0.0;
float lastHeight = 0.0;
unsigned long lastBlinkMs = 0;
bool redBlinkState = false;
unsigned long lastSerialStatusMs = 0;
SoftwareSerial servoBus(SERVO_BUS_RX_PIN, SERVO_BUS_TX_PIN);

void sendReady() {
  Serial.print("UNO_READY firmware=");
  Serial.println(FIRMWARE_VERSION);
}

void sendStartupReport() {
  Serial.println("BEGIN_UNO_WIRING_TEST");
  Serial.println("project=Crop Chop PC YOLO to UNO Bridge");
  Serial.print("firmware=");
  Serial.println(FIRMWARE_VERSION);
  Serial.print("baud=");
  Serial.println(BAUD_RATE);
  Serial.print("servo_bus_rx_pin=");
  Serial.println(SERVO_BUS_RX_PIN);
  Serial.print("servo_bus_tx_pin=");
  Serial.println(SERVO_BUS_TX_PIN);
  Serial.println("servo_protocol=Feetech_STS_SMS_serial_bus_assumed");
  Serial.print("xiao_d1_input_pin=");
  Serial.println(XIAO_D1_INPUT_PIN);
  Serial.print("xiao_d2_input_pin=");
  Serial.println(XIAO_D2_INPUT_PIN);
  Serial.print("green_safe_led_pin=");
  Serial.println(GREEN_SAFE_LED_PIN);
  Serial.print("yellow_danger_led_pin=");
  Serial.println(YELLOW_DANGER_LED_PIN);
  Serial.print("red_power_danger_led_pin=");
  Serial.println(RED_POWER_DANGER_LED_PIN);
  Serial.println("commands=HELLO,PING,STATUS,ARM_LOGIC,DISARM_LOGIC,NO_DETECTION,SET_THRESHOLD,DETECTION,SERVO_SCAN,SERVO_PING,SERVO_STATUS,SERVO_TORQUE,SERVO_MOVE_SAFE");
  Serial.println("END_UNO_WIRING_TEST");
}

void sendAck(const char *command) {
  Serial.print("ACK command=");
  Serial.println(command);
}

void sendError(const char *code) {
  Serial.print("ERROR code=");
  Serial.println(code);
}

void servoFlushInput() {
  servoBus.listen();
  while (servoBus.available() > 0) {
    servoBus.read();
  }
}

void servoWritePacket(byte id, byte instruction, const byte *params, byte paramCount) {
  byte length = paramCount + 2;
  byte checksum = id + length + instruction;
  servoBus.write(0xFF);
  servoBus.write(0xFF);
  servoBus.write(id);
  servoBus.write(length);
  servoBus.write(instruction);
  for (byte index = 0; index < paramCount; index++) {
    servoBus.write(params[index]);
    checksum += params[index];
  }
  servoBus.write(~checksum);
  servoBus.flush();
}

bool servoReadReply(byte expectedId, byte *error, byte *params, byte *paramCount, byte maxParams) {
  unsigned long deadline = millis() + SERVO_REPLY_TIMEOUT_MS;
  byte state = 0;
  byte id = 0;
  byte length = 0;
  byte payloadIndex = 0;
  byte payload[16];

  *paramCount = 0;
  *error = 0xFF;
  while (millis() < deadline) {
    if (servoBus.available() <= 0) {
      continue;
    }
    byte value = servoBus.read();
    if (state == 0 && value == 0xFF) {
      state = 1;
    } else if (state == 1 && value == 0xFF) {
      state = 2;
    } else if (state == 2) {
      id = value;
      state = 3;
    } else if (state == 3) {
      length = value;
      payloadIndex = 0;
      state = 4;
    } else if (state == 4) {
      if (payloadIndex < sizeof(payload)) {
        payload[payloadIndex] = value;
      }
      payloadIndex++;
      if (payloadIndex >= length) {
        if (id != expectedId || length < 2) {
          return false;
        }
        byte checksum = id + length;
        for (byte index = 0; index < length - 1 && index < sizeof(payload); index++) {
          checksum += payload[index];
        }
        checksum = ~checksum;
        if (checksum != payload[length - 1]) {
          return false;
        }
        *error = payload[0];
        *paramCount = (length - 2 < maxParams) ? (length - 2) : maxParams;
        for (byte index = 0; index < *paramCount; index++) {
          params[index] = payload[index + 1];
        }
        return true;
      }
    } else {
      state = 0;
    }
  }
  return false;
}

bool servoPing(byte id) {
  byte error;
  byte params[4];
  byte paramCount;
  servoFlushInput();
  servoWritePacket(id, SERVO_INST_PING, nullptr, 0);
  return servoReadReply(id, &error, params, &paramCount, sizeof(params));
}

bool servoReadWord(byte id, byte address, int *value) {
  byte paramsOut[2] = {address, 2};
  byte error;
  byte paramsIn[4];
  byte paramCount;
  servoFlushInput();
  servoWritePacket(id, SERVO_INST_READ, paramsOut, 2);
  if (!servoReadReply(id, &error, paramsIn, &paramCount, sizeof(paramsIn)) || error != 0 || paramCount < 2) {
    return false;
  }
  *value = paramsIn[0] | (paramsIn[1] << 8);
  return true;
}

bool servoWriteByte(byte id, byte address, byte value) {
  byte paramsOut[2] = {address, value};
  byte error;
  byte paramsIn[2];
  byte paramCount;
  servoFlushInput();
  servoWritePacket(id, SERVO_INST_WRITE, paramsOut, 2);
  return servoReadReply(id, &error, paramsIn, &paramCount, sizeof(paramsIn)) && error == 0;
}

bool servoWriteMove(byte id, int position, int speed) {
  byte paramsOut[7];
  byte error;
  byte paramsIn[2];
  byte paramCount;
  paramsOut[0] = SERVO_REG_GOAL_POSITION;
  paramsOut[1] = lowByte(position);
  paramsOut[2] = highByte(position);
  paramsOut[3] = 0;
  paramsOut[4] = 0;
  paramsOut[5] = lowByte(speed);
  paramsOut[6] = highByte(speed);
  servoFlushInput();
  servoWritePacket(id, SERVO_INST_WRITE, paramsOut, 7);
  return servoReadReply(id, &error, paramsIn, &paramCount, sizeof(paramsIn)) && error == 0;
}

void handleServoScan(char *payload) {
  int maxId = atoi(payload);
  if (maxId <= 0 || maxId > 253) {
    maxId = 20;
  }
  Serial.print("SERVO_SCAN_BEGIN max_id=");
  Serial.println(maxId);
  for (byte id = 1; id <= maxId; id++) {
    if (servoPing(id)) {
      Serial.print("SERVO_FOUND id=");
      Serial.println(id);
    }
  }
  Serial.println("SERVO_SCAN_END");
}

void handleServoPing(char *payload) {
  byte id = atoi(payload);
  Serial.print("SERVO_PING id=");
  Serial.print(id);
  Serial.print(" ok=");
  Serial.println(servoPing(id) ? 1 : 0);
}

void handleServoStatus(char *payload) {
  byte id = atoi(payload);
  int position = 0;
  Serial.print("SERVO_STATUS id=");
  Serial.print(id);
  if (servoReadWord(id, SERVO_REG_PRESENT_POSITION, &position)) {
    Serial.print(" ok=1 position=");
    Serial.println(position);
  } else {
    Serial.println(" ok=0");
  }
}

void handleServoTorque(char *payload) {
  int id;
  int enable;
  if (sscanf(payload, "%d %d", &id, &enable) != 2 || id < 1 || id > 253 || enable < 0 || enable > 1) {
    sendError("bad_servo_torque");
    return;
  }
  Serial.print("SERVO_TORQUE id=");
  Serial.print(id);
  Serial.print(" enable=");
  Serial.print(enable);
  Serial.print(" ok=");
  Serial.println(servoWriteByte(id, SERVO_REG_TORQUE_ENABLE, enable ? 1 : 0) ? 1 : 0);
}

void handleServoMoveSafe(char *payload) {
  int id;
  int position;
  int speed;
  if (sscanf(payload, "%d %d %d", &id, &position, &speed) != 3) {
    sendError("bad_servo_move");
    return;
  }
  if (!logicArmed) {
    sendError("servo_logic_disarmed");
    return;
  }
  if (id < 1 || id > 253 || position < SERVO_SAFE_MIN_POSITION || position > SERVO_SAFE_MAX_POSITION || speed < 1 || speed > SERVO_SAFE_MAX_SPEED) {
    sendError("servo_move_outside_safe_limits");
    return;
  }
  Serial.print("SERVO_MOVE_SAFE id=");
  Serial.print(id);
  Serial.print(" position=");
  Serial.print(position);
  Serial.print(" speed=");
  Serial.print(speed);
  Serial.print(" ok=");
  Serial.println(servoWriteMove(id, position, speed) ? 1 : 0);
}

const char *currentDecision() {
  if (logicArmed && lastConfidence >= confidenceThreshold) {
    return "DANGER";
  }
  return "SAFE";
}

void updateStatusLeds() {
  bool danger = strcmp(currentDecision(), "DANGER") == 0;
  unsigned long now = millis();

  digitalWrite(GREEN_SAFE_LED_PIN, danger ? LOW : HIGH);
  digitalWrite(YELLOW_DANGER_LED_PIN, danger ? HIGH : LOW);

  if (danger) {
    if (now - lastBlinkMs >= DANGER_BLINK_INTERVAL_MS) {
      redBlinkState = !redBlinkState;
      lastBlinkMs = now;
    }
    digitalWrite(RED_POWER_DANGER_LED_PIN, redBlinkState ? HIGH : LOW);
  } else {
    redBlinkState = false;
    digitalWrite(RED_POWER_DANGER_LED_PIN, HIGH);
  }
}

void sendStatus() {
  updateStatusLeds();
  Serial.print("STATUS armed=");
  Serial.print(logicArmed ? 1 : 0);
  Serial.print(" xiao_d1=");
  Serial.print(digitalRead(XIAO_D1_INPUT_PIN));
  Serial.print(" xiao_d2=");
  Serial.print(digitalRead(XIAO_D2_INPUT_PIN));
  Serial.print(" detections=");
  Serial.print(detectionCount);
  Serial.print(" last_label=");
  Serial.print(lastLabel);
  Serial.print(" last_confidence=");
  Serial.print(lastConfidence, 3);
  Serial.print(" threshold=");
  Serial.print(confidenceThreshold, 3);
  Serial.print(" decision=");
  Serial.println(currentDecision());
}

void sendTestStatus() {
  updateStatusLeds();
  Serial.print("TEST_STATUS uptime_ms=");
  Serial.print(millis());
  Serial.print(" armed=");
  Serial.print(logicArmed ? 1 : 0);
  Serial.print(" xiao_d1=");
  Serial.print(digitalRead(XIAO_D1_INPUT_PIN));
  Serial.print(" xiao_d2=");
  Serial.print(digitalRead(XIAO_D2_INPUT_PIN));
  Serial.print(" green=");
  Serial.print(digitalRead(GREEN_SAFE_LED_PIN));
  Serial.print(" yellow=");
  Serial.print(digitalRead(YELLOW_DANGER_LED_PIN));
  Serial.print(" red=");
  Serial.print(digitalRead(RED_POWER_DANGER_LED_PIN));
  Serial.print(" detections=");
  Serial.print(detectionCount);
  Serial.print(" confidence=");
  Serial.print(lastConfidence, 3);
  Serial.print(" threshold=");
  Serial.print(confidenceThreshold, 3);
  Serial.print(" decision=");
  Serial.println(currentDecision());
}

void clearDetection() {
  strncpy(lastLabel, "none", sizeof(lastLabel) - 1);
  lastLabel[sizeof(lastLabel) - 1] = '\0';
  lastConfidence = 0.0;
  lastCenterX = 0.0;
  lastCenterY = 0.0;
  lastWidth = 0.0;
  lastHeight = 0.0;
}

void handleDetection(char *payload) {
  char label[24];
  float confidence;
  float centerX;
  float centerY;
  float width;
  float height;

  int parsed = sscanf(payload, "%23s %f %f %f %f %f", label, &confidence, &centerX, &centerY, &width, &height);
  if (parsed != 6) {
    sendError("bad_detection");
    return;
  }

  strncpy(lastLabel, label, sizeof(lastLabel) - 1);
  lastLabel[sizeof(lastLabel) - 1] = '\0';
  lastConfidence = confidence;
  lastCenterX = centerX;
  lastCenterY = centerY;
  lastWidth = width;
  lastHeight = height;
  detectionCount++;
  updateStatusLeds();
  sendStatus();
}

void handleSetThreshold(char *payload) {
  float threshold = atof(payload);
  if (threshold < 0.0 || threshold > 1.0) {
    sendError("bad_threshold");
    return;
  }
  confidenceThreshold = threshold;
  sendAck("SET_THRESHOLD");
  sendStatus();
}

void handleCommand(char *line) {
  if (strcmp(line, "HELLO") == 0) {
    sendReady();
    return;
  }
  if (strcmp(line, "PING") == 0) {
    Serial.print("PONG uptime_ms=");
    Serial.println(millis());
    return;
  }
  if (strcmp(line, "NO_DETECTION") == 0) {
    clearDetection();
    updateStatusLeds();
    sendStatus();
    return;
  }
  if (strcmp(line, "ARM_LOGIC") == 0) {
    logicArmed = true;
    updateStatusLeds();
    sendAck("ARM_LOGIC");
    sendStatus();
    return;
  }
  if (strcmp(line, "DISARM_LOGIC") == 0) {
    logicArmed = false;
    updateStatusLeds();
    sendAck("DISARM_LOGIC");
    sendStatus();
    return;
  }
  if (strcmp(line, "STATUS") == 0) {
    sendStatus();
    return;
  }
  if (strncmp(line, "DETECTION ", 10) == 0) {
    handleDetection(line + 10);
    return;
  }
  if (strncmp(line, "SET_THRESHOLD ", 14) == 0) {
    handleSetThreshold(line + 14);
    return;
  }
  if (strncmp(line, "SERVO_SCAN", 10) == 0) {
    handleServoScan(line + 10);
    return;
  }
  if (strncmp(line, "SERVO_PING ", 11) == 0) {
    handleServoPing(line + 11);
    return;
  }
  if (strncmp(line, "SERVO_STATUS ", 13) == 0) {
    handleServoStatus(line + 13);
    return;
  }
  if (strncmp(line, "SERVO_TORQUE ", 13) == 0) {
    handleServoTorque(line + 13);
    return;
  }
  if (strncmp(line, "SERVO_MOVE_SAFE ", 16) == 0) {
    handleServoMoveSafe(line + 16);
    return;
  }

  sendError("unknown_command");
}

void readSerialLine() {
  while (Serial.available() > 0) {
    char character = Serial.read();
    if (character == '\r') {
      continue;
    }
    if (character == '\n') {
      lineBuffer[lineLength] = '\0';
      if (lineLength > 0) {
        handleCommand(lineBuffer);
      }
      lineLength = 0;
      return;
    }
    if (lineLength < LINE_BUFFER_SIZE - 1) {
      lineBuffer[lineLength++] = character;
    } else {
      lineLength = 0;
      sendError("line_too_long");
    }
  }
}

void setup() {
  pinMode(XIAO_D1_INPUT_PIN, INPUT);
  pinMode(XIAO_D2_INPUT_PIN, INPUT);
  pinMode(GREEN_SAFE_LED_PIN, OUTPUT);
  pinMode(YELLOW_DANGER_LED_PIN, OUTPUT);
  pinMode(RED_POWER_DANGER_LED_PIN, OUTPUT);
  Serial.begin(BAUD_RATE);
  servoBus.begin(1000000);
  clearDetection();
  updateStatusLeds();
  sendReady();
  sendStartupReport();
  sendStatus();
}

void loop() {
  readSerialLine();
  updateStatusLeds();
  if (millis() - lastSerialStatusMs >= SERIAL_STATUS_INTERVAL_MS) {
    lastSerialStatusMs = millis();
    sendTestStatus();
  }
}
