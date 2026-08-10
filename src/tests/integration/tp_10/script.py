# test_delegate_only.py
import tflite_runtime.interpreter as tflite

print("About to load delegate...")
delegate = tflite.load_delegate("libedgetpu.so.1")
print("Delegate loaded:", delegate)