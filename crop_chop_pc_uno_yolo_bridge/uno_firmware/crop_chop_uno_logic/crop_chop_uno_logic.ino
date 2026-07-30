const unsigned long BAUD_RATE = 115200;
const char *FIRMWARE_VERSION = "0.2.0";
const size_t LINE_BUFFER_SIZE = 96;
const unsigned long DANGER_BLINK_INTERVAL_MS = 250;

const byte XIAO_D1_INPUT_PIN = 9;
const byte XIAO_D2_INPUT_PIN = 8;
const byte GREEN_SAFE_LED_PIN = 7;
const byte YELLOW_DANGER_LED_PIN = 6;
const byte RED_POWER_DANGER_LED_PIN = 5;

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

void sendReady() {
  Serial.print("UNO_READY firmware=");
  Serial.println(FIRMWARE_VERSION);
}

void sendAck(const char *command) {
  Serial.print("ACK command=");
  Serial.println(command);
}

void sendError(const char *code) {
  Serial.print("ERROR code=");
  Serial.println(code);
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
  clearDetection();
  updateStatusLeds();
  sendReady();
}

void loop() {
  readSerialLine();
  updateStatusLeds();
}
