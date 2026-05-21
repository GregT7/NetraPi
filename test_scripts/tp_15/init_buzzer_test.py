import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT)

print("GPIO High")
GPIO.output(18, GPIO.HIGH)
time.sleep(5)
print("GPIO LOW")
GPIO.output(18, GPIO.LOW)
time.sleep(1)
print("test end")

GPIO.cleanup()
