"""
Weather Poller
Polls OpenWeatherMap for current conditions (or optional mock) and triggers the nudge
workflow when spray conditions are favorable (wind < 10 km/h, no recent rain).
Set MOCK_WEATHER=true for deterministic demo weather; production uses real API when key is set.
"""
import json
import os
import boto3
from typing import Dict, Any, List
import urllib.request
import urllib.parse

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')

TABLE_NAME = os.environ['TABLE_NAME']
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

table = dynamodb.Table(TABLE_NAME)

MOCK_WEATHER = os.environ.get('MOCK_WEATHER', 'false').lower() == 'true'
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
WEATHER_API_BASE = os.environ.get('WEATHER_API_BASE', 'https://api.openweathermap.org/data/2.5/weather')

# District -> coordinates (approximate; used for geo-based story and weather lookup)
DISTRICT_COORDS = {
    'Latur': {'lat': 18.4088, 'lon': 76.5604},
    'Jalna': {'lat': 19.8347, 'lon': 75.8816},
    'Nagpur': {'lat': 21.1458, 'lon': 79.0882},
}


def get_unique_locations() -> List[str]:
    """
    Get unique locations from user profiles.
    Uses GSI1 query instead of full table scan to reduce DynamoDB costs.
    GSI1PK is set to LOCATION#{location} for all user profiles.
    """
    locations = set()

    for district in DISTRICT_COORDS.keys():
        try:
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :pk',
                ExpressionAttributeValues={':pk': f'LOCATION#{district}'},
                Limit=1
            )
            if response.get('Items'):
                locations.add(district)
        except Exception as e:
            print(f"Error querying GSI1 for {district}: {e}")
            locations.add(district)

    return list(locations)


def check_weather_mock(location: str) -> Dict[str, Any]:
    """Mock weather for demo - always return perfect conditions for all configured locations"""
    coords = DISTRICT_COORDS.get(location)
    if location in DISTRICT_COORDS:
        return {
            'location': location,
            'coordinates': coords,
            'wind_speed': 8.5,  # km/h (< 10)
            'rain': 0,
            'temperature': 28,
            'humidity': 65,
            'favorable': True,
            'mock': True
        }
    return {
        'location': location,
        'coordinates': coords,
        'wind_speed': 15,
        'rain': 0,
        'favorable': False,
        'mock': True
    }


def check_weather_real(location: str) -> Dict[str, Any]:
    """Fetch current weather from OpenWeatherMap; fall back to mock on missing key or HTTP errors."""
    coords = DISTRICT_COORDS.get(location)
    if not coords:
        print(f"Weather: no coordinates for {location}, using mock")
        return check_weather_mock(location)
    if not WEATHER_API_KEY:
        print("Weather: WEATHER_API_KEY not set, using mock fallback")
        return check_weather_mock(location)

    query = urllib.parse.urlencode({
        'lat': coords['lat'],
        'lon': coords['lon'],
        'appid': WEATHER_API_KEY,
        'units': 'metric'
    })
    url = f"{WEATHER_API_BASE}?{query}"

    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
    except Exception as e:
        print(f"Weather: OpenWeatherMap request failed ({e!r}), using mock fallback")
        return check_weather_mock(location)

    wind_mps = float(data.get('wind', {}).get('speed', 0))
    wind_kmh = wind_mps * 3.6
    rain_mm = 0
    if 'rain' in data:
        rain_mm = data['rain'].get('1h', data['rain'].get('3h', 0)) or 0

    temperature = float(data.get('main', {}).get('temp', 0))
    humidity = float(data.get('main', {}).get('humidity', 0))

    favorable = wind_kmh < 10 and rain_mm == 0

    return {
        'location': location,
        'coordinates': coords,
        'wind_speed': round(wind_kmh, 1),
        'rain': rain_mm,
        'temperature': temperature,
        'humidity': humidity,
        'favorable': favorable,
        'mock': False
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Poll weather and trigger nudge workflow"""
    if not STATE_MACHINE_ARN:
        print("Weather poller: STATE_MACHINE_ARN not set, skipping nudge triggers")
        return {
            'statusCode': 200,
            'skipped': True,
            'reason': 'STATE_MACHINE_ARN missing',
            'locations_checked': 0,
            'favorable_locations': 0,
            'details': [],
            'mock_mode': MOCK_WEATHER
        }

    locations = get_unique_locations()
    print(f"Checking weather for {len(locations)} locations")

    favorable_locations = []

    for location in locations:
        if MOCK_WEATHER:
            weather = check_weather_mock(location)
        else:
            weather = check_weather_real(location)

        if weather.get('favorable'):
            favorable_locations.append(weather)

            stepfunctions.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps({
                    'location': location,
                    'weather': weather,
                    'activity': 'spray'
                })
            )

            print(f"Triggered nudge workflow for {location}")

    return {
        'statusCode': 200,
        'locations_checked': len(locations),
        'favorable_locations': len(favorable_locations),
        'details': favorable_locations,
        'mock_mode': MOCK_WEATHER
    }
