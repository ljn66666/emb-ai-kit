"""Host-side mirror of the servo-stabilizer throttle math.

This is the exact same budget/stagger logic as servo_stabilizer.cpp, written in
pure Python so it can be unit-tested without any hardware. The MCU firmware and
this scheduler agree on one rule:

    never let  active_servos * stall_current  exceed  supply * safety

Run the tests with:  python -m pytest tests/   (or just `python tests/test_scheduler.py`)
"""

from __future__ import annotations


class ServoStabilizer:
    def __init__(
        self,
        supply_amps: float = 3.0,
        servo_stall_amps: float = 0.7,
        safety: float = 0.7,
        settle_ms: int = 250,
        stagger_ms: int = 60,
    ):
        self.supply = supply_amps
        self.stall = servo_stall_amps
        self.safety = safety
        self.settle = settle_ms
        self.stagger = stagger_ms
        self.slots: dict[int, dict] = {}
        self.last_start = -10_000_000  # far in the past

    # ---- config-derived ----
    def max_concurrent(self) -> int:
        # +1e-9 guards float error (e.g. 3.0*0.7/0.7 == 2.9999.. -> floor 2)
        n = int(self.supply * self.safety / self.stall + 1e-9)
        return max(1, n)

    # ---- lifecycle ----
    def attach(self, sid: int, pin=None) -> bool:
        self.slots[sid] = {"target": 1500, "active": False, "done_at": 0}
        return True

    def active_count(self, now: int) -> int:
        return sum(1 for s in self.slots.values() if s["active"] and now < s["done_at"])

    # ---- the throttle gate ----
    def request_move(self, sid: int, us: int, now: int) -> bool:
        if sid not in self.slots:
            return False
        if not (500 <= us <= 2500):
            return False
        if now - self.last_start < self.stagger:
            return False
        if self.active_count(now) >= self.max_concurrent():
            return False
        self.slots[sid]["target"] = us
        self.slots[sid]["active"] = True
        self.slots[sid]["done_at"] = now + self.settle
        self.last_start = now
        return True

    def update(self, now: int) -> None:
        for s in self.slots.values():
            if s["active"] and now >= s["done_at"]:
                s["active"] = False
