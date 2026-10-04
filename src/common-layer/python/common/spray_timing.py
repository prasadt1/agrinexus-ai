"""
Spray-timing answers from real weather.

The nudge tells a farmer when the weather in their district suits spraying (wind under
10 km/h, no rain). When the farmer asks the same thing ("can I spray today?", "is tomorrow
a good time to spray?"), the answer comes from the same weather source and the same rule,
in fixed sentences, so the model never invents a forecast.

- today: current conditions from OpenWeatherMap, the call the weather poller makes.
- tomorrow: the 3-hourly forecast for tomorrow's early morning in India (slots that fall
  between 05:00 and 11:00 IST), favorable only if every slot has wind under 10 km/h, no rain
  volume and a rain probability of 30% or less.
- Any failure (no key, request error, unusable response) returns None and the reply says
  the weather is not available and states the rule, instead of guessing (REQ-SPRAY-003).

Only the three onboarding districts have coordinates. Other locations get None from
lookups, and the caller falls back to the knowledge base.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

WIND_LIMIT_KMH = 10.0
RAIN_PROBABILITY_LIMIT = 0.3
IST = timezone(timedelta(hours=5, minutes=30))
TOMORROW_WINDOW_IST = (5, 11)  # forecast slots at 05:30 and 08:30 IST

DISTRICT_COORDS = {
    "Latur": {"lat": 18.4088, "lon": 76.5604},
    "Jalna": {"lat": 19.8347, "lon": 75.8816},
    "Nagpur": {"lat": 21.1458, "lon": 79.0882},
}

CURRENT_URL = os.environ.get("WEATHER_API_BASE", "https://api.openweathermap.org/data/2.5/weather")
FORECAST_URL = os.environ.get("WEATHER_FORECAST_BASE", "https://api.openweathermap.org/data/2.5/forecast")

_api_key_cache: Optional[str] = None


def _api_key() -> Optional[str]:
    global _api_key_cache
    if _api_key_cache:
        return _api_key_cache
    secret_id = os.environ.get("WEATHER_API_KEY_SECRET")
    if not secret_id:
        return None
    try:
        import boto3

        _api_key_cache = boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)["SecretString"]
        return _api_key_cache
    except Exception as e:
        print(f"Spray timing: weather API key unavailable: {e}")
        return None


def _get_json(url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Spray timing: weather request failed: {e!r}")
        return None


def district_known(district: Optional[str]) -> bool:
    return bool(district) and district in DISTRICT_COORDS


def current_conditions(district: str, fetch: Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]] = _get_json) -> Optional[Dict[str, Any]]:
    """{'wind_kmh', 'rain_mm', 'favorable'} for the district right now, or None."""
    coords = DISTRICT_COORDS.get(district)
    key = _api_key()
    if not coords or not key:
        return None
    data = fetch(CURRENT_URL, {"lat": coords["lat"], "lon": coords["lon"], "appid": key, "units": "metric"})
    if not data:
        return None
    try:
        wind_kmh = float(data["wind"]["speed"]) * 3.6
    except (KeyError, TypeError, ValueError):
        return None
    rain = data.get("rain") or {}
    rain_mm = float(rain.get("1h", rain.get("3h", 0)) or 0)
    return {"wind_kmh": round(wind_kmh, 1), "rain_mm": rain_mm, "favorable": wind_kmh < WIND_LIMIT_KMH and rain_mm == 0}


def tomorrow_morning_slots(items: List[Dict[str, Any]], now_utc: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Forecast items that fall on tomorrow (IST) between 05:00 and 11:00 IST."""
    now_ist = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    tomorrow = (now_ist + timedelta(days=1)).date()
    out = []
    for item in items:
        try:
            when = datetime.fromtimestamp(int(item["dt"]), tz=timezone.utc).astimezone(IST)
        except (KeyError, TypeError, ValueError):
            continue
        if when.date() == tomorrow and TOMORROW_WINDOW_IST[0] <= when.hour < TOMORROW_WINDOW_IST[1]:
            out.append(item)
    return out


def tomorrow_conditions(
    district: str,
    fetch: Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]] = _get_json,
    now_utc: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """{'wind_kmh', 'rain_mm', 'rain_probability', 'favorable'} for tomorrow morning, or None."""
    coords = DISTRICT_COORDS.get(district)
    key = _api_key()
    if not coords or not key:
        return None
    data = fetch(FORECAST_URL, {"lat": coords["lat"], "lon": coords["lon"], "appid": key, "units": "metric", "cnt": 16})
    if not data:
        return None
    slots = tomorrow_morning_slots(data.get("list") or [], now_utc)
    if not slots:
        return None
    winds, rains, pops = [], [], []
    for slot in slots:
        try:
            winds.append(float(slot["wind"]["speed"]) * 3.6)
        except (KeyError, TypeError, ValueError):
            return None
        rains.append(float((slot.get("rain") or {}).get("3h", 0) or 0))
        pops.append(float(slot.get("pop", 0) or 0))
    wind_kmh, rain_mm, pop = max(winds), max(rains), max(pops)
    return {
        "wind_kmh": round(wind_kmh, 1),
        "rain_mm": rain_mm,
        "rain_probability": pop,
        "favorable": wind_kmh < WIND_LIMIT_KMH and rain_mm == 0 and pop <= RAIN_PROBABILITY_LIMIT,
    }


