import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchPublicClips,
  mintPublicClipUrl,
  type PlaybackSeriesFile,
  type PlaybackTransitionsFile,
  type PublicClipRow,
} from '@/api/publicPlayback'
import PlaybackSeriesChart from './PlaybackSeriesChart'
import PlaybackStateDiagram, {
  playbackAccentClass,
  stateIdAtTime,
} from './PlaybackStateDiagram'
import {
  FLAG_IN_OPERATING_ENVELOPE,
  FLAG_REAL_WORLD,
  FLAG_SYNTHETIC,
  filterByFlags,
  overallAccuracy,
} from '@/lib/clipAccuracy'

const PAGE_SIZE = 5
const MINT_DEBOUNCE_MS = 300
const CACHE_SAFETY_SECONDS = 10
const SEEK_LOCK_EPSILON = 0.4

const CLIP_FILTERS = [
  { flag: FLAG_IN_OPERATING_ENVELOPE, label: 'Good scenario' },
  { flag: FLAG_REAL_WORLD, label: 'Real world' },
  { flag: FLAG_SYNTHETIC, label: 'Parking-lot / synthetic' },
] as const

type CachedMint = {
  areas: PlaybackSeriesFile | null
  expiresAt: number
  motion: PlaybackSeriesFile | null
  transitions: PlaybackTransitionsFile | null
  url: string
}

function seriesPoints(
  file: PlaybackSeriesFile | null,
  key: 'area' | 'score',
  scale = 1,
) {
  if (!file?.points) {
    return []
  }
  return file.points
    .map((point) => ({
      t: point.t,
      value: (key === 'area' ? point.area : point.score) ?? 0,
    }))
    .map((point) => ({ ...point, value: point.value * scale }))
}

