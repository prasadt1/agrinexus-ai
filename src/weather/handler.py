"""
Weather Poller
Polls weather API and triggers nudge workflow for favorable conditions
"""
import json
import os
import boto3
import requests
from typing import Dict, Any, List

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')
secrets = boto3.client('secretsmanager')

TABLE_NAME = os.environ['TABLE_NAME']
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

table = dynamodb.Table(TABLE_NAME)


def get_weather_api_key() -> Dict[str, str]:
    """Get weather API credentials from Secrets Manager"""
    response = secrets.get_secret_value(SecretId='agrinexus-weather-dev')
    return json.loads(response['SecretString'])


def get_unique_locations() -> List[str]:
    """Get unique locations from user profiles"""
    # Query GSI1 to get all users grouped by location
    response = table.scan(
        FilterExpression='begins_with(SK, :sk)',
        ExpressionAttributeValues={':sk': 'PROFILE'}
    )
    
    locations = set()
    for item in response.get('Items', []):
        location = item.get('location')
        if location:
            locations.add(location)
    
    return list(locations)


def check_weather(location: str, api_key: str, base_url: str) -> Dict[str, Any]:
    """Check weather conditions for location"""
    try:
        response = requests.get(
            f"{base_url}/weather",
            params={
                'q': location,
                'appid': api_key,
                'units': 'metric'
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        wind_speed = data.get('wind', {}).get('speed', 0) * 3.6  # m/s to km/h
        rain = data.get('rain', {}).get('1h', 0)
        
        return {
            'location': location,
            'wind_speed': wind_speed,
            'rain': rain,
            'favorable': wind_speed < 10 and rain == 0
        }
    except Exception as e:
        print(f"Error checking weather for {location}: {e}")
        return {
            'location': location,
            'error': str(e),
            'favorable': False
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Poll weather and trigger nudge workflow"""
    # Get weather API credentials
    weather_creds = get_weather_api_key()
    api_key = weather_creds['API_KEY']
    base_url = weather_creds['BASE_URL']
    
    # Get unique locations
    locations = get_unique_locations()
    print(f"Checking weather for {len(locations)} locations")
    
    favorable_locations = []
    
    # Check weather for each location
    for location in locations:
        weather = check_weather(location, api_key, base_url)
        
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
        'details': favorable_locations
    }
