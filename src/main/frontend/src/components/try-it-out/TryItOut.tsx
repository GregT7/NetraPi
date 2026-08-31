import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchPublicClips,
  mintPublicClipUrl,
  type PublicClipRow,
} from '@/api/publicPlayback'

const PAGE_SIZE = 5

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
  const mintAbort = useRef<AbortController | null>(null)
  const liveStatusAbort = useRef<AbortController | null>(null)
  const liveStatusTimers = useRef<ReturnType<typeof setTimeout>[]>([])

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

  function selectClip(clip: PublicClipRow) {
    mintAbort.current?.abort()
    const controller = new AbortController()
    mintAbort.current = controller
    setSelectedId(clip.id)
    setVideoUrl('')
    setMessage('Requesting a 2-minute playback URL…')
    mintPublicClipUrl(clip.clipId, controller.signal)
      .then((minted) => {
        if (controller.signal.aborted) {
          return
        }
        setVideoUrl(minted.url)
        setMessage('')
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

  return (
    <section className="scroll-mt-20 px-6 py-16" id="try-it-out">
      <div className="mx-auto max-w-4xl space-y-6">
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

        <div className="overflow-hidden rounded-lg border border-dashed border-zinc-600 bg-zinc-900">
          {videoUrl ? (
            <video
              aria-label="Event clip"
              autoPlay
              className="aspect-video w-full bg-black"
              controls
              playsInline
              src={videoUrl}
            />
          ) : (
            <div className="flex aspect-video items-center justify-center px-4 text-center text-sm text-zinc-400">
              {message || 'No clip selected'}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
