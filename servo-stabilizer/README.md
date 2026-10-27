# servo-stabilizer

The code behind emb-ai-kit's two hardest servo lessons — the ones that waste a
weekend and never show up in a simulator:

1. **Boot-state jitter** — the horn snaps to a random angle the instant you power
   on, because the PWM channel attaches at an undefined value. Fixed by writing
   the idle pulse (1500 µs = center) **before** attaching.
2. **Power brownout** — drive too many servos at once and the rail collapses, the
   MCU reboots, *"it resets whenever it moves."* Fixed by a current-aware
   scheduler that never lets concurrent stall-current exceed the supply budget.

## The rule

```
active_servos × stall_current  ≤  supply_amps × safety
```

With 4× SG90 (0.7 A stall) on a 3 A supply at 0.7 safety → at most **3 servos
move at the same time**; the 4th waits its turn. The scheduler also enforces a
minimum stagger between moves, because even within budget, slamming the rail with
four simultaneous inrushes is what tips it over.

## C++ (runs on the MCU)

```cpp
#include <servo_stabilizer.h>

ServoStabilizer::Config cfg;
cfg.supply_amps = 3.0;        // dedicated servo supply, NOT the MCU's 5 V
ServoStabilizer stab(cfg);

void setup() {
  // attach writes idle BEFORE the horn can snap
  stab.attach(0, D1);
  stab.attach(1, D2);
  stab.attach(2, D3);
  stab.attach(3, D4);
}

void loop() {
  // requestMove returns false if the budget is full right now — just retry
  if (!stab.requestMove(2, 2000)) { /* retry next tick */ }
  stab.update();  // releases budget after each move settles
  delay(20);
}
```

> `servo_stabilizer.cpp/.h` compile against the standard Arduino `Servo` library
> (ESP32/AVR/STM32 cores). Flash-tested on Seeed XIAO ESP32S3 Sense with 4× SG90.

## Python mirror (unit-tested without hardware)

`python/scheduler.py` is the **same throttle math** in pure Python, so the logic
is verifiable on any machine:

```bash
python servo-stabilizer/tests/test_scheduler.py
# ALL servo-stabilizer scheduler tests PASSED
```

It proves the invariant: at no instant does the concurrent active count exceed
`maxConcurrent()`, even when a 4th move is requested simultaneously.

## Why this is a product, not a doc

`emb-ai-kit` documents the pitfalls; `servo-stabilizer` **ships the fix as
importable code**. For a client building a multi-servo product, this is the
library that keeps their device from rebooting in the field — the kind of
"boring but critical" firmware that's worth paying for.
