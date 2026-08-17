from typing import Any

import requests
from pydantic import BaseModel, Field

from app.task.tool.tool import Tool, ToolPolicy, ToolResult


class WeatherArgs(BaseModel):
    location: str = Field(..., description="City or region name, for example Shanghai")


class WeatherTool(Tool):
    name = "weather"
    description = "Look up the current weather for a city or region."
    args = WeatherArgs
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=8.0, retry_count=1)
    trigger_words = {
        "weather": 1.2,
        "forecast": 1.0,
        "temperature": 0.9,
        "rain": 0.8,
        "天气": 1.3,
        "气温": 1.0,
        "下雨": 0.9,
        "温度": 0.9,
    }
    negative_triggers = {"knowledge": 0.8, "memory": 0.6}

    def extract_args(self, content: str) -> dict[str, Any]:
        stripped = content.strip()
        markers = ["weather in", "forecast for", "天气", "查询天气", "看看", "查看"]
        for marker in markers:
            lowered = stripped.lower()
            index = lowered.find(marker) if marker.isascii() else stripped.find(marker)
            if index != -1:
                value = stripped[index + len(marker) :].strip(" ：:，,。?？")
                if value:
                    return {"location": value}
        return {"location": stripped}

    def run(self, **kwargs) -> ToolResult:
        location = kwargs["location"].strip()
        try:
            geo_resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "zh", "format": "json"},
                timeout=8,
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            results = geo_data.get("results") or []
            if not results:
                return ToolResult(success=False, error=f"Could not find location: {location}")

            target = results[0]
            weather_resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": target["latitude"],
                    "longitude": target["longitude"],
                    "current": "temperature_2m,apparent_temperature,wind_speed_10m,weather_code",
                    "timezone": "auto",
                },
                timeout=8,
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json().get("current", {})
        except requests.RequestException as exc:
            return ToolResult(success=False, error=f"Weather lookup failed: {exc}")

        code = int(weather_data.get("weather_code", -1))
        result = {
            "location": target.get("name", location),
            "country": target.get("country", ""),
            "timezone": weather_data.get("timezone", target.get("timezone", "")),
            "temperature_c": weather_data.get("temperature_2m"),
            "apparent_temperature_c": weather_data.get("apparent_temperature"),
            "wind_speed_kmh": weather_data.get("wind_speed_10m"),
            "weather_code": code,
            "weather_text": self._describe_weather(code),
        }
        return ToolResult(success=True, data=result)

    @staticmethod
    def _describe_weather(code: int) -> str:
        mapping = {
            0: "Clear",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            80: "Rain showers",
            81: "Rain showers",
            82: "Heavy rain showers",
            95: "Thunderstorm",
        }
        return mapping.get(code, "Unknown")
