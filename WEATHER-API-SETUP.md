# Weather API Setup Guide

AgriNexus uses real-time weather data from OpenWeatherMap to trigger timely farming advice.

## Getting Your Free API Key

1. **Sign up at OpenWeatherMap**
   - Visit: https://openweathermap.org/api
   - Click "Sign Up" (top right)
   - Create a free account

2. **Get Your API Key**
   - After signup, go to: https://home.openweathermap.org/api_keys
   - Your default API key will be shown
   - Copy the key (it looks like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`)

3. **Activate Your Key**
   - New API keys take 10-15 minutes to activate
   - Test it at: `https://api.openweathermap.org/data/2.5/weather?lat=19.8762&lon=75.3433&appid=YOUR_KEY`

## Free Tier Limits

- **60 calls/minute**
- **1,000,000 calls/month**
- Perfect for AgriNexus (checks weather every 6 hours)

## Configure AgriNexus

### Option 1: During Deployment
```bash
sam deploy --parameter-overrides WeatherApiKey=YOUR_API_KEY
```

### Option 2: Update Existing Stack
```bash
aws lambda update-function-configuration \
  --function-name agrinexus-weather-dev \
  --environment "Variables={WEATHER_API_KEY=YOUR_API_KEY,MOCK_WEATHER=false}"
```

### Option 3: AWS Console
1. Go to Lambda → `agrinexus-weather-dev`
2. Configuration → Environment variables
3. Edit → Add `WEATHER_API_KEY` = your key
4. Set `MOCK_WEATHER` = `false`
5. Save

## Testing

### Quick invoke (OpenWeatherMap path)

Run the weather poller manually:
```bash
aws lambda invoke \
  --function-name agrinexus-weather-dev \
  --payload '{}' \
  response.json && cat response.json
```

- With **`MOCK_WEATHER=false`** and a valid **`WEATHER_API_KEY`**, expect **`"mock_mode": false`** at the top level.
- In **`details`**, each entry should include **`"mock": false`** when the API succeeded (wind/rain from OpenWeatherMap).
- If the key is missing or the HTTP call fails, the handler logs the reason and falls back to mock data (`"mock": true` in per-location objects).

### End-to-end: “Ramesh” from Latur, Maharashtra

1. **Deploy** with a real **`WeatherApiKey`** and **`MOCK_WEATHER=false`** on the weather Lambda.
2. **Onboard** a test user (your phone) in WhatsApp: choose language → pick **Latur** (or Jalna / Nagpur) from district **buttons**, or type `Latur` / `लातूर`. Complete crop + nudge consent so **`GSI1PK` = `LOCATION#Latur`** exists.
3. **Invoke** the poller (command above). The Lambda queries GSI1 for each configured district including **Latur**; if at least one user exists for Latur, that district is checked against OpenWeatherMap at **lat 18.4088, lon 76.5604**.
4. **CloudWatch** logs for `agrinexus-weather-dev`: look for `Checking weather for … locations`, **`Triggered nudge workflow for Latur`** when conditions are favorable (wind &lt; 10 km/h, no rain in the payload), or no trigger when weather is unfavorable (expected in real conditions).

To force a **deterministic demo** of the nudge pipeline without depending on live weather, temporarily set **`MOCK_WEATHER=true`** on the weather Lambda (favorable mock for configured districts). Label demo recordings accordingly.

### Verify OpenWeatherMap directly (optional)

```bash
curl -sS "https://api.openweathermap.org/data/2.5/weather?lat=18.4088&lon=76.5604&appid=YOUR_KEY&units=metric" | jq '.wind.speed, .rain'
```

Compare wind (m/s × 3.6 = km/h) and rain fields with the logic in `src/weather/handler.py`.

## Weather Criteria for Nudges

AgriNexus triggers spray reminders when:
- Wind speed < 10 km/h (ideal for pesticide application)
- No rain expected
- Temperature and humidity are recorded for context

## Fallback Behavior

If the API key is missing or invalid, the system automatically falls back to mock data to ensure demos continue working.
