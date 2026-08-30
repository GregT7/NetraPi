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

