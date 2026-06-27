from src.nudge.cadence import resolve_cadence

def test_defaults_when_rules_absent():
    assert resolve_cadence(None) == ([24, 48], 72)
    assert resolve_cadence({}) == ([24, 48], 72)

def test_reads_rules_when_present():
    rules = {"reminderIntervals": [12, 36], "expiryHours": 60}
    assert resolve_cadence(rules) == ([12, 36], 60)

def test_partial_rules_fall_back_per_field():
    assert resolve_cadence({"reminderIntervals": [6]}) == ([6], 72)
    assert resolve_cadence({"expiryHours": 96}) == ([24, 48], 96)

def test_empty_intervals_falls_back_to_default():
    assert resolve_cadence({"reminderIntervals": []}) == ([24, 48], 72)
