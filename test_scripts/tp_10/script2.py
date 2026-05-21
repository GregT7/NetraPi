import tflite_runtime.interpreter as tflite

MODEL = "/home/terrelgat/Desktop/diyTest/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite"

interpreter = tflite.Interpreter(
    model_path=MODEL,
    experimental_delegates=[tflite.load_delegate("libedgetpu.so.1")]
)
interpreter.allocate_tensors()
print("Interpreter OK")
