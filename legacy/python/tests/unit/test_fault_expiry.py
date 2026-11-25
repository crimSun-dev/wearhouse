from app.weather import FaultState


def test_demo_fault_expires_after_ten_minutes(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.weather.time.monotonic", lambda: clock[0])
    fault = FaultState("timeout")
    assert fault.mode == "timeout"
    clock[0] += 600
    assert fault.mode == "none"