# --- fixed sentences -------------------------------------------------------------------
# Wording follows the nudge (nudge_copy.py): "<district>: weather is favorable for spraying,
# wind N km/h". The district name is shown as stored (English), as the nudge does.

_TEXT = {
    "hi": {
        "now_ok": "{d}: अभी स्प्रे के लिए मौसम अनुकूल है। हवा {w} km/h है, बारिश नहीं। सुबह या शाम को स्प्रे करें।",
        "now_wind": "{d}: अभी स्प्रे के लिए मौसम अनुकूल नहीं है। हवा {w} km/h है (10 km/h से कम होनी चाहिए)। हवा कम होने पर ही स्प्रे करें।",
        "now_rain": "{d}: अभी बारिश हो रही है, स्प्रे न करें। बारिश रुकने के बाद 3-4 घंटे सूखा रहे तब स्प्रे करें।",
        "tmrw_ok": "{d}: कल सुबह स्प्रे के लिए मौसम अनुकूल रहने की संभावना है। हवा लगभग {w} km/h, बारिश की संभावना कम। सुबह जल्दी स्प्रे करें।",
        "tmrw_wind": "{d}: कल सुबह हवा स्प्रे के लिए ज़्यादा रहने की संभावना है (लगभग {w} km/h; 10 km/h से कम होनी चाहिए)। स्प्रे टालें और सुबह मौसम फिर देखें।",
        "tmrw_rain": "{d}: कल सुबह बारिश की संभावना है ({p}%)। स्प्रे टालें और सुबह मौसम फिर देखें।",
        "unavailable": "{d}: अभी मौसम की जानकारी नहीं मिल पा रही है। स्प्रे से पहले देखें: हवा 10 km/h से कम हो और अगले 3-4 घंटे बारिश न हो।",
        "caveat": "यह जिले का मौसम है; अपने खेत पर हवा और बादल भी देखें।",
    },
    "mr": {
        "now_ok": "{d}: आता फवारणीसाठी हवामान अनुकूल आहे. वारा {w} km/h, पाऊस नाही. सकाळी किंवा संध्याकाळी फवारणी करा.",
        "now_wind": "{d}: आता फवारणीसाठी हवामान अनुकूल नाही. वारा {w} km/h आहे (10 km/h पेक्षा कमी हवा). वारा कमी झाल्यावरच फवारणी करा.",
        "now_rain": "{d}: आता पाऊस पडत आहे, फवारणी करू नका. पाऊस थांबल्यावर 3-4 तास कोरडे राहिल्यास फवारणी करा.",
        "tmrw_ok": "{d}: उद्या सकाळी फवारणीसाठी हवामान अनुकूल राहण्याची शक्यता आहे. वारा सुमारे {w} km/h, पावसाची शक्यता कमी. सकाळी लवकर फवारणी करा.",
        "tmrw_wind": "{d}: उद्या सकाळी वारा फवारणीसाठी जास्त राहण्याची शक्यता आहे (सुमारे {w} km/h; 10 km/h पेक्षा कमी हवा). फवारणी पुढे ढकला आणि सकाळी हवामान पुन्हा पाहा.",
        "tmrw_rain": "{d}: उद्या सकाळी पावसाची शक्यता आहे ({p}%). फवारणी पुढे ढकला आणि सकाळी हवामान पुन्हा पाहा.",
        "unavailable": "{d}: सध्या हवामानाची माहिती मिळत नाही. फवारणीपूर्वी पाहा: वारा 10 km/h पेक्षा कमी असावा आणि पुढील 3-4 तास पाऊस नसावा.",
        "caveat": "हे जिल्ह्याचे हवामान आहे; तुमच्या शेतावर वारा आणि ढग पण पाहा.",
    },
    "te": {
        "now_ok": "{d}: ఇప్పుడు స్ప్రే చేయడానికి వాతావరణం అనుకూలంగా ఉంది. గాలి {w} km/h, వర్షం లేదు. ఉదయం లేదా సాయంత్రం స్ప్రే చేయండి.",
        "now_wind": "{d}: ఇప్పుడు స్ప్రే చేయడానికి వాతావరణం అనుకూలంగా లేదు. గాలి {w} km/h (10 km/h కంటే తక్కువ ఉండాలి). గాలి తగ్గాకే స్ప్రే చేయండి.",
        "now_rain": "{d}: ఇప్పుడు వర్షం పడుతోంది, స్ప్రే చేయవద్దు. వర్షం ఆగాక 3-4 గంటలు పొడిగా ఉంటే స్ప్రే చేయండి.",
        "tmrw_ok": "{d}: రేపు ఉదయం స్ప్రే చేయడానికి వాతావరణం అనుకూలంగా ఉండే అవకాశం ఉంది. గాలి సుమారు {w} km/h, వర్షం అవకాశం తక్కువ. ఉదయం త్వరగా స్ప్రే చేయండి.",
        "tmrw_wind": "{d}: రేపు ఉదయం గాలి స్ప్రేకు ఎక్కువగా ఉండే అవకాశం ఉంది (సుమారు {w} km/h; 10 km/h కంటే తక్కువ ఉండాలి). స్ప్రే వాయిదా వేసి ఉదయం వాతావరణం మళ్ళీ చూడండి.",
        "tmrw_rain": "{d}: రేపు ఉదయం వర్షం అవకాశం ఉంది ({p}%). స్ప్రే వాయిదా వేసి ఉదయం వాతావరణం మళ్ళీ చూడండి.",
        "unavailable": "{d}: ప్రస్తుతం వాతావరణ సమాచారం అందడం లేదు. స్ప్రేకు ముందు చూడండి: గాలి 10 km/h కంటే తక్కువ, తర్వాతి 3-4 గంటలు వర్షం ఉండకూడదు.",
        "caveat": "ఇది జిల్లా వాతావరణం; మీ పొలంలో గాలి, మేఘాలు కూడా చూడండి.",
    },
    "en": {
        "now_ok": "{d}: the weather is favorable for spraying now. Wind {w} km/h, no rain. Spray in the morning or evening.",
        "now_wind": "{d}: the weather is not favorable for spraying now. Wind is {w} km/h (it should be under 10 km/h). Spray only once the wind drops.",
        "now_rain": "{d}: it is raining now, do not spray. Spray once it has stayed dry for 3 to 4 hours after the rain.",
        "tmrw_ok": "{d}: the weather tomorrow morning is likely to be favorable for spraying. Wind about {w} km/h, low chance of rain. Spray early in the morning.",
        "tmrw_wind": "{d}: the wind tomorrow morning is likely to be too high for spraying (about {w} km/h; it should be under 10 km/h). Hold off and check the weather again in the morning.",
        "tmrw_rain": "{d}: rain is likely tomorrow morning ({p}% chance). Hold off and check the weather again in the morning.",
        "unavailable": "{d}: the weather is not available right now. Before spraying, check that the wind is under 10 km/h and no rain is expected for the next 3 to 4 hours.",
        "caveat": "This is the district weather; also check the wind and clouds at your own field.",
    },
}


