#ifndef SERVO_STABILIZER_H
#define SERVO_STABILIZER_H
#include <Arduino.h>
#include <Servo.h>

// servo-stabilizer — kill the two silent servo killers on real hardware:
//   1) boot-state jitter  (horn snaps on power-on)
//   2) power brownout     (too many servos move at once, rail collapses)
// The C++ class runs on the MCU; the same throttle math is mirrored in
// servo-stabilizer/python/scheduler.py so it can be unit-tested without hardware.

class ServoStabilizer {
public:
  struct Config {
    int idle_us = 1500;             // pulse written BEFORE attach — kills boot jitter
    float supply_amps = 3.0f;       // current available to the servo rail
    float servo_stall_amps = 0.7f;  // per-servo current draw at stall (~SG90)
    float safety = 0.7f;            // keep peak demand under this fraction of supply
    unsigned long settle_ms = 250;  // a servo counts as "active" this long after a move
    unsigned long stagger_ms = 60;  // min gap between starting two moves
  };

  static const uint8_t MAX = 16;

  explicit ServoStabilizer(const Config& cfg = Config());

  // Attach and write idle FIRST, before any motion. Prevents the power-on snap.
  bool attach(uint8_t id, int pin);

  // Request a move. Returns false if the current budget can't take another
  // concurrent move right now (or within the stagger window) — caller retries.
  bool requestMove(uint8_t id, int us);

  // Call every loop(). Releases a servo's budget once it has settled.
  void update();

  int  lastUs(uint8_t id) const;
  bool isMoving(uint8_t id) const;
  int  maxConcurrent() const;

private:
  struct Slot {
    int pin = -1;
    Servo srv;
    int target = 1500;
    bool active = false;
    bool registered = false;
    unsigned long done_at = 0;
  };
  Config cfg_;
  Slot slots_[MAX];
  unsigned long last_start_ = 0;

  int activeCount() const;
  Slot* find(uint8_t id);
};

#endif
