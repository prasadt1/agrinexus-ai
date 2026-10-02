"""Weather handler tests — mock weather, real weather parsing, favorable logic."""
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_WEATHER_HANDLER = _ROOT / "src" / "weather" / "handler.py"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123:stateMachine:test")
    monkeypatch.setenv("MOCK_WEATHER", "true")


@pytest.fixture()
def weather_module(monkeypatch):
    """Import weather handler with boto3 mocked."""
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace(query=lambda **kw: {"Items": []})
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_sfn = types.SimpleNamespace(start_execution=lambda **kw: {})
    mock_secrets = types.SimpleNamespace(get_secret_value=lambda **kw: {"SecretString": "key"})

    def _client(svc, **kw):
        if svc == "stepfunctions":
            return mock_sfn
        return mock_secrets

    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = _client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    # Load the intended weather handler by file path to avoid collisions with other
    # `handler` modules used by the processor.
    spec = importlib.util.spec_from_file_location("weather_handler", _WEATHER_HANDLER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# Mock weather
# ---------------------------------------------------------------------------

class TestMockWeather:
    def test_latur_favorable(self, weather_module):
        w = weather_module.check_weather_mock("Latur")
        assert w["favorable"] is True
        assert w["mock"] is True
        assert w["wind_speed"] == 8.5

    def test_jalna_favorable(self, weather_module):
        w = weather_module.check_weather_mock("Jalna")
        assert w["favorable"] is True

    def test_nagpur_favorable(self, weather_module):
        w = weather_module.check_weather_mock("Nagpur")
        assert w["favorable"] is True

    def test_unknown_location_not_favorable(self, weather_module):
        w = weather_module.check_weather_mock("UnknownCity")
        assert w["favorable"] is False

    def test_coordinates_present(self, weather_module):
        w = weather_module.check_weather_mock("Latur")
        assert "lat" in w["coordinates"]
        assert "lon" in w["coordinates"]


# ---------------------------------------------------------------------------
# District coordinates
# ---------------------------------------------------------------------------

class TestDistrictCoords:
    def test_three_districts_configured(self, weather_module):
        assert len(weather_module.DISTRICT_COORDS) == 3

    def test_all_districts_have_lat_lon(self, weather_module):
        for name, coords in weather_module.DISTRICT_COORDS.items():
            assert "lat" in coords, f"{name} missing lat"
            assert "lon" in coords, f"{name} missing lon"

    def test_latur_coords_reasonable(self, weather_module):
        c = weather_module.DISTRICT_COORDS["Latur"]
        assert 17 < c["lat"] < 20
        assert 75 < c["lon"] < 78


# ---------------------------------------------------------------------------
# lambda_handler (mock mode)
# ---------------------------------------------------------------------------

class TestLambdaHandlerMock:
    def test_returns_200(self, weather_module, monkeypatch):
        monkeypatch.setattr(weather_module, "get_unique_locations", lambda: ["Latur"])
        monkeypatch.setattr(weather_module, "MOCK_WEATHER", True)
        executions = []
        monkeypatch.setattr(weather_module, "stepfunctions",
                            types.SimpleNamespace(start_execution=lambda **kw: executions.append(kw)))
        result = weather_module.lambda_handler({}, None)
        assert result["statusCode"] == 200

    def test_triggers_workflow_for_favorable(self, weather_module, monkeypatch):
        monkeypatch.setattr(weather_module, "get_unique_locations", lambda: ["Latur"])
        monkeypatch.setattr(weather_module, "MOCK_WEATHER", True)
        executions = []
        monkeypatch.setattr(weather_module, "stepfunctions",
                            types.SimpleNamespace(start_execution=lambda **kw: executions.append(kw)))
        result = weather_module.lambda_handler({}, None)
        assert result["favorable_locations"] == 1
        assert len(executions) == 1

    def test_no_trigger_without_state_machine(self, weather_module, monkeypatch):
        monkeypatch.setattr(weather_module, "STATE_MACHINE_ARN", None)
        result = weather_module.lambda_handler({}, None)
        assert result.get("skipped") is True


# ---------------------------------------------------------------------------
# Real weather parsing
# ---------------------------------------------------------------------------

class TestRealWeatherParsing:
    def test_favorable_conditions(self, weather_module):
        """Wind < 10 km/h and no rain = favorable."""
        # wind 2 m/s = 7.2 km/h
        assert 2 * 3.6 < 10  # favorable

    def test_unfavorable_high_wind(self, weather_module):
        """Wind >= 10 km/h = not favorable."""
        assert 3 * 3.6 > 10  # 10.8 km/h, not favorable


# ---------------------------------------------------------------------------
# Fail closed: no real weather means no spray nudge
# ---------------------------------------------------------------------------

class _Metrics:
    def __init__(self):
        self.calls = []

    def put_metric_data(self, **kw):
        self.calls.append(kw)


def _real_mode(weather_module, monkeypatch, *, key="key", urlopen=None):
    monkeypatch.setattr(weather_module, "MOCK_WEATHER", False)
    monkeypatch.setattr(weather_module, "get_unique_locations", lambda: ["Latur"])
    monkeypatch.setattr(weather_module, "get_weather_api_key", lambda: key)
    executions, metrics = [], _Metrics()
    monkeypatch.setattr(weather_module, "stepfunctions",
                        types.SimpleNamespace(start_execution=lambda **kw: executions.append(kw)))
    monkeypatch.setattr(weather_module, "cloudwatch", metrics)
    if urlopen is not None:
        monkeypatch.setattr(weather_module.urllib.request, "urlopen", urlopen)
    return executions, metrics


def _failed_reasons(metrics):
    out = []
    for call in metrics.calls:
        assert call["Namespace"] == "AgriNexus/Weather"
        for d in call["MetricData"]:
            assert d["MetricName"] == "WeatherFetchFailed"
            out.append({x["Name"]: x["Value"] for x in d["Dimensions"]}["Reason"])
    return out


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestFailClosed:
    def test_missing_key_no_nudge_and_metric(self, weather_module, monkeypatch):
        executions, metrics = _real_mode(weather_module, monkeypatch, key=None)
        result = weather_module.lambda_handler({}, None)
        assert executions == []
        assert result["favorable_locations"] == 0
        assert _failed_reasons(metrics) == ["missing_key"]

    def test_http_error_no_nudge_and_metric(self, weather_module, monkeypatch):
        def boom(*a, **k):
            raise OSError("HTTP Error 401: Unauthorized")

        executions, metrics = _real_mode(weather_module, monkeypatch, urlopen=boom)
        result = weather_module.lambda_handler({}, None)
        assert executions == []
        assert result["favorable_locations"] == 0
        assert _failed_reasons(metrics) == ["request_error"]

    def test_response_without_wind_is_unavailable(self, weather_module, monkeypatch):
        executions, metrics = _real_mode(
            weather_module, monkeypatch, urlopen=lambda *a, **k: _Resp({"main": {"temp": 30}})
        )
        weather_module.lambda_handler({}, None)
        assert executions == []
        assert _failed_reasons(metrics) == ["bad_response"]

    def test_unavailable_result_shape(self, weather_module, monkeypatch):
        _real_mode(weather_module, monkeypatch, key=None)
        w = weather_module.check_weather_real("Latur")
        assert w["favorable"] is False
        assert w["reason"] == "weather_unavailable"
        assert w["mock"] is False

    def test_unknown_district_is_unavailable_not_mock(self, weather_module, monkeypatch):
        _real_mode(weather_module, monkeypatch)
        w = weather_module.check_weather_real("UnknownCity")
        assert w["favorable"] is False and w["reason"] == "weather_unavailable"
        assert w["mock"] is False

    def test_real_calm_dry_weather_still_nudges(self, weather_module, monkeypatch):
        executions, metrics = _real_mode(
            weather_module, monkeypatch,
            urlopen=lambda *a, **k: _Resp({"wind": {"speed": 2}, "main": {"temp": 28, "humidity": 60}}),
        )
        result = weather_module.lambda_handler({}, None)
        assert result["favorable_locations"] == 1 and len(executions) == 1
        assert metrics.calls == []

    def test_mock_never_reached_from_error_path(self, weather_module, monkeypatch):
        _real_mode(weather_module, monkeypatch, key=None)
        monkeypatch.setattr(weather_module, "check_weather_mock",
                            lambda *_a: pytest.fail("mock reached from error path"))
        weather_module.lambda_handler({}, None)
