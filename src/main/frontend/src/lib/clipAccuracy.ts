export const FLAG_ERROR = 'error'
export const FLAG_IN_OPERATING_ENVELOPE = 'in_operating_envelope'
export const FLAG_REAL_WORLD = 'real_world'
export const FLAG_SYNTHETIC = 'synthetic'
export const ERROR_LABEL = 'Error'

export const STOP_CLASSES = [
  'Complete Stop',
  'Rolling Stop',
  'Run-through Stop',
] as const

export type AccuracyClass = (typeof STOP_CLASSES)[number]

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

export type LiveAccuracySnapshot = {
  field: LiveAccuracyBlock
  ideal: LiveAccuracyBlock
  tripSeconds: number
}

export type LiveAccuracyBlock = {
  classes: ClassAccuracy[]
  falsePositives: number
  labeled: number
  matches: number
  percent: number | null
  unlabeled: number
}

const UNRELATED_LABEL = 'Unrelated'

export function clipHasFlag(clip: ClipForAccuracy, flag: string): boolean {
  return (clip.flags ?? []).includes(flag)
}

export function clipDisplayLabel(clip: ClipForAccuracy): string {
  return clipHasFlag(clip, FLAG_ERROR) ? ERROR_LABEL : clip.label
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

export function fieldClips<T extends ClipForAccuracy>(clips: T[]): T[] {
  return clips.filter(
    (clip) =>
      !clipHasFlag(clip, FLAG_SYNTHETIC) && !clipHasFlag(clip, FLAG_ERROR),
  )
}

export function realWorldClips<T extends ClipForAccuracy>(clips: T[]): T[] {
  return clips.filter((clip) => clipHasFlag(clip, FLAG_REAL_WORLD))
}

export function idealClips<T extends ClipForAccuracy>(clips: T[]): T[] {
  return clips.filter(
    (clip) =>
      clipHasFlag(clip, FLAG_IN_OPERATING_ENVELOPE) &&
      !clipHasFlag(clip, FLAG_SYNTHETIC) &&
      !clipHasFlag(clip, FLAG_ERROR),
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

export function stopAccuracy(clips: ClipForAccuracy[]): OverallAccuracy {
  const stopClips = clips.filter((clip) =>
    STOP_CLASSES.includes(clip.label as AccuracyClass),
  )
  const matches = stopClips.filter(
    (clip) => clip.classification === clip.label,
  ).length
  const unlabeled = clips.filter((clip) => clip.label === '-').length
  return {
    labeled: stopClips.length,
    matches,
    unlabeled,
    percent:
      stopClips.length === 0
        ? null
        : Math.round((100 * matches) / stopClips.length),
  }
}

export function falsePositiveCount(clips: ClipForAccuracy[]): number {
  return clips.filter((clip) => clip.label === UNRELATED_LABEL).length
}

export function falsePositiveRate(clips: ClipForAccuracy[]): {
  labeled: number
  matches: number
  percent: number | null
} {
  const total = clips.length
  const falsePositives = falsePositiveCount(clips)
  return {
    labeled: total,
    matches: falsePositives,
    percent:
      total === 0 ? null : Math.round((100 * falsePositives) / total),
  }
}

export function errorCount(clips: ClipForAccuracy[]): number {
  return clips.filter((clip) => clipHasFlag(clip, FLAG_ERROR)).length
}

export function errorRate(clips: ClipForAccuracy[]): {
  labeled: number
  matches: number
  percent: number | null
} {
  const total = clips.length
  const errors = errorCount(clips)
  return {
    labeled: total,
    matches: errors,
    percent: total === 0 ? null : Math.round((100 * errors) / total),
  }
}

export function perStopAccuracy(clips: ClipForAccuracy[]): ClassAccuracy[] {
  const labeled = clips.filter((clip) => clip.label !== '-')
  return STOP_CLASSES.map((name) => {
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

export function liveAccuracyBlock(clips: ClipForAccuracy[]): LiveAccuracyBlock {
  const stats = stopAccuracy(clips)
  return {
    classes: perStopAccuracy(clips),
    falsePositives: falsePositiveCount(clips),
    labeled: stats.labeled,
    matches: stats.matches,
    percent: stats.percent,
    unlabeled: stats.unlabeled,
  }
}

export function liveAccuracySnapshot(
  clips: ClipForAccuracy[],
  tripSeconds = 0,
): LiveAccuracySnapshot {
  return {
    field: liveAccuracyBlock(fieldClips(clips)),
    ideal: liveAccuracyBlock(idealClips(clips)),
    tripSeconds,
  }
}

export function formatOverallLine(stats: {
  labeled: number
  matches: number
  percent: number | null
}): string {
  if (stats.percent === null || stats.labeled === 0) {
    return 'No labeled stop-type clips yet'
  }
  return `${stats.percent}% (${stats.matches}/${stats.labeled} clips predicted correctly)`
}

export function formatClassLine(row: ClassAccuracy): string {
  if (row.percent === null) {
    return `${row.name} (${row.count} clips): n/a`
  }
  return `${row.name} (${row.count} clips): ${row.percent}%`
}

export function formatFalsePositives(count: number): string {
  const noun = count === 1 ? 'false positive' : 'false positives'
  return `${count} ${noun} (unrelated detections)`
}

export function formatPendingLabels(count: number): string {
  return `Clips Pending Labels: ${count}`
}

export function formatTripTime(seconds: number): string {
  const hours = Math.round((Math.max(0, seconds) / 3600) * 10) / 10
  const text = Number.isInteger(hours) ? String(hours) : hours.toFixed(1)
  const noun = hours === 1 ? 'hour' : 'hours'
  return `Total Trip Time: ${text} ${noun}`
}

export function formatNamedAccuracy(
  name: string,
  block: { labeled: number; matches: number; percent: number | null },
): string {
  const noun = block.labeled === 1 ? 'clip' : 'clips'
  if (block.percent === null) {
    return `${name}: n/a (${block.matches}/${block.labeled} ${noun})`
  }
  return `${name}: ${block.percent}% (${block.matches}/${block.labeled} ${noun})`
}
