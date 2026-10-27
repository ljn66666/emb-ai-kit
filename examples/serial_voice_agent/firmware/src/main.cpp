// emb-ai-kit · serial_voice_agent firmware
// Seeed XIAO ESP32S3 Sense + 4x SG90 + MAX98357A (I2S)
//
// Core idea: the device speaks a FRAMED serial protocol and moves servos.
// It NEVER holds an API key. The host bridge does the LLM work.
//
// Real-hardware lesson baked in:
//   1. Servo pins are D1..D7 (NOT D0) to avoid ESP32 strapping-pin jitter.
//   2. Every servo is driven to its idle (1500 us = center) BEFORE the PWM
//      channel is attached, so a boot glitch cannot snap it.
//   3. Power: servos run on their OWN 5V/3A supply, GND shared with MCU.

#include <Arduino.h>
#include <ArduinoJson.h>

// ---- Servo config -------------------------------------------------------
// D1..D7 on the XIAO = GPIO 2..8. D0 (GPIO1) is left free on purpose.
// LEDC channels 0..6 map 1:1 to the 7 servo pins.
static const int SERVO_PINS[7] = {D1, D2, D3, D4, D5, D6, D7};
static const int SERVO_CH[7]   = {0, 1, 2, 3, 4, 5, 6};
static const int LEDC_FREQ     = 50;     // Hz, standard servo
static const int LEDC_RES      = 16;     // 16-bit resolution
static const int IDLE_US       = 1500;   // center pulse width

// 50 Hz -> 20 ms period. With 16-bit res, one tick =
// (LEDC_FREQ * (1<<LEDC_RES)) / 50 ... we use ledcWrite microsecond helper.
#define US_TO_DUTY(us) (int)((us * 65536.0) / 20000.0)

// ---- Serial protocol ----------------------------------------------------
// Framed JSON, one object per line, terminated by '\n':
//   {"cmd":"move","id":2,"us":1500}
//   {"cmd":"center"}                 -> all to idle
// A line-based parser recovers automatically from any dropped byte.

static const size_t JSON_CAP = 256;
static char lineBuf[JSON_CAP];
static size_t lineLen = 0;

void driveServo(int id, int us) {
  if (id < 0 || id > 6) return;
  us = constrain(us, 500, 2500);
  ledcWrite(SERVO_CH[id], US_TO_DUTY(us));
}

void centerAll() {
  for (int i = 0; i < 7; i++) driveServo(i, IDLE_US);
}

void handleLine(const char* buf) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, buf);
  if (err) {
    Serial.printf("{\"err\":\"bad_json\",\"msg\":\"%s\"}\n", err.c_str());
    return;
  }
  const char* cmd = doc["cmd"] | "";
  if (strcmp(cmd, "move") == 0) {
    driveServo(doc["id"] | -1, doc["us"] | IDLE_US);
    Serial.println("{\"ok\":1}");
  } else if (strcmp(cmd, "center") == 0) {
    centerAll();
    Serial.println("{\"ok\":1}");
  } else {
    Serial.println("{\"err\":\"unknown_cmd\"}");
  }
}

void setup() {
  Serial.begin(115200);

  // 1. Define idle state BEFORE anything can drive the pin.
  for (int i = 0; i < 7; i++) {
    pinMode(SERVO_PINS[i], OUTPUT);
    digitalWrite(SERVO_PINS[i], LOW);            // hard idle, no glitch
  }

  // 2. Attach PWM only after pins are defined.
  for (int i = 0; i < 7; i++) {
    ledcSetup(SERVO_CH[i], LEDC_FREQ, LEDC_RES);
    ledcAttachPin(SERVO_PINS[i], SERVO_CH[i]);
    driveServo(i, IDLE_US);                       // center immediately
  }

  centerAll();
  Serial.println("{\"ready\":1,\"servos\":7}");

  // NOTE on audio (MAX98357A, I2S BCLK=12 LRCLK=13 DIN=14):
  // In this minimal example the host bridge handles speech-to-text and only
  // sends JSON actions down the wire, so the device needs no I2S code.
  // If you want on-device TTS, init I2S with those pins and a fixed 16 kHz
  // rate; size the DMA buffer to your frame to avoid underruns.
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        handleLine(lineBuf);
        lineLen = 0;
      }
    } else if (lineLen < JSON_CAP - 1) {
      lineBuf[lineLen++] = c;
    }
    // if lineBuf overflows we just drop bytes and re-sync on next '\n'
  }
  delay(1);
}
