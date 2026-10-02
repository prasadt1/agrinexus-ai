"""
Weather Poller
Polls OpenWeatherMap for current conditions and triggers the nudge workflow when spray
conditions are favorable (wind < 10 km/h, no recent rain).

Fails closed: a missing key, request error or unusable response means no nudge for that
district and an AgriNexus/Weather WeatherFetchFailed metric. Mock weather is used only
when MOCK_WEATHER=true is set explicitly, never as an error fallback.
"""
import json
import os
import boto3
from typing import Dict, Any, List
import urllib.request
import urllib.parse

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')
secretsmanager = boto3.client('secretsmanager')
cloudwatch = boto3.client('cloudwatch')

TABLE_NAME = os.environ['TABLE_NAME']
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

table = dynamodb.Table(TABLE_NAME)

MOCK_WEATHER = os.environ.get('MOCK_WEATHER', 'false').lower() == 'true'
WEATHER_API_KEY_SECRET = os.environ.get('WEATHER_API_KEY_SECRET')
WEATHER_API_BASE = os.environ.get('WEATHER_API_BASE', 'https://api.openweathermap.org/data/2.5/weather')

# Cache the API key to avoid repeated Secrets Manager calls
_weather_api_key_cache = None

def get_weather_api_key() -> str:
    """Get weather API key from Secrets Manager (with caching)"""
    global _weather_api_key_cache
    
    if _weather_api_key_cache:
        return _weather_api_key_cache
    
    if not WEATHER_API_KEY_SECRET:
        return None
    
    try:
        response = secretsmanager.get_secret_value(SecretId=WEATHER_API_KEY_SECRET)
        _weather_api_key_cache = response['SecretString']
        return _weather_api_key_cache
    except Exception as e:
        print(f"Error fetching weather API key from Secrets Manager: {e}")
        return None

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


def _weather_unavailable(location: str, reason: str) -> Dict[str, Any]:
    print(f"Weather unavailable for {location}: {reason}; no nudge this cycle")
    try:
        cloudwatch.put_metric_data(
            Namespace='AgriNexus/Weather',
            MetricData=[{
                'MetricName': 'WeatherFetchFailed',
                'Dimensions': [
                    {'Name': 'Location', 'Value': location},
                    {'Name': 'Reason', 'Value': reason},
                ],
                'Value': 1,
                'Unit': 'Count',
            }],
        )
    except Exception as e:
        print(f"Weather: failed to emit WeatherFetchFailed metric: {e!r}")
    return {
        'location': location,
        'coordinates': DISTRICT_COORDS.get(location),
        'favorable': False,
        'reason': 'weather_unavailable',
        'mock': False,
    }


def check_weather_real(location: str) -> Dict[str, Any]:
    """Fetch current weather from OpenWeatherMap. Any failure is unfavorable."""
    coords = DISTRICT_COORDS.get(location)
    if not coords:
        return _weather_unavailable(location, 'no_coordinates')

    weather_api_key = get_weather_api_key()
    if not weather_api_key:
        return _weather_unavailable(location, 'missing_key')

    query = urllib.parse.urlencode({
        'lat': coords['lat'],
        'lon': coords['lon'],
        'appid': weather_api_key,
        'units': 'metric'
    })
    url = f"{WEATHER_API_BASE}?{query}"

    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
    except Exception as e:
        print(f"Weather: OpenWeatherMap request failed ({e!r})")
        return _weather_unavailable(location, 'request_error')

    try:
        wind_mps = float(data['wind']['speed'])
    except (KeyError, TypeError, ValueError):
        return _weather_unavailable(location, 'bad_response')
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

    if MOCK_WEATHER:
        print("Weather poller: MOCK_WEATHER=true, using demo weather (not real conditions)")

    for location in locations:
        if MOCK_WEATHER:
            weather = check_weather_mock(location)
        else:
            weather = check_weather_real(location)

        if weather.get('favorable'):
            favorable_locations.append(weather)

            workflow_input = {
                'location': location,
                'weather': weather,
                'activity': 'spray'
            }
            if (event or {}).get('force') is True:
                workflow_input['force'] = True
            stepfunctions.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps(workflow_input)
            )

            print(f"Triggered nudge workflow for {location}")

    return {
        'statusCode': 200,
        'locations_checked': len(locations),
        'favorable_locations': len(favorable_locations),
        'details': favorable_locations,
        'mock_mode': MOCK_WEATHER
    }
