"""
Weather Poller
Polls weather API and triggers nudge workflow for favorable conditions
DEMO MODE: Mocks perfect weather for Aurangabad for reliable demo
"""
import json
import os
import boto3
from typing import Dict, Any, List

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')

TABLE_NAME = os.environ['TABLE_NAME']
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

table = dynamodb.Table(TABLE_NAME)

# DEMO MODE: Mock perfect weather for Aurangabad
MOCK_WEATHER = True


def get_unique_locations() -> List[str]:
    """Get unique locations from user profiles"""
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


def check_weather_mock(location: str) -> Dict[str, Any]:
    """Mock weather for demo - always return perfect conditions for Aurangabad"""
    if location == 'Aurangabad':
        return {
            'location': location,
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
            'wind_speed': 15,
            'rain': 0,
            'favorable': False,
            'mock': True
        }


def check_weather_real(location: str) -> Dict[str, Any]:
    """Real weather API call (disabled for demo)"""
    # TODO: Implement real OpenWeatherMap API call
    # For now, return mock data
    return check_weather_mock(location)


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