def _t(dialect: str) -> Dict[str, str]:
    return _TEXT.get((dialect or "en").strip().lower(), _TEXT["en"])


def spray_timing_reply(district: str, dialect: str, day: str, conditions: Optional[Dict[str, Any]]) -> str:
    """Fixed two-sentence answer for 'today' or 'tomorrow' from the looked-up conditions (or None)."""
    t = _t(dialect)
    if conditions is None:
        body = t["unavailable"].format(d=district)
    elif day == "tomorrow":
        if conditions["favorable"]:
            body = t["tmrw_ok"].format(d=district, w=conditions["wind_kmh"])
        elif conditions["rain_mm"] > 0 or conditions.get("rain_probability", 0) > RAIN_PROBABILITY_LIMIT:
            body = t["tmrw_rain"].format(d=district, p=int(round(conditions.get("rain_probability", 0) * 100)))
        else:
            body = t["tmrw_wind"].format(d=district, w=conditions["wind_kmh"])
    else:
        if conditions["favorable"]:
            body = t["now_ok"].format(d=district, w=conditions["wind_kmh"])
        elif conditions["rain_mm"] > 0:
            body = t["now_rain"].format(d=district)
        else:
            body = t["now_wind"].format(d=district, w=conditions["wind_kmh"])
    return f"{body} {t['caveat']}"


def answer_spray_timing(district: str, dialect: str, day: str) -> str:
    """Look up the weather for the day asked and return the fixed reply (never raises)."""
    try:
        conditions = tomorrow_conditions(district) if day == "tomorrow" else current_conditions(district)
    except Exception as e:  # the reply must never fail because of the weather call
        print(f"Spray timing: lookup failed: {e!r}")
        conditions = None
    return spray_timing_reply(district, dialect, day, conditions)
