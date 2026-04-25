import pytest

from grotesk.presentation.web.routes import build_operation_rows, format_seconds_label, parse_time_value


def test_parse_time_value_accepts_seconds_and_timecodes() -> None:
    assert parse_time_value("75") == 75
    assert parse_time_value("01:15") == 75
    assert parse_time_value("1:02:30") == 3750


def test_parse_time_value_rejects_invalid_seconds_component() -> None:
    with pytest.raises(ValueError):
        parse_time_value("01:75")


def test_build_operation_rows_formats_minutes_and_seconds() -> None:
    rows = build_operation_rows([])

    assert rows == []
    assert format_seconds_label(75) == "01:15"
    assert format_seconds_label(3750) == "01:02:30"
