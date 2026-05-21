# NetraPi
RaspberryPi project emulating the Netradyne cameras used to monitor Amazon delivery drivers and improve driving quality.

## TPU/AI Notes
- I had to use a very specific tech stack for the ai inference and footage capturing subsystems due to the limitations of the Coral USB TPU. Originally, I was using the native picam but the libraries picam uses are not compatible with the python libraries needed by the TPU. Ergo, I swapped to a usb-based camera. I also was not able to get pycoral to work and opted instead to use solely tflite-runtime.
- Model:
    - Name: SSDLite MobileDet
    - Input Size: 320x320x3
    - Latency: 9.1 ms
    - mAP: 32.9%
    - Link: https://gweb-coral-full.uc.r.appspot.com/models/object-detection/
- Dataset: 
    - Name: Berkeley DeepDrive Dataset (BDD100K)
    - Usage: Helpful for gathering sample clips to test my algorithms on
- Dependencies
    - opencv-python==4.8.1.78
    - Pillow==10.4.0
    - tflite-runtime==2.11.0
    - numpy==1.26.4