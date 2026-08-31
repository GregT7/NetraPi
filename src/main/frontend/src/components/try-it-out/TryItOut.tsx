import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchPublicClips,
  mintPublicClipUrl,
  type PlaybackSeriesFile,
  type PlaybackTransitionsFile,
  type PublicClipRow,
} from '@/api/publicPlayback'
import PlaybackSeriesChart from './PlaybackSeriesChart'
import PlaybackStateDiagram, {
  DUMMY_PHASE_SECONDS,
  dummyTransitions,
  stateIdAtTime,
} from './PlaybackStateDiagram'

const PAGE_SIZE = 5
const MINT_DEBOUNCE_MS = 300
const CACHE_SAFETY_SECONDS = 10
const SEEK_LOCK_EPSILON = 0.4

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
  const [selectedId, setSelectedId] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [detailed, setDetailed] = useState(true)
  const [areas, setAreas] = useState<PlaybackSeriesFile | null>(null)
  const [motion, setMotion] = useState<PlaybackSeriesFile | null>(null)
  const [transitions, setTransitions] = useState<PlaybackTransitionsFile | null>(
    null,
  )
  const [classification, setClassification] = useState('')
  const [showMotion, setShowMotion] = useState(false)
  const [stateId, setStateId] = useState('Monitoring')
  const [duration, setDuration] = useState(0)
  const mintAbort = useRef<AbortController | null>(null)
  const mintCache = useRef<Map<number, CachedMint>>(new Map())
  const mintDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mintGeneration = useRef(0)
  const selectedIdRef = useRef('')
  const liveStatusAbort = useRef<AbortController | null>(null)
  const liveStatusTimers = useRef<ReturnType<typeof setTimeout>[]>([])
  const videoRef = useRef<HTMLVideoElement>(null)
  const playheadRef = useRef<HTMLDivElement>(null)
  const allowedTime = useRef(0)
  const originHold = useRef(false)

  function resetToMonitoring() {
    originHold.current = true
    allowedTime.current = 0
    setStateId('Monitoring')
    setShowMotion(false)
    setDuration(0)
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

  const pageCount = Math.max(1, Math.ceil(clips.length / PAGE_SIZE))
  const pageStart = page * PAGE_SIZE
  const pageClips = clips.slice(pageStart, pageStart + PAGE_SIZE)
  const rangeStart = clips.length === 0 ? 0 : pageStart + 1
  const rangeEnd = pageStart + pageClips.length
  const t0 = areas?.t0_s ?? motion?.t0_s ?? 0
  const sampleEnd = areas?.sample_end_s ?? motion?.sample_end_s ?? t0
  const areaPoints = seriesPoints(areas, 'area', 100)
  const motionPoints = seriesPoints(motion, 'score')
  const xMax = Math.max(
    duration,
    sampleEnd,
    areaPoints[areaPoints.length - 1]?.t ?? 0,
    motionPoints[motionPoints.length - 1]?.t ?? 0,
  )
  const hasTelemetry = areas != null || motion != null
  const phaseFile = useMemo(() => {
    if (transitions?.states?.length) {
      return transitions
    }
    return dummyTransitions(
      classification || 'rolling-stop',
      videoUrl ? duration : DUMMY_PHASE_SECONDS,
    )
  }, [classification, duration, transitions, videoUrl])

  useEffect(() => {
    if (!detailed) {
      return
    }
    let frame = 0
    const tick = () => {
      const video = videoRef.current
      let time: number
      if (!selectedId) {
        time = (performance.now() / 1000) % DUMMY_PHASE_SECONDS
      } else if (originHold.current) {
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
        const pct = Math.min(1, Math.max(0, time / xMax))
        head.style.left = `calc(48px + ${pct} * (100% - 60px))`
      }
      const nextMotion = time >= t0
      setShowMotion((current) => (current === nextMotion ? current : nextMotion))
      const nextState = stateIdAtTime(
        phaseFile,
        time,
        t0,
        sampleEnd,
        classification || 'rolling-stop',
      )
      setStateId((current) => (current === nextState ? current : nextState))
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [classification, detailed, phaseFile, sampleEnd, selectedId, t0, videoUrl, xMax])

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

  function selectClip(clip: PublicClipRow) {
    if (selectedIdRef.current === clip.id) {
      return
    }
    selectedIdRef.current = clip.id
    setSelectedId(clip.id)
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

  return (
    <section className="scroll-mt-20 px-6 py-16" id="try-it-out">
      <div className="mx-auto max-w-6xl space-y-6">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Try it out
        </h2>
        <p className="text-zinc-300">
          Confirmed clips from the cloud database. Click a row to play it from
          the private S3 bucket. The browser never holds AWS or device keys.
        </p>
        <p className="text-sm text-zinc-400">
          Live S3 links {liveUrls}/{liveUrlMax}
        </p>
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
          <table className="w-full text-left">
            <thead className="bg-zinc-900 text-lg text-amber-400">
              <tr>
                <th className="px-4 py-3 font-medium" scope="col">
                  Clip
                </th>
                <th className="px-4 py-3 font-medium" scope="col">
                  Timestamp
                </th>
                <th className="px-4 py-3 font-medium" scope="col">
                  Label
                </th>
                <th className="px-4 py-3 font-medium" scope="col">
                  Prediction
                </th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {listLoading ? (
                <tr>
                  <td className="px-4 py-6 text-zinc-400" colSpan={4}>
                    Loading clips…
                  </td>
                </tr>
              ) : pageClips.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-zinc-400" colSpan={4}>
                    {listError
                      ? 'No clips to show.'
                      : 'No confirmed clips in the database yet.'}
                  </td>
                </tr>
              ) : (
                pageClips.map((clip) => {
                  const matched = clip.classification === clip.label
                  const selected = selectedId === clip.id
                  return (
                    <tr
                      aria-selected={selected}
                      className={`cursor-pointer border-t border-zinc-800 ${
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
                      <td className="px-4 py-3 text-amber-400">{clip.id}</td>
                      <td className="px-4 py-3 text-zinc-200">{clip.dateTime}</td>
                      <td className="px-4 py-3 text-zinc-200">{clip.label}</td>
                      <td
                        className={`px-4 py-3 ${matched ? 'text-emerald-400' : 'text-red-400'}`}
                      >
                        {clip.classification}
                      </td>
                    </tr>
                  )
                })
              )}
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
            {rangeStart}–{rangeEnd} of {clips.length}
          </p>
          <button
            className="rounded-md border border-zinc-700 px-4 py-2 text-zinc-100 enabled:hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={page >= pageCount - 1 || clips.length === 0}
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
          Detailed analysis
        </label>

        <div
          className={
            detailed
              ? 'grid items-start gap-3 lg:grid-cols-3'
              : 'overflow-hidden rounded-lg border border-dashed border-zinc-600 bg-zinc-900'
          }
        >
          <div
            aria-label={detailed ? 'Event clip slot' : undefined}
            className={
              detailed
                ? 'w-full max-w-full overflow-hidden rounded-lg border border-dashed border-zinc-600 bg-zinc-900 lg:col-span-2'
                : ''
            }
          >
            <div
              className={
                detailed
                  ? 'flex h-[min(70vh,32rem)] w-full items-center justify-center bg-zinc-950'
                  : ''
              }
            >
              {videoUrl ? (
                <video
                  aria-label="Event clip"
                  autoPlay
                  className={
                    detailed
                      ? 'playback-no-seek max-h-full max-w-full object-contain'
                      : 'aspect-video w-full bg-black'
                  }
                  controls
                  onLoadedMetadata={(event) => {
                    allowedTime.current = 0
                    event.currentTarget.currentTime = 0
                    setDuration(event.currentTarget.duration || 0)
                  }}
                  playsInline
                  ref={videoRef}
                  src={videoUrl}
                />
              ) : (
                <div
                  className={
                    detailed
                      ? 'px-4 text-center text-sm text-zinc-400'
                      : 'flex aspect-video items-center justify-center px-4 text-center text-sm text-zinc-400'
                  }
                >
                  {message || 'No clip selected'}
                </div>
              )}
            </div>
          </div>
          {detailed ? (
            <div className="grid min-h-144 grid-rows-[minmax(22rem,1.25fr)_minmax(12rem,1fr)] gap-3">
              <div className="min-h-0 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900 p-2">
                <PlaybackStateDiagram
                  key={selectedId || 'idle'}
                  stateId={stateId}
                />
              </div>
              <div className="overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900 p-2">
                {hasTelemetry ? (
                  <PlaybackSeriesChart
                    color={showMotion ? '#fbbf24' : '#38bdf8'}
                    emptyLabel="No analysis data"
                    playheadRef={playheadRef}
                    points={showMotion ? motionPoints : areaPoints}
                    title={showMotion ? 'Motion' : 'Sign Area'}
                    xMax={xMax}
                    yLabel={
                      showMotion ? 'Motion (px / Frame)' : 'Sign Area (% of Frame)'
                    }
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
