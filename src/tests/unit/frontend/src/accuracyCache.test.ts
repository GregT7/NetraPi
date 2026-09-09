import { afterEach, describe, expect, it } from 'vitest'
import {
  accuracySnapshotsEqual,
  readAccuracyCache,
  writeAccuracyCache,
} from '@/lib/accuracyCache'
import type { LiveAccuracySnapshot } from '@/lib/clipAccuracy'

const snapshot: LiveAccuracySnapshot = {
  field: {
    classes: [
      { count: 2, matches: 1, name: 'Complete Stop', percent: 50 },
      { count: 0, matches: 0, name: 'Rolling Stop', percent: null },
      { count: 0, matches: 0, name: 'Run-through Stop', percent: null },
    ],
    falsePositives: 1,
    labeled: 2,
    matches: 1,
    percent: 50,
    unlabeled: 0,
  },
  ideal: {
    classes: [
      { count: 1, matches: 1, name: 'Complete Stop', percent: 100 },
      { count: 0, matches: 0, name: 'Rolling Stop', percent: null },
      { count: 0, matches: 0, name: 'Run-through Stop', percent: null },
    ],
    falsePositives: 0,
    labeled: 1,
    matches: 1,
    percent: 100,
    unlabeled: 0,
  },
}

afterEach(() => {
  localStorage.clear()
})

describe('accuracyCache', () => {
  it('round-trips a snapshot and detects a change', () => {
    expect(readAccuracyCache()).toBeNull()
    writeAccuracyCache(snapshot)
    expect(readAccuracyCache()).toEqual(snapshot)
    const updated = {
      ...snapshot,
      field: { ...snapshot.field, percent: 40, matches: 0 },
    }
    expect(accuracySnapshotsEqual(snapshot, updated)).toBe(false)
    writeAccuracyCache(updated)
    expect(readAccuracyCache()?.field.percent).toBe(40)
  })
})
