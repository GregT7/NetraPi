export const FLAG_IN_OPERATING_ENVELOPE = 'in_operating_envelope'
export const FLAG_REAL_WORLD = 'real_world'
export const FLAG_SYNTHETIC = 'synthetic'

export const ACCURACY_CLASSES = [
  'Complete Stop',
  'Rolling Stop',
  'Run-through Stop',
  'Unrelated',
] as const

export type AccuracyClass = (typeof ACCURACY_CLASSES)[number]

export type ClipForAccuracy = {
  classification: string
  flags?: string[]
  label: string
}

export type OverallAccuracy = {
  labeled: number
  matches: number
  unlabeled: number
  percent: number | null
}

export type ClassAccuracy = {
  name: AccuracyClass
  count: number
  matches: number
  percent: number | null
}

export function clipHasFlag(clip: ClipForAccuracy, flag: string): boolean {
  return (clip.flags ?? []).includes(flag)
}

export function filterByFlags<T extends ClipForAccuracy>(
  clips: T[],
  flags: string[],
): T[] {
  if (flags.length === 0) {
    return clips
  }
  return clips.filter((clip) => flags.every((flag) => clipHasFlag(clip, flag)))
}

export function idealClips<T extends ClipForAccuracy>(clips: T[]): T[] {
  return clips.filter(
    (clip) =>
      clipHasFlag(clip, FLAG_IN_OPERATING_ENVELOPE) &&
      !clipHasFlag(clip, FLAG_SYNTHETIC),
  )
}

export function overallAccuracy(clips: ClipForAccuracy[]): OverallAccuracy {
  const unlabeled = clips.filter((clip) => clip.label === '-').length
  const labeled = clips.filter((clip) => clip.label !== '-')
  const matches = labeled.filter(
    (clip) => clip.classification === clip.label,
  ).length
  return {
    labeled: labeled.length,
    matches,
    unlabeled,
    percent:
      labeled.length === 0
        ? null
        : Math.round((100 * matches) / labeled.length),
  }
}

export function perClassAccuracy(clips: ClipForAccuracy[]): ClassAccuracy[] {
  const labeled = clips.filter((clip) => clip.label !== '-')
  return ACCURACY_CLASSES.map((name) => {
    const inClass = labeled.filter((clip) => clip.label === name)
    const matches = inClass.filter(
      (clip) => clip.classification === clip.label,
    ).length
    return {
      name,
      count: inClass.length,
      matches,
      percent:
        inClass.length === 0
          ? null
          : Math.round((100 * matches) / inClass.length),
    }
  })
}

export function formatOverallLine(stats: OverallAccuracy): string {
  if (stats.percent === null || stats.labeled === 0) {
    return 'No labeled clips yet'
  }
  return `${stats.percent}% (${stats.matches}/${stats.labeled} clips predicted correctly)`
}

export function formatClassLine(row: ClassAccuracy): string {
  if (row.percent === null) {
    return `${row.name} (${row.count} clips): —`
  }
  return `${row.name} (${row.count} clips): ${row.percent}%`
}
