import { useState } from 'react'

type ClipRow = {
  classification: string
  dateTime: string
  id: string
  label: string
}

const PAGE_SIZE = 5

const clips: ClipRow[] = [
  {
    classification: 'Complete stop',
    dateTime: '2026-03-14 09:41',
    id: 'clip-12',
    label: 'Complete stop',
  },
  {
    classification: 'Rolling stop',
    dateTime: '2026-03-14 10:06',
    id: 'clip-27',
    label: 'Rolling stop',
  },
  {
    classification: 'Rolling stop',
    dateTime: '2026-03-14 10:22',
    id: 'clip-41',
    label: 'Run-through',
  },
  {
    classification: 'Complete stop',
    dateTime: '2026-03-14 11:03',
    id: 'clip-63',
    label: 'Unrelated',
  },
  {
    classification: 'Run-through',
    dateTime: '2026-03-14 11:48',
    id: 'clip-70',
    label: 'Run-through',
  },
  {
    classification: 'Complete stop',
    dateTime: '2026-03-14 12:15',
    id: 'clip-81',
    label: 'Complete stop',
  },
  {
    classification: 'Rolling stop',
    dateTime: '2026-03-14 12:41',
    id: 'clip-88',
    label: 'Unrelated',
  },
  {
    classification: 'Run-through',
    dateTime: '2026-03-14 13:02',
    id: 'clip-92',
    label: 'Run-through',
  },
  {
    classification: 'Unrelated',
    dateTime: '2026-03-14 13:27',
    id: 'clip-95',
    label: 'Unrelated',
  },
  {
    classification: 'Complete stop',
    dateTime: '2026-03-14 13:54',
    id: 'clip-99',
    label: 'Rolling stop',
  },
]

export default function TryItOut() {
  const [message, setMessage] = useState('')
  const [page, setPage] = useState(0)
  const [selectedId, setSelectedId] = useState('')

  const pageCount = Math.ceil(clips.length / PAGE_SIZE)
  const pageStart = page * PAGE_SIZE
  const pageClips = clips.slice(pageStart, pageStart + PAGE_SIZE)
  const rangeStart = pageStart + 1
  const rangeEnd = pageStart + pageClips.length

  function selectClip(clipId: string) {
    setSelectedId(clipId)
    setMessage('Playback not wired yet')
  }

  return (
    <section className="scroll-mt-20 px-6 py-16" id="try-it-out">
      <div className="mx-auto max-w-4xl space-y-6">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Try it out
        </h2>
        <p className="text-zinc-300">
          Clip playback from S3 is not wired yet. The table is a stand-in.
        </p>

        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-left text-base">
            <thead className="bg-zinc-900 text-amber-400">
              <tr>
                <th className="px-4 py-3 font-medium" scope="col">
                  Clip
                </th>
                <th className="px-4 py-3 font-medium" scope="col">
                  Date + time
                </th>
                <th className="px-4 py-3 font-medium" scope="col">
                  Label
                </th>
                <th className="px-4 py-3 font-medium" scope="col">
                  Classification
                </th>
              </tr>
            </thead>
            <tbody>
              {pageClips.map((clip) => {
                const matched = clip.classification === clip.label
                const selected = selectedId === clip.id
                return (
                  <tr
                    aria-selected={selected}
                    className={`cursor-pointer border-t border-zinc-800 ${
                      selected ? 'bg-zinc-800' : 'hover:bg-zinc-800/80'
                    }`}
                    key={clip.id}
                    onClick={() => selectClip(clip.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        selectClip(clip.id)
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
            {rangeStart}–{rangeEnd} of {clips.length}
          </p>
          <button
            className="rounded-md border border-zinc-700 px-4 py-2 text-zinc-100 enabled:hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((current) => current + 1)}
            type="button"
          >
            Next
          </button>
        </div>

        <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
          {message || 'No clip selected'}
        </div>
      </div>
    </section>
  )
}
