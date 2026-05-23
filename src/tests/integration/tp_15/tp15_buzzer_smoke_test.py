import time

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
BUZZER_PIN = 18

GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Initialize PWM (start with any frequency, we'll change it)
pwm = GPIO.PWM(BUZZER_PIN, 1000)
pwm.start(0)  # start with no sound

# Define pitches (Hz)
pitches = [
    750, 1000
]

# Define volumes (duty cycle %)
volumes = [
5, 10, 15, 20
]

try:
    print("Starting tone test...")

    for pitch in pitches:
        for volume in volumes:
            print(f"Playing {pitch}Hz at {volume}% volume")

            pwm.ChangeFrequency(pitch)
            pwm.ChangeDutyCycle(volume)

            time.sleep(2)

            # brief pause between tones
            pwm.ChangeDutyCycle(0)
            time.sleep(0.5)

    print("Test complete.")

finally:
    # Stop PWM and drop the handle before GPIO.cleanup().
    # Otherwise PWM.__del__ can call stop() after lgpio handles are gone
    # and print an ignored TypeError on newer Pi OS (lgpio backend).
    try:
        pwm.ChangeDutyCycle(0)
        pwm.stop()
    except Exception:
        pass
    pwm = None
    GPIO.cleanup()
