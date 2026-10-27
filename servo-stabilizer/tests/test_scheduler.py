"""Unit tests for the servo-stabilizer throttle scheduler.

Run:  python tests/test_scheduler.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from scheduler import ServoStabilizer


def test_budget_limits_concurrent_moves():
    # 3 A supply, 0.7 A/servo, 0.7 safety -> max 3 concurrent
    ss = ServoStabilizer(supply_amps=3.0)
    for i in range(4):
        ss.attach(i)
    assert ss.max_concurrent() == 3

    # Stagger the requests 70 ms apart so the *stagger* gate doesn't block them,
    # but keep all "active" (settle=250) so the *budget* gate is what bites.
    assert ss.request_move(0, 1500, now=0)   is True
    assert ss.request_move(1, 1500, now=70)  is True
    assert ss.request_move(2, 1500, now=140) is True
    assert ss.request_move(3, 1500, now=210) is False  # budget full: 3 already active
    assert ss.active_count(210) == 3  # invariant: never exceed the budget


def test_rejected_move_retries_after_settle():
    ss = ServoStabilizer(supply_amps=3.0)
    for i in range(4):
        ss.attach(i)
    ss.request_move(0, 1500, now=0)
    ss.request_move(1, 1500, now=70)
    ss.request_move(2, 1500, now=140)
    # 3 accepted, 4th rejected at 210 due to budget; let everything settle
    ss.update(400)
    assert ss.active_count(400) == 0
    assert ss.request_move(3, 1500, now=400) is True


def test_out_of_range_rejected():
    ss = ServoStabilizer()
    ss.attach(0)
    assert ss.request_move(0, 9999, now=1000) is False
    assert ss.request_move(0, 1500, now=1000) is True


def test_stagger_window():
    ss = ServoStabilizer(stagger_ms=60)
    ss.attach(0)
    ss.attach(1)
    assert ss.request_move(0, 1500, now=0) is True
    assert ss.request_move(1, 1500, now=10) is False  # inside stagger window
    assert ss.request_move(1, 1500, now=70) is True


def test_single_servo_always_fits():
    ss = ServoStabilizer(supply_amps=0.8)  # tiny supply, still >=1 allowed
    ss.attach(0)
    assert ss.max_concurrent() == 1
    assert ss.request_move(0, 1500, now=0) is True


if __name__ == "__main__":
    test_budget_limits_concurrent_moves()
    test_rejected_move_retries_after_settle()
    test_out_of_range_rejected()
    test_stagger_window()
    test_single_servo_always_fits()
    print("ALL servo-stabilizer scheduler tests PASSED")
