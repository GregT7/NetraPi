export type HardwareNodeCard = {
  title: string
  body: string
  imageSrc?: string
  imageAlt?: string
}

export const HARDWARE_NODE_CARDS: Record<string, HardwareNodeCard> = {
  Mount: {
    title: 'Windshield Mount',
    body: '3D-printed suction mount holds the camera forward-facing on the Mazda3 windshield.',
  },
  Cam: {
    title: 'Arducam USB',
    body: 'USB camera captures the road through the windshield for stop-sign detection.',
  },
  Pi: {
    title: 'Raspberry Pi 5',
    body: 'Raspberry Pi 5 runs capture, Coral inference, and local SQLite.',
  },
  Battery: {
    title: 'Portable Battery',
    body: 'USB battery pack powers the Pi in the car without a permanent 12V tap.',
  },
  Coral: {
    title: 'Coral USB TPU',
    body: 'Google Coral USB TPU runs on-device SSDLite stop-sign detection.',
  },
  Hotspot: {
    title: 'Cellular Hotspot',
    body: 'Phone hotspot gives the Pi a path to the backend when it uploads clips.',
  },
  S3: {
    title: 'AWS S3',
    body: 'Private S3 bucket stores confirmed event clips behind signed GET URLs.',
  },
  Phone: {
    title: 'Phone',
    body: 'Phone shares cellular data as the hotspot; it is not the in-car display.',
  },
  Buzzer: {
    title: 'GPIO Buzzer',
    body: 'GPIO PWM buzzer gives real-time audible feedback when a stop-sign event is classified.',
  },
}
