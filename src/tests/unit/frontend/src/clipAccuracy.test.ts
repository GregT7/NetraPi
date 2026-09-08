import { describe, expect, it } from 'vitest'
import {
  FLAG_IN_OPERATING_ENVELOPE,
  FLAG_SYNTHETIC,
  filterByFlags,
  formatClassLine,
  formatOverallLine,
  idealClips,
  overallAccuracy,
  perClassAccuracy,
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
    classification: 'Run-through Stop',
    flags: [],
    label: '-',
  },
]

describe('clipAccuracy', () => {
  it('scores overall labeled clips and ignores unlabeled', () => {
    const stats = overallAccuracy(clips)
    expect(stats).toEqual({
      labeled: 3,
      matches: 2,
      unlabeled: 1,
      percent: 67,
    })
    expect(formatOverallLine(stats)).toBe(
      '67% (2/3 clips predicted correctly)',
    )
  })

  it('filters with AND and keeps ideal clips off synthetic', () => {
    expect(filterByFlags(clips, ['real_world']).map((clip) => clip.label)).toEqual(
      ['Complete Stop', 'Rolling Stop'],
    )
    expect(idealClips(clips)).toHaveLength(1)
    expect(idealClips(clips)[0]?.label).toBe('Complete Stop')
  })

  it('reports per-class counts and dashes empty classes', () => {
    const rows = perClassAccuracy(clips)
    expect(formatClassLine(rows[0])).toBe('Complete Stop (1 clips): 100%')
    expect(formatClassLine(rows[1])).toBe('Rolling Stop (2 clips): 50%')
    expect(formatClassLine(rows[2])).toBe('Run-through Stop (0 clips): —')
    expect(formatClassLine(rows[3])).toBe('Unrelated (0 clips): —')
  })
})
