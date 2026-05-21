import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
BUZZER_PIN = 18

GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Initialize PWM (start with any frequency, we'll change it)
pwm = GPIO.PWM(BUZZER_PIN, 1000)
pwm.start(0)  # start with no sound

# Define pitches (Hz)
pitches = [
    500,   # low
    1000,  # medium
    2000   # high
]

# Define volumes (duty cycle %)
volumes = [
    20,   # low volume
    50,   # medium volume
    80    # high volume
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
    pwm.stop()
    GPIO.cleanup()