from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field
from app.task.tool.tool import Tool, ToolResult

class DateTimeArgs(BaseModel):
    timezone_name: str = Field(default="Asia/Shanghai", description="IANA timezone name")


class DateTimeTool(Tool):
    name = "datetime_info"
    description = "Return the current local date and time for a given timezone."
    args = DateTimeArgs
    trigger_words = {
        "time": 1.0,
        "date": 0.8,
        "timezone": 0.8,
        "now": 0.6,
        "几点": 1.0,
        "时间": 1.2,
        "日期": 0.8,
        "时区": 0.8,
    }

    def extract_args(self, content: str):
        lower = content.lower()
        mapping = {
            "singapore": "Asia/Singapore",
            "beijing": "Asia/Shanghai",
            "shanghai": "Asia/Shanghai",
            "tokyo": "Asia/Tokyo",
            "london": "Europe/London",
            "new york": "America/New_York",
            "utc": "UTC",
            "新加坡": "Asia/Singapore",
            "北京": "Asia/Shanghai",
            "上海": "Asia/Shanghai",
            "东京": "Asia/Tokyo",
            "伦敦": "Europe/London",
            "纽约": "America/New_York",
        }
        for key, value in mapping.items():
            if key in lower or key in content:
                return {"timezone_name": value}
        return {"timezone_name": "Asia/Shanghai"}

    def run(self, **kwargs):
        timezone_name = kwargs["timezone_name"]
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            fallback_zone = self._fallback_timezone(timezone_name)
            if fallback_zone is None:
                return ToolResult(success=False, error=f"Unknown timezone: {timezone_name}")
            zone = fallback_zone

        now = datetime.now(zone)
        utc_now = datetime.now(timezone.utc)
        return ToolResult(
            success=True,
            data={
                "timezone": timezone_name,
                "local_time": now.isoformat(),
                "local_hour": now.hour,
                "local_minute": now.minute,
                "utc_time": utc_now.isoformat(),
                "weekday": now.strftime("%A"),
            },
        )

    @staticmethod
    def _fallback_timezone(timezone_name: str):
        mapping = {
            "UTC": timezone.utc,
            "Asia/Shanghai": timezone(timedelta(hours=8)),
            "Asia/Singapore": timezone(timedelta(hours=8)),
            "Asia/Tokyo": timezone(timedelta(hours=9)),
            "Europe/London": timezone(timedelta(hours=0)),
            "America/New_York": timezone(timedelta(hours=-5)),
        }
        return mapping.get(timezone_name)
