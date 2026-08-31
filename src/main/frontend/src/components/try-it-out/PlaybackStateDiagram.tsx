import { useEffect, useRef, useState } from 'react'
import type { PlaybackTransitionsFile } from '@/api/publicPlayback'

export const PLAYBACK_STATE_IDS = [
  'Monitoring',
  'SampleMotion',
  'CompleteStop',
  'RollingStop',
  'RunThrough',
] as const

export type PlaybackStateId = (typeof PLAYBACK_STATE_IDS)[number]

export const DUMMY_PHASE_SECONDS = 12

export function dummyTransitions(
  classification = 'rolling-stop',
  duration = DUMMY_PHASE_SECONDS,
): PlaybackTransitionsFile {
  const span = duration > 1 ? duration : DUMMY_PHASE_SECONDS
  const t0 = Math.round(span * 0.33 * 10) / 10
  const sampleEnd =
    Math.round(Math.min(span * 0.75, t0 + Math.max(3, span * 0.35)) * 10) / 10
  return {
    classification,
    schema_version: 1,
    states: [
      { t: 0, id: 'Monitoring' },
      { t: t0, id: 'SampleMotion' },
      { t: sampleEnd, id: outcomeStateId(classification) },
    ],
  }
}

const STATE_LABELS: Record<PlaybackStateId, string> = {
  CompleteStop: 'Complete Stop',
  Monitoring: 'Monitoring',
  RollingStop: 'Rolling Stop',
  RunThrough: 'Run-through',
  SampleMotion: "Sample Car's Motion",
}

type PlaybackStateDiagramProps = {
  stateId: string
}

function isPlaybackStateId(value: string): value is PlaybackStateId {
  return (PLAYBACK_STATE_IDS as readonly string[]).includes(value)
}

export function outcomeStateId(classification: string): PlaybackStateId {
  const value = classification.trim().toLowerCase()
  if (value.includes('complete')) {
    return 'CompleteStop'
  }
  if (value.includes('rolling')) {
    return 'RollingStop'
  }
  if (value.includes('run')) {
    return 'RunThrough'
  }
  return 'CompleteStop'
}

export function stateIdAtTime(
  file: PlaybackTransitionsFile | null,
  time: number,
  t0: number,
  sampleEnd: number,
  classification: string,
): PlaybackStateId {
  if (file?.states?.length) {
    let id: PlaybackStateId = 'Monitoring'
    for (const state of file.states) {
      if (typeof state.t !== 'number' || time < state.t) {
        continue
      }
      if (isPlaybackStateId(state.id)) {
        id = state.id
      }
    }
    return id
  }
  if (time < t0) {
    return 'Monitoring'
  }
  if (time < sampleEnd) {
    return 'SampleMotion'
  }
  return outcomeStateId(classification)
}

function nodeClass(
  active: boolean,
  tone: 'amber' | 'green' | 'purple' | 'red' = 'amber',
) {
  const idle =
    tone === 'green'
      ? 'border-emerald-800 text-zinc-400'
      : tone === 'purple'
        ? 'border-violet-800 text-zinc-400'
        : tone === 'red'
          ? 'border-red-900 text-zinc-400'
          : 'border-zinc-600 text-zinc-300'
  const live =
    tone === 'green'
      ? 'border-emerald-400 bg-emerald-950 text-emerald-50 shadow-[0_0_18px_rgb(52_211_153/0.45)]'
      : tone === 'purple'
        ? 'border-violet-400 bg-violet-950 text-violet-50 shadow-[0_0_18px_rgb(167_139_250/0.45)]'
        : tone === 'red'
          ? 'border-red-400 bg-red-950 text-red-50 shadow-[0_0_18px_rgb(248_113_113/0.45)]'
          : 'border-amber-400 bg-zinc-800 text-zinc-50 shadow-[0_0_18px_rgb(251_191_36/0.4)]'
  return `flex min-h-12 flex-1 items-center justify-center rounded-lg border-2 px-2 py-2 text-center text-sm font-semibold leading-tight transition-[border-color,background-color,box-shadow,color] duration-300 ${
    active ? live : `${idle} bg-zinc-950`
  }`
}

