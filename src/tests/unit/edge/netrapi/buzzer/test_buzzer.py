from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from config.types import BuzzerConfig, BuzzerPlayOnConfig
from netrapi.buzzer import Buzzer
from netrapi.events import DrivingEvent, StopSignEnum


def _buzzer_config(
    *,
    unsafe: bool = True,
    safe: bool = False,
    duration_seconds: float = 0.05,
) -> BuzzerConfig:
    return BuzzerConfig(
        gpio_pin=18,
        volume=50.0,
        pitch=1000.0,
        duration_seconds=duration_seconds,
        play_on=BuzzerPlayOnConfig(unsafe=unsafe, safe=safe),
    )


def test_disabled_buzzer_open_beep_close_are_noop():
    buzzer = Buzzer(_buzzer_config(unsafe=False, safe=False))

    with patch.dict("sys.modules", {"RPi": MagicMock(), "RPi.GPIO": MagicMock()}):
        buzzer.open()
        assert buzzer.beep(DrivingEvent(type=StopSignEnum.ROLLING_STOP)) is False
        buzzer.close()

    assert buzzer.enabled is False
    assert buzzer.available is False


def test_open_soft_fails_when_gpio_missing():
    buzzer = Buzzer(_buzzer_config())

    buzzer.open()

    assert buzzer.available is False
    assert buzzer.beep(DrivingEvent(type=StopSignEnum.ROLLING_STOP)) is False


def test_beep_filters_by_play_on_flags():
    gpio = MagicMock()
    pwm = MagicMock()
    gpio.PWM.return_value = pwm
    fake_rpi = SimpleNamespace(GPIO=gpio)

    buzzer = Buzzer(_buzzer_config(unsafe=True, safe=False, duration_seconds=0.01))
    with patch.dict("sys.modules", {"RPi": fake_rpi, "RPi.GPIO": gpio}):
        buzzer.open()
        assert buzzer.available is True
        assert buzzer.beep(DrivingEvent(type=StopSignEnum.COMPLETE_STOP)) is False
        buzzer.close()

    duty_values = [call.args[0] for call in pwm.ChangeDutyCycle.call_args_list]
    assert 50.0 not in duty_values


def test_beep_plays_for_unsafe_event():
    gpio = MagicMock()
    pwm = MagicMock()
    gpio.PWM.return_value = pwm
    fake_rpi = SimpleNamespace(GPIO=gpio)

    buzzer = Buzzer(_buzzer_config(unsafe=True, safe=False, duration_seconds=0.05))
    with patch.dict("sys.modules", {"RPi": fake_rpi, "RPi.GPIO": gpio}):
        buzzer.open()
        assert buzzer.beep(DrivingEvent(type=StopSignEnum.ROLLING_STOP)) is True
        import time

        time.sleep(0.1)
        buzzer.close()

    gpio.setup.assert_called_once_with(18, gpio.OUT)
    pwm.ChangeFrequency.assert_called_with(1000.0)
    assert any(call.args[0] == 50.0 for call in pwm.ChangeDutyCycle.call_args_list)
    pwm.stop.assert_called_once()
    gpio.cleanup.assert_called_once()


def test_close_swallows_cleanup_errors():
    gpio = MagicMock()
    pwm = MagicMock()
    pwm.stop.side_effect = RuntimeError("pwm stop failed")
    gpio.cleanup.side_effect = RuntimeError("cleanup failed")
    gpio.PWM.return_value = pwm
    fake_rpi = SimpleNamespace(GPIO=gpio)

    buzzer = Buzzer(_buzzer_config(duration_seconds=0.01))
    with patch.dict("sys.modules", {"RPi": fake_rpi, "RPi.GPIO": gpio}):
        buzzer.open()
        buzzer.close()

    assert buzzer._available is False
    assert buzzer._pwm is None
    assert buzzer._gpio is None
