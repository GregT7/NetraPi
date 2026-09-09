import type { LiveAccuracySnapshot } from './clipAccuracy'

const STORAGE_KEY = 'netrapi.resultsAccuracy.v1'

export function readAccuracyCache(): LiveAccuracySnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as LiveAccuracySnapshot
    if (!parsed?.field || !parsed?.ideal) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function writeAccuracyCache(snapshot: LiveAccuracySnapshot): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
  } catch {
    return
  }
}

export function accuracySnapshotsEqual(
  left: LiveAccuracySnapshot,
  right: LiveAccuracySnapshot,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}
