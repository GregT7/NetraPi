from __future__ import annotations

import logging
import threading
import time
from typing import Any

from config.types import BuzzerConfig

from netrapi.events.driving_event import DrivingEvent

logger = logging.getLogger(__name__)
_PULSE_GAP_SECONDS = 0.12


class Buzzer:
    """PWM passive buzzer; beeps off the main loop via a short daemon thread."""

    def __init__(self, config: BuzzerConfig) -> None:
        self._config = config
        self._gpio: Any | None = None
        self._pwm: Any | None = None
        self._available = False
        self._lock = threading.Lock()
        self._stop_beep = threading.Event()

    @property
    def config(self) -> BuzzerConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def available(self) -> bool:
        """True after a successful ``open()`` with working GPIO/PWM."""
        return self._available

    def open(self) -> None:
        if not self._config.enabled:
            return
        if self._available:
            return
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self._config.gpio_pin, GPIO.OUT)
            pwm = GPIO.PWM(self._config.gpio_pin, self._config.pitch)
            pwm.start(0)
            self._gpio = GPIO
            self._pwm = pwm
            self._available = True
            self._stop_beep.clear()
        except Exception:
            logger.exception("Buzzer open failed; audible feedback disabled")
            self._available = False
            self._gpio = None
            self._pwm = None

    def pulse(self, count: int = 1) -> bool:
        """Start ``count`` non-blocking tones. Returns True if a sequence was started."""
        if count < 1:
            return False
        return self._start_pulses(count)

    def beep(self, event: DrivingEvent) -> bool:
        """Start a coded non-blocking tone when policy allows.

        Complete stop: 1 pulse, rolling: 2, run-through: 3.
        Returns True if a tone sequence was started.
        """
        if event.is_unsafe:
            if not self._config.play_on.unsafe:
                return False
        elif not self._config.play_on.safe:
            return False
        return self._start_pulses(event.type.beep_count)

    def _start_pulses(self, count: int) -> bool:
        if not self._available or not self._config.enabled:
            return False
        thread = threading.Thread(
            target=self._beep_worker,
            args=(count,),
            name="buzzer-beep",
            daemon=True,
        )
        thread.start()
        return True

    def close(self) -> None:
        self._stop_beep.set()
        with self._lock:
            try:
                if self._pwm is not None:
                    try:
                        self._pwm.ChangeDutyCycle(0)
                    except Exception:
                        logger.exception("Buzzer failed to silence PWM during close")
                    try:
                        self._pwm.stop()
                    except Exception:
                        logger.exception("Buzzer failed to stop PWM during close")
            finally:
                # Drop PWM before GPIO.cleanup so PWM.__del__ does not stop after
                # lgpio handles are gone (ignored TypeError on Pi OS Bookworm).
                self._pwm = None

            if self._gpio is not None:
                try:
                    self._gpio.cleanup()
                except Exception:
                    logger.exception("Buzzer GPIO cleanup failed")
                finally:
                    self._gpio = None

            self._available = False

    def _sleep_until(self, deadline: float) -> None:
        while time.monotonic() < deadline:
            if self._stop_beep.is_set():
                return
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def _beep_worker(self, count: int) -> None:
        gap_s = min(_PULSE_GAP_SECONDS, self._config.duration_seconds)
        for index in range(count):
            if self._stop_beep.is_set():
                return
            with self._lock:
                if not self._available or self._pwm is None or self._stop_beep.is_set():
                    return
                try:
                    self._pwm.ChangeFrequency(self._config.pitch)
                    self._pwm.ChangeDutyCycle(self._config.volume)
                except Exception:
                    logger.exception("Buzzer failed to start tone")
                    return

            # Sleep outside the lock so close() can silence promptly.
            self._sleep_until(time.monotonic() + self._config.duration_seconds)

            with self._lock:
                if self._pwm is None:
                    return
                try:
                    self._pwm.ChangeDutyCycle(0)
                except Exception:
                    logger.exception("Buzzer failed to end tone")
                    return

            if index + 1 < count and not self._stop_beep.is_set():
                self._sleep_until(time.monotonic() + gap_s)
