"""
Weather Poller
Polls weather API and triggers nudge workflow for favorable conditions
DEMO MODE: Mocks perfect weather for Aurangabad for reliable demo
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

# DEMO MODE: Mock perfect weather for Aurangabad
MOCK_WEATHER = os.environ.get('MOCK_WEATHER', 'false').lower() == 'true'
USE_REAL_WEATHER = os.environ.get('USE_REAL_WEATHER', 'false').lower() == 'true'
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
WEATHER_API_BASE = os.environ.get('WEATHER_API_BASE', 'https://api.openweathermap.org/data/2.5/weather')

# District -> coordinates (approximate; used for geo-based story and weather lookup)
DISTRICT_COORDS = {
    'Aurangabad': {'lat': 19.8762, 'lon': 75.3433},
    'Jalna': {'lat': 19.8347, 'lon': 75.8816},
    'Nagpur': {'lat': 21.1458, 'lon': 79.0882}
}


def get_unique_locations() -> List[str]:
    """Get unique locations from user profiles"""
    locations = set()
    last_evaluated_key = None
    while True:
        scan_kwargs = {
            'FilterExpression': 'begins_with(SK, :sk)',
            'ExpressionAttributeValues': {':sk': 'PROFILE'}
        }
        if last_evaluated_key:
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        for item in response.get('Items', []):
            location = item.get('location')
            if location:
                locations.add(location)

        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break

    return list(locations)


def check_weather_mock(location: str) -> Dict[str, Any]:
    """Mock weather for demo - always return perfect conditions for Aurangabad"""
    coords = DISTRICT_COORDS.get(location)
    if location == 'Aurangabad':
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
    else:
        # For other locations, return unfavorable to focus demo on Aurangabad
        return {
            'location': location,
            'coordinates': coords,
            'wind_speed': 15,
            'rain': 0,
            'favorable': False,
            'mock': True
        }


def check_weather_real(location: str) -> Dict[str, Any]:
    """Real weather API call (disabled for demo)"""
    coords = DISTRICT_COORDS.get(location)
    if not coords or not WEATHER_API_KEY:
        return check_weather_mock(location)

    query = urllib.parse.urlencode({
        'lat': coords['lat'],
        'lon': coords['lon'],
        'appid': WEATHER_API_KEY,
        'units': 'metric'
    })
    url = f\"{WEATHER_API_BASE}?{query}\"

    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
    except Exception:
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
    # Get unique locations
    locations = get_unique_locations()
    print(f"Checking weather for {len(locations)} locations")
    
    favorable_locations = []
    
    # Check weather for each location
    for location in locations:
        if MOCK_WEATHER:
            weather = check_weather_mock(location)
        elif USE_REAL_WEATHER:
            weather = check_weather_real(location)
        else:
            weather = check_weather_real(location)
        
        if weather.get('favorable'):
            favorable_locations.append(weather)
            
            # Trigger nudge workflow
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
