from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.insights.service import InsightsService


def test_dst_transition_uses_correct_international_offsets() -> None:
    service = InsightsService(cast(AsyncSession, None))
    before = service._local_datetime(
        datetime(2026, 3, 8, 6, 30, tzinfo=UTC), "America/New_York"
    )
    after = service._local_datetime(
        datetime(2026, 3, 8, 7, 30, tzinfo=UTC), "America/New_York"
    )
    assert before == "2026-03-08T01:30:00-05:00"
    assert after == "2026-03-08T03:30:00-04:00"


def test_leap_day_and_midnight_timezone_conversion() -> None:
    service = InsightsService(cast(AsyncSession, None))
    leap_day = service._local_datetime(
        datetime(2028, 2, 29, 18, 45, tzinfo=UTC), "Asia/Kolkata"
    )
    previous_day = service._local_datetime(
        datetime(2026, 1, 1, 0, 15, tzinfo=UTC), "America/Los_Angeles"
    )
    assert leap_day == "2028-03-01T00:15:00+05:30"
    assert previous_day == "2025-12-31T16:15:00-08:00"
