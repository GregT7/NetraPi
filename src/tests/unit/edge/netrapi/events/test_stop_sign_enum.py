from netrapi.events import Stage1Label, Stage2Label, StopSignEnum


def test_stop_sign_enum_unsafe_flags():
    assert StopSignEnum.ROLLING_STOP.is_unsafe is True
    assert StopSignEnum.RUN_THROUGH.is_unsafe is True
    assert StopSignEnum.COMPLETE_STOP.is_unsafe is False


def test_stop_sign_enum_values():
    assert StopSignEnum.ROLLING_STOP.value == "stop_sign_rolling_stop"
    assert StopSignEnum.COMPLETE_STOP.value == "stop_sign_complete_stop"


def test_stop_sign_enum_model_labels():
    assert StopSignEnum.COMPLETE_STOP.model_label == "complete-stop"
    assert StopSignEnum.ROLLING_STOP.model_label == "rolling-stop"
    assert StopSignEnum.RUN_THROUGH.model_label == "run-through"
    assert StopSignEnum.from_model_label("rolling-stop") is StopSignEnum.ROLLING_STOP


def test_stage_label_values():
    assert Stage1Label.COMPLETE_STOP.value == "complete-stop"
    assert Stage1Label.ROLLING_OR_RUN_THROUGH.value == "rolling-or-run-through"
    assert Stage2Label.ROLLING_STOP.value == "rolling-stop"
    assert Stage2Label.RUN_THROUGH.value == "run-through"