export default function TryItOut() {
  const [clips, setClips] = useState<PublicClipRow[]>([])
  const [liveUrlMax, setLiveUrlMax] = useState(20)
  const [liveUrls, setLiveUrls] = useState(0)
  const [listError, setListError] = useState('')
  const [listLoading, setListLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [page, setPage] = useState(0)
  const [activeFlags, setActiveFlags] = useState<string[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [detailed, setDetailed] = useState(true)
  const [areas, setAreas] = useState<PlaybackSeriesFile | null>(null)
  const [motion, setMotion] = useState<PlaybackSeriesFile | null>(null)
  const [transitions, setTransitions] = useState<PlaybackTransitionsFile | null>(
    null,
  )
  const [classification, setClassification] = useState('')
  const [stateId, setStateId] = useState('')
  const [playheadOff, setPlayheadOff] = useState(false)
  const mintAbort = useRef<AbortController | null>(null)
  const mintCache = useRef<Map<number, CachedMint>>(new Map())
  const mintDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mintGeneration = useRef(0)
  const selectedIdRef = useRef('')
  const liveStatusAbort = useRef<AbortController | null>(null)
  const liveStatusTimers = useRef<ReturnType<typeof setTimeout>[]>([])
  const videoRef = useRef<HTMLVideoElement>(null)
  const playbackRef = useRef<HTMLDivElement>(null)
  const playheadRef = useRef<HTMLDivElement>(null)
  const playheadOffRef = useRef(false)
  const allowedTime = useRef(0)
  const originHold = useRef(false)

  function resetToMonitoring() {
    originHold.current = true
    allowedTime.current = 0
    playheadOffRef.current = false
    setPlayheadOff(false)
    setStateId('')
    const video = videoRef.current
    if (!video) {
      return
    }
    video.pause()
    try {
      video.currentTime = 0
    } catch {
      return
    }
  }

  const loadClips = useCallback((signal?: AbortSignal) => {
    setListLoading(true)
    setListError('')
    fetchPublicClips(signal)
      .then((result) => {
        if (signal?.aborted) {
          return
        }
        setClips(result.clips)
        setLiveUrls(result.liveUrls)
        setLiveUrlMax(result.liveUrlMax)
        setPage(0)
        setListLoading(false)
      })
      .catch((error: unknown) => {
        if (signal?.aborted) {
          return
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setClips([])
        setListLoading(false)
        setListError(
          error instanceof Error && error.message
            ? error.message
            : 'Could not load clips from the database.',
        )
      })
  }, [])

  const refreshLiveStatus = useCallback(() => {
    liveStatusAbort.current?.abort()
    const controller = new AbortController()
    liveStatusAbort.current = controller
    fetchPublicClips(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        setLiveUrls(result.liveUrls)
        setLiveUrlMax(result.liveUrlMax)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
      })
  }, [])

  function scheduleLiveStatusRefresh(expiresInSeconds: number) {
    const delayMs = Math.max(0, expiresInSeconds) * 1000
    const timerId = setTimeout(() => {
      liveStatusTimers.current = liveStatusTimers.current.filter((id) => id !== timerId)
      refreshLiveStatus()
    }, delayMs)
    liveStatusTimers.current.push(timerId)
  }

  useEffect(() => {
    const controller = new AbortController()
    loadClips(controller.signal)
    return () => {
      controller.abort()
      mintAbort.current?.abort()
      liveStatusAbort.current?.abort()
      if (mintDebounce.current !== null) {
        clearTimeout(mintDebounce.current)
        mintDebounce.current = null
      }
      for (const timerId of liveStatusTimers.current) {
        clearTimeout(timerId)
      }
      liveStatusTimers.current = []
    }
  }, [loadClips])

  const visibleClips: PublicClipRow[] = filterByFlags(clips, activeFlags)
  const accuracy = overallAccuracy(visibleClips)
  const pageCount = Math.max(1, Math.ceil(visibleClips.length / PAGE_SIZE))
  const pageStart = page * PAGE_SIZE
  const pageClips = visibleClips.slice(pageStart, pageStart + PAGE_SIZE)
  const rangeStart = visibleClips.length === 0 ? 0 : pageStart + 1
  const rangeEnd = pageStart + pageClips.length
  const t0 = areas?.t0_s ?? motion?.t0_s ?? 0
  const sampleEnd = Number(areas?.sample_end_s ?? motion?.sample_end_s ?? t0)
  const areaPoints = seriesPoints(areas, 'area', 100)
  const motionPoints = seriesPoints(motion, 'score')
  const xMax = Math.max(sampleEnd + 3, 0.01)
  const hasTelemetry = areas != null || motion != null
  const accent = detailed ? playbackAccentClass(stateId) : undefined

  useEffect(() => {
    if (!detailed || !videoUrl) {
      return
    }
    let frame = 0
    const tick = () => {
      const video = videoRef.current
      let time: number
      if (originHold.current) {
        if (video && video.currentTime > 0.2) {
          try {
            video.currentTime = 0
          } catch {
            /* not seekable yet */
          }
        } else if (video && video.readyState >= 1) {
          originHold.current = false
        }
        time = 0
      } else {
        time = video?.currentTime ?? 0
      }
      const head = playheadRef.current
      if (head && xMax > 0) {
        const pct = Math.max(0, time / xMax)
        head.style.left = `calc(48px + ${pct} * (100% - 96px))`
      }
      const off = time >= xMax
      if (playheadOffRef.current !== off) {
        playheadOffRef.current = off
        setPlayheadOff(off)
      }
      const nextState = stateIdAtTime(
        transitions,
        time,
        t0,
        sampleEnd,
        classification,
      )
      setStateId((current) => (current === nextState ? current : nextState))
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [classification, detailed, sampleEnd, t0, transitions, videoUrl, xMax])

  useEffect(() => {
    const video = videoRef.current
    if (!video || !detailed || !videoUrl) {
      return
    }
    const player = video
    allowedTime.current = originHold.current ? 0 : player.currentTime
    function onTimeUpdate() {
      if (originHold.current) {
        allowedTime.current = 0
        return
      }
      if (!player.seeking) {
        allowedTime.current = player.currentTime
      }
    }
    function onSeeking() {
      if (originHold.current) {
        allowedTime.current = 0
        if (player.currentTime > 0.2) {
          player.currentTime = 0
        }
        return
      }
      const dest = player.currentTime
      const durationNow = player.duration
      const nearEnd =
        Number.isFinite(durationNow) &&
        durationNow > 0 &&
        allowedTime.current >= durationNow - 0.35
      if (dest < 0.2 && (player.ended || nearEnd)) {
        allowedTime.current = dest
        return
      }
      if (Math.abs(dest - allowedTime.current) < SEEK_LOCK_EPSILON) {
        return
      }
      player.currentTime = allowedTime.current
    }
    player.addEventListener('timeupdate', onTimeUpdate)
    player.addEventListener('seeking', onSeeking)
    return () => {
      player.removeEventListener('timeupdate', onTimeUpdate)
      player.removeEventListener('seeking', onSeeking)
    }
  }, [detailed, videoUrl])

  function cachedMint(clipId: number): CachedMint | null {
    const cached = mintCache.current.get(clipId)
    if (!cached) {
      return null
    }
    if (cached.expiresAt <= Date.now()) {
      mintCache.current.delete(clipId)
      return null
    }
    return cached
  }

  function applyPlayback(cached: CachedMint, label: string) {
    mintAbort.current?.abort()
    resetToMonitoring()
    setVideoUrl(cached.url)
    setAreas(cached.areas)
    setMotion(cached.motion)
    setTransitions(cached.transitions)
    setClassification(label)
    setMessage('')
  }

  function mintClip(clip: PublicClipRow, generation: number) {
    const cached = cachedMint(clip.clipId)
    if (cached) {
      applyPlayback(cached, clip.classification)
      return
    }
    mintAbort.current?.abort()
    const controller = new AbortController()
    mintAbort.current = controller
    resetToMonitoring()
    setVideoUrl('')
    setAreas(null)
    setMotion(null)
    setTransitions(null)
    setMessage('Requesting a 2-minute playback URL…')
    mintPublicClipUrl(clip.clipId, controller.signal)
      .then((minted) => {
        if (generation !== mintGeneration.current) {
          return
        }
        if (controller.signal.aborted) {
          return
        }
        const expiresIn =
          typeof minted.expires_in === 'number' ? minted.expires_in : 0
        const next: CachedMint = {
          areas: minted.areas ?? null,
          expiresAt: Date.now() + Math.max(0, expiresIn - CACHE_SAFETY_SECONDS) * 1000,
          motion: minted.motion ?? null,
          transitions: minted.transitions ?? null,
          url: minted.url,
        }
        mintCache.current.set(clip.clipId, next)
        applyPlayback(next, clip.classification)
        if (typeof minted.live_urls === 'number') {
          setLiveUrls(minted.live_urls)
        }
        if (typeof minted.live_url_max === 'number') {
          setLiveUrlMax(minted.live_url_max)
        }
        if (typeof minted.expires_in === 'number') {
          scheduleLiveStatusRefresh(minted.expires_in)
        }
      })
      .catch((error: unknown) => {
        if (generation !== mintGeneration.current) {
          return
        }
        if (controller.signal.aborted) {
          return
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        const fallback = 'Could not reach the playback API.'
        setMessage(error instanceof Error && error.message ? error.message : fallback)
      })
  }

  function revealPlayback() {
    const node = playbackRef.current
    if (!node || typeof node.scrollIntoView !== 'function') {
      return
    }
    node.scrollIntoView({ behavior: 'smooth', block: 'start', inline: 'nearest' })
  }

  function selectClip(clip: PublicClipRow) {
    if (selectedIdRef.current === clip.id) {
      return
    }
    selectedIdRef.current = clip.id
    setSelectedId(clip.id)
    revealPlayback()
    resetToMonitoring()
    setClassification(clip.classification)
    mintGeneration.current += 1
    const generation = mintGeneration.current
    if (mintDebounce.current !== null) {
      clearTimeout(mintDebounce.current)
      mintDebounce.current = null
    }
    const cached = cachedMint(clip.clipId)
    if (cached) {
      applyPlayback(cached, clip.classification)
      return
    }
    setVideoUrl('')
    setAreas(null)
    setMotion(null)
    setTransitions(null)
    setMessage('')
    mintDebounce.current = setTimeout(() => {
      mintDebounce.current = null
      if (generation !== mintGeneration.current) {
        return
      }
      mintClip(clip, generation)
    }, MINT_DEBOUNCE_MS)
  }

  function toggleFlag(flag: string) {
    setPage(0)
    setActiveFlags((current) =>
      current.includes(flag)
        ? current.filter((item) => item !== flag)
        : [...current, flag],
    )
  }

  return (
    <section className="scroll-mt-20 px-6 pb-6 pt-16" id="try-it-out">
      <div className="mx-auto max-w-6xl space-y-6">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Try It Out
        </h2>
        <p className="text-zinc-300">
          Confirmed clips from the cloud database. Click a row to play it from
          the private S3 bucket. The browser never holds AWS or device keys.
        </p>
        <p className="text-sm text-zinc-400">
          Live S3 links {liveUrls}/{liveUrlMax}
        </p>
        {clips.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {CLIP_FILTERS.map((filter) => {
              const pressed = activeFlags.includes(filter.flag)
              return (
                <button
                  aria-pressed={pressed}
                  className={`rounded-md border px-3 py-1 text-sm ${
                    pressed
                      ? 'border-amber-400 bg-amber-400/10 text-amber-300'
                      : 'border-zinc-700 text-zinc-300 hover:bg-zinc-800'
                  }`}
                  key={filter.flag}
                  onClick={() => toggleFlag(filter.flag)}
                  type="button"
                >
                  {filter.label}
                </button>
              )
            })}
          </div>
        ) : null}
        {clips.length > 0 ? (
          <p className="text-sm text-zinc-300">
            {visibleClips.length === 0
              ? 'No clips match these filters.'
              : accuracy.labeled === 0
              ? `No labeled clips yet. ${accuracy.unlabeled} unlabeled excluded.`
              : `${accuracy.matches} of ${accuracy.labeled} labeled clips match (${
                  accuracy.percent ?? 0
                }%). ${accuracy.unlabeled} unlabeled excluded.`}
          </p>
        ) : null}
        {listError ? (
          <div className="flex flex-wrap items-center gap-3 text-sm text-red-400">
            <p>{listError}</p>
            <button
              className="rounded-md border border-zinc-700 px-3 py-1 text-zinc-100 hover:bg-zinc-800"
              onClick={() => loadClips()}
              type="button"
            >
              Retry
            </button>
          </div>
        ) : null}

        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full table-fixed text-left">
            <colgroup>
              <col className="w-[18%]" />
              <col className="w-[12%]" />
              <col className="w-[32%]" />
              <col className="w-[19%]" />
              <col className="w-[19%]" />
            </colgroup>
            <thead className="bg-zinc-900 text-lg text-amber-400">
              <tr className="h-12">
                <th className="px-4 font-medium" scope="col">
                  Clip
                </th>
                <th className="px-4 font-medium" scope="col">
                  Session
                </th>
                <th className="px-4 font-medium" scope="col">
                  Timestamp
                </th>
                <th className="px-4 font-medium" scope="col">
                  Label
                </th>
                <th className="px-4 font-medium" scope="col">
                  Prediction
                </th>
              </tr>
            </thead>
            <tbody className="text-sm text-white">
              {listLoading || visibleClips.length === 0
                ? Array.from({ length: PAGE_SIZE }, (_, index) => (
                    <tr className="h-12 border-t border-zinc-800" key={`empty-${index}`}>
                      <td className="truncate px-4 text-zinc-400" colSpan={5}>
                        {index === 0
                          ? listLoading
                            ? 'Loading clips…'
                            : listError
                              ? 'No clips to show.'
                              : clips.length === 0
                                ? 'No confirmed clips in the database yet.'
                                : 'No clips match these filters.'
                          : '\u00a0'}
                      </td>
                    </tr>
                  ))
                : Array.from({ length: PAGE_SIZE }, (_, index) => {
                    const clip = pageClips[index]
                    if (!clip) {
                      return (
                        <tr className="h-12 border-t border-zinc-800" key={`pad-${index}`}>
                          <td className="truncate px-4">&nbsp;</td>
                          <td className="truncate px-4">&nbsp;</td>
                          <td className="truncate px-4">&nbsp;</td>
                          <td className="truncate px-4">&nbsp;</td>
                          <td className="truncate px-4">&nbsp;</td>
                        </tr>
                      )
                    }
                    const unlabeled = clip.label === '-'
                    const matched = !unlabeled && clip.classification === clip.label
                    const selected = selectedId === clip.id
                    return (
                      <tr
                        aria-selected={selected}
                        className={`h-12 cursor-pointer border-t border-zinc-800 ${
                          selected
                            ? 'bg-zinc-700 hover:bg-zinc-700'
                            : 'hover:bg-zinc-800/40'
                        }`}
                        key={clip.id}
                        onClick={() => selectClip(clip)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            selectClip(clip)
                          }
                        }}
                        tabIndex={0}
                      >
                        <td className="truncate px-4">{clip.id}</td>
                        <td className="truncate px-4">{clip.drivingSessionId}</td>
                        <td className="truncate px-4">{clip.dateTime}</td>
                        <td className="truncate px-4">{clip.label}</td>
                        <td
                          className={`truncate px-4 ${
                            unlabeled
                              ? ''
                              : matched
                                ? 'text-emerald-400'
                                : 'text-red-400'
                          }`}
                        >
                          {clip.classification}
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between gap-4 text-base text-zinc-300">
          <button
            className="rounded-md border border-zinc-700 px-4 py-2 text-zinc-100 enabled:hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={page === 0}
            onClick={() => setPage((current) => current - 1)}
            type="button"
          >
            Previous
          </button>
          <p>
            {rangeStart}–{rangeEnd} of {visibleClips.length}
          </p>
          <button
            className="rounded-md border border-zinc-700 px-4 py-2 text-zinc-100 enabled:hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={page >= pageCount - 1 || visibleClips.length === 0}
            onClick={() => setPage((current) => current + 1)}
            type="button"
          >
            Next
          </button>
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-200">
          <input
            checked={detailed}
            className="size-4 accent-amber-400"
            onChange={(event) => setDetailed(event.target.checked)}
            type="checkbox"
          />
          Detailed Analysis
        </label>

        <div
          aria-label="Clip playback"
          className={
            detailed
              ? 'grid scroll-mt-20 items-start gap-3 lg:grid-cols-3'
              : 'scroll-mt-20 overflow-hidden rounded-lg border border-dashed border-zinc-600 bg-zinc-900'
          }
          ref={playbackRef}
        >
          <div
            aria-label={detailed ? 'Event clip slot' : undefined}
            className={
              detailed
                ? `w-full max-w-full overflow-hidden rounded-lg border-dashed bg-zinc-900 transition-[border-color,box-shadow] duration-300 lg:col-span-2 ${
                    accent ? `border-4 ${accent}` : 'border-2 border-zinc-600'
                  }`
                : ''
            }
            data-accent-border={detailed ? accent : undefined}
          >
            <div
              className={
                detailed
                  ? 'flex h-[min(70vh,32rem)] w-full items-center justify-center bg-zinc-950'
                  : 'flex h-[calc(22rem+9rem+0.75rem)] w-full items-center justify-center bg-zinc-950'
              }
            >
              {videoUrl ? (
                <video
                  aria-label="Event clip"
                  autoPlay
                  className={
                    detailed
                      ? 'playback-no-seek max-h-full max-w-full object-contain'
                      : 'max-h-full max-w-full object-contain bg-black'
                  }
                  controls
                  onLoadedMetadata={(event) => {
                    allowedTime.current = 0
                    event.currentTarget.currentTime = 0
                  }}
                  playsInline
                  ref={videoRef}
                  src={videoUrl}
                />
              ) : (
                <div className="px-4 text-center text-sm text-zinc-400">
                  {message || 'No clip selected'}
                </div>
              )}
            </div>
          </div>
          {detailed ? (
            <div className="grid grid-rows-[minmax(22rem,1.25fr)_minmax(9rem,0.9fr)] gap-3">
              <div
                className={`min-h-0 overflow-hidden rounded-lg bg-zinc-900 p-2 transition-[border-color,box-shadow] duration-300 ${
                  accent ? `border-4 ${accent}` : 'border-2 border-zinc-700'
                }`}
                data-accent-border={accent}
              >
                <PlaybackStateDiagram
                  key={selectedId || 'idle'}
                  stateId={videoUrl ? stateId : ''}
                />
              </div>
              <div
                className={`min-h-0 overflow-hidden rounded-lg bg-zinc-900 p-2 transition-[border-color,box-shadow] duration-300 ${
                  accent ? `border-4 ${accent}` : 'border-2 border-zinc-700'
                }`}
                data-accent-border={accent}
              >
                {hasTelemetry ? (
                  <PlaybackSeriesChart
                    areaPoints={areaPoints}
                    emptyLabel="No analysis data"
                    motionPoints={motionPoints}
                    playheadOff={playheadOff}
                    playheadRef={playheadRef}
                    xMax={xMax}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center px-3 text-center text-sm text-zinc-400">
                    {videoUrl
                      ? 'No analysis data for this clip'
                      : 'No clip selected'}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
