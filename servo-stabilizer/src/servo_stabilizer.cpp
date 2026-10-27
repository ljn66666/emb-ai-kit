#include "servo_stabilizer.h"

ServoStabilizer::ServoStabilizer(const Config& cfg) : cfg_(cfg) {}

int ServoStabilizer::maxConcurrent() const {
  // budget = supply * safety; how many stall-class servos can share it?
  // +1e-6 guards against float error (e.g. 3.0*0.7/0.7 == 2.99999.. -> floor 2).
  int n = (int)(cfg_.supply_amps * cfg_.safety / cfg_.servo_stall_amps + 1e-6f);
  return n < 1 ? 1 : n;
}

ServoStabilizer::Slot* ServoStabilizer::find(uint8_t id) {
  if (id >= MAX) return nullptr;
  return &slots_[id];
}

bool ServoStabilizer::attach(uint8_t id, int pin) {
  if (id >= MAX) return false;
  Slot& s = slots_[id];
  // Prime the idle pulse BEFORE attaching so the horn never snaps on power-up.
  s.srv.writeMicroseconds(cfg_.idle_us);
  s.srv.attach(pin);
  s.srv.writeMicroseconds(cfg_.idle_us);  // re-assert after attach
  s.pin = pin;
  s.target = cfg_.idle_us;
  s.registered = true;
  return true;
}

int ServoStabilizer::activeCount() const {
  int n = 0;
  for (uint8_t i = 0; i < MAX; i++)
    if (slots_[i].registered && slots_[i].active) n++;
  return n;
}

bool ServoStabilizer::requestMove(uint8_t id, int us) {
  if (id >= MAX) return false;
  Slot& s = slots_[id];
  if (!s.registered) return false;
  if (us < 500 || us > 2500) return false;       // out of physical range
  // Throttle: respect stagger window AND current budget.
  if (millis() - last_start_ < cfg_.stagger_ms) return false;
  if (activeCount() >= maxConcurrent()) return false;
  s.target = us;
  s.active = true;
  s.done_at = millis() + cfg_.settle_ms;
  s.srv.writeMicroseconds(us);
  last_start_ = millis();
  return true;
}

void ServoStabilizer::update() {
  unsigned long now = millis();
  for (uint8_t i = 0; i < MAX; i++) {
    if (!slots_[i].registered || !slots_[i].active) continue;
    if ((long)(now - slots_[i].done_at) >= 0) {
      slots_[i].active = false;  // budget released after settle
    }
  }
}

int ServoStabilizer::lastUs(uint8_t id) const {
  if (id >= MAX) return 0;
  return slots_[id].target;
}

bool ServoStabilizer::isMoving(uint8_t id) const {
  if (id >= MAX) return false;
  return slots_[id].active;
}
