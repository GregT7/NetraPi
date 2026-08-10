import numpy as np
import tflite_runtime.interpreter as tflite

MODEL = "/home/terrelgat/Desktop/diyTest/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite"

interpreter = tflite.Interpreter(
    model_path=MODEL,
    experimental_delegates=[tflite.load_delegate("libedgetpu.so.1")]
)
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("Input details:", input_details)
print("Output details:", output_details)

input_shape = input_details[0]["shape"]
dummy = np.zeros(input_shape, dtype=input_details[0]["dtype"])

interpreter.set_tensor(input_details[0]["index"], dummy)
interpreter.invoke()

for out in output_details:
    arr = interpreter.get_tensor(out["index"])
    print("Output", out["index"], arr.shape, arr.dtype)
