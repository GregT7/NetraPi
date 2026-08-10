from netrapi.events import DrivingEvent, StopSignEnum


def test_driving_event_is_unsafe_from_type():
    assert DrivingEvent(type=StopSignEnum.COMPLETE_STOP).is_unsafe is False
    assert DrivingEvent(type=StopSignEnum.ROLLING_STOP).is_unsafe is True
    assert DrivingEvent(type=StopSignEnum.RUN_THROUGH).is_unsafe is True