function SelfLoop({ active }: { active: boolean }) {
  const color = active ? '#fbbf24' : '#52525b'
  return (
    <svg
      aria-hidden
      className={`w-9 shrink-0 self-stretch ${active ? 'playback-poll-stroke' : ''}`}
      preserveAspectRatio="none"
      viewBox="0 0 40 56"
    >
      <path
        d="M38 14 H14 C6 14 6 42 14 42 H38"
        fill="none"
        stroke={color}
        strokeLinecap="round"
        strokeWidth="2.5"
      />
      <polygon fill={color} points="38,42 27,36.5 27,47.5" />
    </svg>
  )
}

function LoopBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <div
      className={`flex items-center gap-1.5 text-[11px] ${
        active ? 'text-amber-400' : 'text-zinc-500'
      }`}
    >
      <span
        className={`inline-block size-2 rounded-full ${
          active ? 'bg-amber-400 playback-poll' : 'bg-zinc-600'
        }`}
      />
      {label}
    </div>
  )
}

function PollingState({
  active,
  label,
  loopLabel,
}: {
  active: boolean
  label: string
  loopLabel: string
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1">
      <div className="flex min-h-0 w-full flex-1 items-stretch">
        <SelfLoop active={active} />
        <div className={nodeClass(active)}>{label}</div>
      </div>
      <LoopBadge active={active} label={loopLabel} />
    </div>
  )
}

function DownEdge({
  active,
  flash,
  label,
}: {
  active: boolean
  flash: boolean
  label: string
}) {
  const lit = active || flash
  return (
    <div className="flex flex-col items-center py-0.5">
      <p className={`text-[11px] ${lit ? 'text-amber-300' : 'text-zinc-500'}`}>
        {label}
      </p>
      <div
        className={`h-5 w-0.5 ${flash ? 'playback-edge-flash' : ''} ${
          lit ? 'bg-amber-400' : 'bg-zinc-600'
        }`}
      />
      <div
        className={`border-x-4 border-t-[6px] border-x-transparent ${
          lit ? 'border-t-amber-400' : 'border-t-zinc-600'
        }`}
      />
    </div>
  )
}

export default function PlaybackStateDiagram({ stateId }: PlaybackStateDiagramProps) {
  const current = isPlaybackStateId(stateId) ? stateId : 'Monitoring'
  const previous = useRef(current)
  const [flash, setFlash] = useState('')

  useEffect(() => {
    if (previous.current === current) {
      return
    }
    const edge = `${previous.current}->${current}`
    previous.current = current
    setFlash(edge)
    const timer = window.setTimeout(() => setFlash(''), 700)
    return () => window.clearTimeout(timer)
  }, [current])

  const sampling = current === 'SampleMotion'
  const classified =
    current === 'CompleteStop' ||
    current === 'RollingStop' ||
    current === 'RunThrough'

  return (
    <div
      aria-label="Stop-sign encounter states"
      className="flex h-full min-h-0 flex-col justify-between gap-1 p-1"
    >
      <PollingState
        active={current === 'Monitoring'}
        label={STATE_LABELS.Monitoring}
        loopLabel="Approach not detected"
      />

      <DownEdge
        active={sampling || classified}
        flash={flash === 'Monitoring->SampleMotion'}
        label="Approach detected"
      />

      <PollingState
        active={sampling}
        label={STATE_LABELS.SampleMotion}
        loopLabel="Under 5 seconds"
      />

      <DownEdge
        active={classified}
        flash={flash.startsWith('SampleMotion->')}
        label="5 seconds passed"
      />

      <div className="grid min-h-0 flex-1 grid-cols-3 gap-1.5">
        <div className={nodeClass(current === 'CompleteStop', 'green')}>
          {STATE_LABELS.CompleteStop}
        </div>
        <div className={nodeClass(current === 'RollingStop', 'purple')}>
          {STATE_LABELS.RollingStop}
        </div>
        <div className={nodeClass(current === 'RunThrough', 'red')}>
          {STATE_LABELS.RunThrough}
        </div>
      </div>
    </div>
  )
}
