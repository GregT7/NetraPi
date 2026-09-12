import { describe, expect, it } from 'vitest'
import {
  ERROR_LABEL,
  FLAG_ERROR,
  FLAG_IN_OPERATING_ENVELOPE,
  FLAG_SYNTHETIC,
  clipDisplayLabel,
  errorRate,
  fieldClips,
  falsePositiveRate,
  filterByFlags,
  formatClassLine,
  formatFalsePositives,
  formatNamedAccuracy,
  formatOverallLine,
  formatPendingLabels,
  formatTripTime,
  idealClips,
  liveAccuracySnapshot,
  overallAccuracy,
  perStopAccuracy,
  realWorldClips,
} from '@/lib/clipAccuracy'

const clips = [
  {
    classification: 'Complete Stop',
    flags: ['real_world', FLAG_IN_OPERATING_ENVELOPE],
    label: 'Complete Stop',
  },
  {
    classification: 'Complete Stop',
    flags: ['real_world'],
    label: 'Rolling Stop',
  },
  {
    classification: 'Rolling Stop',
    flags: [FLAG_SYNTHETIC],
    label: 'Rolling Stop',
  },
  {
    classification: 'Complete Stop',
    flags: ['real_world'],
    label: 'Unrelated',
  },
  {
    classification: 'Run-through Stop',
    flags: [],
    label: '-',
  },
  {
    classification: 'Complete Stop',
    flags: ['real_world', FLAG_ERROR],
    label: 'Complete Stop',
  },
]

describe('clipAccuracy', () => {
  it('scores overall labeled clips and ignores unlabeled', () => {
    const stats = overallAccuracy(clips)
    expect(stats).toEqual({
      labeled: 5,
      matches: 3,
      unlabeled: 1,
      percent: 60,
    })
    expect(formatOverallLine(stats)).toBe(
      '60% (3/5 clips predicted correctly)',
    )
  })

  it('filters with AND and keeps field and ideal clips off synthetic and error', () => {
    expect(filterByFlags(clips, ['real_world']).map((clip) => clip.label)).toEqual(
      ['Complete Stop', 'Rolling Stop', 'Unrelated', 'Complete Stop'],
    )
    expect(fieldClips(clips).map((clip) => clip.label)).toEqual([
      'Complete Stop',
      'Rolling Stop',
      'Unrelated',
      '-',
    ])
    expect(realWorldClips(clips).map((clip) => clip.label)).toEqual([
      'Complete Stop',
      'Rolling Stop',
      'Unrelated',
      'Complete Stop',
    ])
    expect(clipDisplayLabel(clips[5])).toBe(ERROR_LABEL)
    expect(idealClips(clips)).toHaveLength(1)
    expect(idealClips(clips)[0]?.label).toBe('Complete Stop')
  })

  it('reports stop-class accuracy and counts unrelated as false positives', () => {
    const snapshot = liveAccuracySnapshot(clips)
    expect(snapshot.field.percent).toBe(50)
    expect(snapshot.field.labeled).toBe(2)
    expect(snapshot.field.matches).toBe(1)
    expect(snapshot.field.falsePositives).toBe(1)
    expect(snapshot.ideal.percent).toBe(100)
    expect(snapshot.ideal.falsePositives).toBe(0)
    expect(formatFalsePositives(1)).toBe('1 false positive (unrelated detections)')
    expect(formatPendingLabels(0)).toBe('Clips Pending Labels: 0')
    expect(formatPendingLabels(1)).toBe('Clips Pending Labels: 1')
    expect(formatTripTime(0)).toBe('Total Trip Time: 0 hours')
    expect(formatTripTime(3600)).toBe('Total Trip Time: 1 hour')
    expect(formatTripTime(37800)).toBe('Total Trip Time: 10.5 hours')
    expect(formatNamedAccuracy('Field Accuracy', snapshot.field)).toBe(
      'Field Accuracy: 50% (1/2 clips)',
    )
    expect(
      formatNamedAccuracy('False Positives', falsePositiveRate(fieldClips(clips))),
    ).toBe('False Positives: 25% (1/4 clips)')
    expect(
      formatNamedAccuracy('Errors', errorRate(realWorldClips(clips))),
    ).toBe('Errors: 25% (1/4 clips)')
    expect(errorRate([])).toEqual({
      labeled: 0,
      matches: 0,
      percent: null,
    })
    expect(
      falsePositiveRate([{ classification: 'Unrelated', label: 'Unrelated' }]),
    ).toEqual({ labeled: 1, matches: 1, percent: 100 })
    expect(falsePositiveRate([])).toEqual({
      labeled: 0,
      matches: 0,
      percent: null,
    })
    const rows = perStopAccuracy(fieldClips(clips))
    expect(formatClassLine(rows[0])).toBe('Complete Stop (1 clips): 100%')
    expect(formatClassLine(rows[1])).toBe('Rolling Stop (1 clips): 0%')
    expect(formatClassLine(rows[2])).toBe('Run-through Stop (0 clips): n/a')
  })
})
