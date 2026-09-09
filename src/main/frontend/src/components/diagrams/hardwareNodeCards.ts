export type HardwareNodeCard = {
  title: string
  body: string
  imageSrc?: string
  imageAlt?: string
  imageClass?: string
}

export const HARDWARE_NODE_CARDS: Record<string, HardwareNodeCard> = {
  Mount: {
    title: 'Windshield Mount',
    body: '3D-printed suction mount holds the camera forward-facing on the Mazda3 windshield.',
    imageSrc: '/gifs/cam-mount.gif?v=1',
    imageAlt: '3D-printed suction mount for the windshield camera',
  },
  Cam: {
    title: 'Arducam USB',
    body: 'An Arducam USB camera captures the road through the windshield for stop-sign detection.',
    imageSrc: '/images/arducam.avif?v=1',
    imageAlt: 'Arducam USB camera',
  },
  Pi: {
    title: 'Raspberry Pi 5',
    body: 'Raspberry Pi 5 runs capture, Coral inference, and local SQLite.',
    imageSrc: '/gifs/pi.gif?v=1',
    imageAlt: 'Raspberry Pi 5 in the in-car build',
  },
  Battery: {
    title: 'Portable Battery',
    body: 'A 98Wh (27,000mAh) 100W USB-C power bank with an AC outlet powers the Pi without a 12V tap.',
    imageSrc: '/images/battery.avif?v=1',
    imageAlt: '100W USB-C power bank with AC outlet',
  },
  Coral: {
    title: 'Coral USB TPU',
    body: 'Google Coral USB TPU runs on-device SSDLite stop-sign detection.',
    imageSrc: '/images/coral-tpu.avif?v=1',
    imageAlt: 'Google Coral USB TPU',
  },
  Hotspot: {
    title: 'Cellular Hotspot',
    body: 'Phone hotspot gives the Pi a path to the backend when it uploads clips.',
    imageSrc: '/gifs/hotspot.gif?v=1',
    imageAlt: 'Phone hotspot used to upload clips from the car',
  },
  S3: {
    title: 'AWS S3',
    body: 'Private S3 bucket stores confirmed event clips behind signed GET URLs.',
  },
  Phone: {
    title: 'Phone',
    body: 'An iPhone 11 shares cellular data as the hotspot; it is not the in-car display.',
    imageSrc: '/images/iphone-11.avif?v=1',
    imageAlt: 'iPhone 11 used as the cellular hotspot',
    imageClass: 'mx-auto max-h-36 w-auto',
  },
  Buzzer: {
    title: 'GPIO Buzzer',
    body: 'A KY-006 passive piezo buzzer on GPIO beeps when a stop-sign event is classified.',
    imageSrc: '/images/buzzer.avif?v=1',
    imageAlt: 'KY-006 passive piezo buzzer module',
  },
}
