import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new Error('offline'))),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver

class IntersectionObserverStub {
  callback: IntersectionObserverCallback

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
  }

  disconnect() {}

  observe(target: Element) {
    this.callback(
      [
        {
          boundingClientRect: target.getBoundingClientRect(),
          intersectionRatio: 1,
          intersectionRect: target.getBoundingClientRect(),
          isIntersecting: true,
          rootBounds: null,
          target,
          time: 0,
        },
      ],
      this as unknown as IntersectionObserver,
    )
  }

  takeRecords(): IntersectionObserverEntry[] {
    return []
  }

  unobserve() {}
}

globalThis.IntersectionObserver =
  IntersectionObserverStub as unknown as typeof IntersectionObserver

function stubBBox() {
  return { x: 0, y: 0, width: 24, height: 24, top: 0, left: 0, bottom: 24, right: 24 }
}

for (const proto of [SVGElement.prototype, HTMLElement.prototype]) {
  if (typeof (proto as unknown as { getBBox?: () => unknown }).getBBox !== 'function') {
    ;(proto as unknown as { getBBox: () => unknown }).getBBox = stubBBox
  }
}

if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    addEventListener() {},
    addListener() {},
    dispatchEvent() {
      return false
    },
    matches: false,
    media: query,
    onchange: null,
    removeEventListener() {},
    removeListener() {},
  })) as typeof window.matchMedia
}

