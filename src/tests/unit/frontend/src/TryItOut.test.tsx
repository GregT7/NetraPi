import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TryItOut from '@/components/try-it-out/TryItOut'
import { playbackAccentClass } from '@/components/try-it-out/PlaybackStateDiagram'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { 'Content-Type': 'application/json' },
      status,
    }),
  )
}

function clipRow(
  clipId: number,
  extras?: Partial<{
    classification: string
    dateTime: string
    driving_session_id: number
    flags: string[]
    label: string
  }>,
) {
  return {
    classification: extras?.classification ?? 'Complete Stop',
    clip_id: clipId,
    dateTime: extras?.dateTime ?? '2026-08-16 06:00 PM',
    driving_session_id: extras?.driving_session_id ?? 1,
    flags: extras?.flags ?? ['real_world'],
    id: `clip-${clipId}`,
    label: extras?.label ?? 'Complete Stop',
  }
}

function mintCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.filter(([input]) =>
    String(input).includes('/api/public/clip-download-url'),
  )
}

async function flushMintDebounce() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
}

describe('TryItOut', () => {
  it('loads confirmed clips and plays a minted URL', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/public/clips')) {
        return jsonResponse({
          clips: [
            clipRow(10, {
              classification: 'Rolling Stop',
              label: 'Complete Stop',
            }),
          ],
          live_url_max: 20,
          live_urls: 1,
        })
      }
      return jsonResponse({
        expires_in: 120,
        live_url_max: 20,
        live_urls: 2,
        url: 'https://s3.example/clip.mp4',
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    expect(screen.getByText('Live S3 links 1/20')).toBeTruthy()
    expect(screen.getByText('Calibrated Accuracy: n/a (0/0 clips)')).toBeTruthy()
    expect(screen.getByText('Field Accuracy: 0% (0/1 clip)')).toBeTruthy()
    expect(screen.getByText('False Positives: 0% (0/1 clip)')).toBeTruthy()
    expect(screen.getByText('Clips Pending Labels: 0')).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Session' })).toBeTruthy()
    expect(screen.getByText('1')).toBeTruthy()
    vi.useFakeTimers()
    const scrollIntoView = vi
      .spyOn(HTMLElement.prototype, 'scrollIntoView')
      .mockImplementation(() => {})
    fireEvent.click(screen.getByText('clip-10'))
    expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'start',
      inline: 'nearest',
    })
    await flushMintDebounce()
    expect(screen.getByLabelText('Event clip').getAttribute('src')).toBe(
      'https://s3.example/clip.mp4',
    )
    expect(screen.getByText('Live S3 links 2/20')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/public/clip-download-url',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ clip_id: 10 }),
      }),
    )
  })

  it('shows a 429 from the mint as a retry message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/api/public/clips')) {
          return jsonResponse({ clips: [clipRow(10)], live_url_max: 20, live_urls: 0 })
        }
        return jsonResponse({ detail: 'Too many live playback URLs' }, 429)
      }),
    )

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    vi.useFakeTimers()
    fireEvent.click(screen.getByText('clip-10'))
    await flushMintDebounce()
    expect(screen.getByText('Too many playback requests. Try again shortly.')).toBeTruthy()
  })

  it('pages real clips from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/api/public/clips')) {
          return jsonResponse({
            clips: [10, 11, 12, 13, 14, 15].map((id) => clipRow(id)),
            live_url_max: 20,
            live_urls: 0,
          })
        }
        return jsonResponse({ expires_in: 120, url: 'https://s3.example/clip.mp4' })
      }),
    )

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    expect(screen.getByText('clip-14')).toBeTruthy()
    expect(screen.queryByText('clip-15')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText('clip-15')).toBeTruthy()
    expect(screen.queryByText('clip-10')).toBeNull()
  })

  it('does not invent sample rows when the list is empty', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes('/api/public/clips')) {
          return jsonResponse({ clips: [], live_url_max: 20, live_urls: 0 })
        }
        return jsonResponse({ expires_in: 120, url: 'https://s3.example/clip.mp4' })
      }),
    )

    render(<TryItOut />)
    expect(
      await screen.findByText('No confirmed clips in the database yet.'),
    ).toBeTruthy()
    expect(screen.getByText('Live S3 links 0/20')).toBeTruthy()
    expect(screen.queryByText('clip-12')).toBeNull()
  })

  it('shows unlabeled rows from the API as dash with sky text', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes('/api/public/clips')) {
          return jsonResponse({
            clips: [clipRow(10, { classification: 'Rolling Stop', label: '-' })],
            live_url_max: 20,
            live_urls: 0,
          })
        }
        return jsonResponse({ expires_in: 120, url: 'https://s3.example/clip.mp4' })
      }),
    )

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    const dash = screen.getByText('-')
    expect(dash).toBeTruthy()
    expect(dash.className).not.toContain('text-sky-300')
    expect(dash.className).toContain('truncate px-4')
    expect(dash.closest('tr')?.className).not.toContain('bg-amber')
  })

  it('reports labeled accuracy and unlabeled exclusions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes('/api/public/clips')) {
          return jsonResponse({
            clips: [
              clipRow(10, {
                classification: 'Complete Stop',
                label: 'Complete Stop',
              }),
              clipRow(11, {
                classification: 'Complete Stop',
                label: 'Rolling Stop',
              }),
              clipRow(12, { classification: 'Rolling Stop', label: '-' }),
              clipRow(13, {
                classification: 'Unrelated',
                label: 'Unrelated',
              }),
            ],
            live_url_max: 20,
            live_urls: 0,
          })
        }
        return jsonResponse({ expires_in: 120, url: 'https://s3.example/clip.mp4' })
      }),
    )

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    expect(screen.getByText('Field Accuracy: 50% (1/2 clips)')).toBeTruthy()
    expect(screen.getByText('False Positives: 25% (1/4 clips)')).toBeTruthy()
    expect(screen.getByText('Clips Pending Labels: 1')).toBeTruthy()
  })

  it('shows real-world clips, Field and Calibrated Accuracy, and a Calibrated tag', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes('/api/public/clips')) {
          return jsonResponse({
            clips: [
              clipRow(10, {
                classification: 'Complete Stop',
                flags: ['real_world', 'in_operating_envelope'],
                label: 'Complete Stop',
              }),
              clipRow(11, {
                classification: 'Complete Stop',
                flags: ['real_world'],
                label: 'Rolling Stop',
              }),
              clipRow(12, {
                classification: 'Rolling Stop',
                flags: ['synthetic'],
                label: 'Rolling Stop',
              }),
            ],
            live_url_max: 20,
            live_urls: 0,
          })
        }
        return jsonResponse({ expires_in: 120, url: 'https://s3.example/clip.mp4' })
      }),
    )

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    expect(screen.getByText('clip-11')).toBeTruthy()
    expect(screen.queryByText('clip-12')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Good scenario' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Real world' })).toBeNull()
    expect(screen.getByRole('columnheader', { name: 'Scenario' })).toBeTruthy()
    expect(screen.getByText('Calibrated')).toBeTruthy()
    expect(screen.getByText('Calibrated Accuracy: 100% (1/1 clip)')).toBeTruthy()
    expect(screen.getByText('Field Accuracy: 50% (1/2 clips)')).toBeTruthy()
    expect(screen.getByText('False Positives: 0% (0/2 clips)')).toBeTruthy()
    expect(screen.getByText('Clips Pending Labels: 0')).toBeTruthy()
  })

  it('refetches the live S3 count after the mint TTL', async () => {
    let listLiveUrls = 0
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/public/clips')) {
        return jsonResponse({
          clips: [clipRow(10)],
          live_url_max: 20,
          live_urls: listLiveUrls,
        })
      }
      listLiveUrls = 1
      return jsonResponse({
        expires_in: 120,
        live_url_max: 20,
        live_urls: 1,
        url: 'https://s3.example/clip.mp4',
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    expect(screen.getByText('Live S3 links 0/20')).toBeTruthy()

    vi.useFakeTimers()
    fireEvent.click(screen.getByText('clip-10'))
    await flushMintDebounce()
    expect(screen.getByLabelText('Event clip')).toBeTruthy()
    expect(screen.getByText('Live S3 links 1/20')).toBeTruthy()

    listLiveUrls = 0
    await act(async () => {
      await vi.advanceTimersByTimeAsync(119_000)
    })
    expect(screen.getByText('Live S3 links 1/20')).toBeTruthy()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000)
    })
    expect(screen.getByText('Live S3 links 0/20')).toBeTruthy()
    expect(screen.getByText('clip-10')).toBeTruthy()
  })

  it('mints once for the last row after a burst of clicks', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/public/clips')) {
        return jsonResponse({
          clips: [10, 11, 12].map((id) => clipRow(id)),
          live_url_max: 20,
          live_urls: 0,
        })
      }
      const clipId = JSON.parse(String(init?.body ?? '{}')).clip_id as number
      return jsonResponse({
        expires_in: 120,
        live_url_max: 20,
        live_urls: 1,
        url: `https://s3.example/clip-${clipId}.mp4`,
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    vi.useFakeTimers()
    fireEvent.click(screen.getByText('clip-10'))
    fireEvent.click(screen.getByText('clip-11'))
    fireEvent.click(screen.getByText('clip-12'))
    expect(mintCalls(fetchMock)).toHaveLength(0)
    await flushMintDebounce()
    const posts = mintCalls(fetchMock)
    expect(posts).toHaveLength(1)
    expect(posts[0]?.[1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ clip_id: 12 }),
      }),
    )
    expect(screen.getByLabelText('Event clip').getAttribute('src')).toBe(
      'https://s3.example/clip-12.mp4',
    )
  })

  it('does not mint again when the playing row is clicked', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/public/clips')) {
        return jsonResponse({
          clips: [clipRow(10)],
          live_url_max: 20,
          live_urls: 0,
        })
      }
      return jsonResponse({
        expires_in: 120,
        url: 'https://s3.example/clip.mp4',
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    vi.useFakeTimers()
    fireEvent.click(screen.getByText('clip-10'))
    await flushMintDebounce()
    expect(mintCalls(fetchMock)).toHaveLength(1)
    fireEvent.click(screen.getByText('clip-10'))
    await flushMintDebounce()
    expect(mintCalls(fetchMock)).toHaveLength(1)
  })

  it('replays a cached URL without minting again', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/public/clips')) {
        return jsonResponse({
          clips: [clipRow(10), clipRow(11)],
          live_url_max: 20,
          live_urls: 0,
        })
      }
      const clipId = JSON.parse(String(init?.body ?? '{}')).clip_id as number
      return jsonResponse({
        expires_in: 120,
        live_url_max: 20,
        live_urls: clipId,
        url: `https://s3.example/clip-${clipId}.mp4`,
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    vi.useFakeTimers()
    fireEvent.click(screen.getByText('clip-10'))
    await flushMintDebounce()
    fireEvent.click(screen.getByText('clip-11'))
    await flushMintDebounce()
    expect(mintCalls(fetchMock)).toHaveLength(2)
    expect(screen.getByLabelText('Event clip').getAttribute('src')).toBe(
      'https://s3.example/clip-11.mp4',
    )
    fireEvent.click(screen.getByText('clip-10'))
    expect(mintCalls(fetchMock)).toHaveLength(2)
    expect(screen.getByLabelText('Event clip').getAttribute('src')).toBe(
      'https://s3.example/clip-10.mp4',
    )
  })

  it('defaults to detailed analysis and keeps the minted URL when toggling', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/public/clips')) {
        return jsonResponse({
          clips: [clipRow(10, { classification: 'Rolling Stop' })],
          live_url_max: 20,
          live_urls: 0,
        })
      }
      return jsonResponse({
        areas: {
          classification: 'rolling-stop',
          points: [{ t: 1, area: 0.02 }],
          sample_end_s: 10,
          schema_version: 1,
          t0_s: 5,
        },
        expires_in: 120,
        motion: {
          classification: 'rolling-stop',
          points: [{ t: 6, score: 0.4 }],
          sample_end_s: 10,
          schema_version: 1,
          t0_s: 5,
        },
        transitions: {
          classification: 'rolling-stop',
          schema_version: 1,
          states: [
            { t: 0, id: 'Monitoring' },
            { t: 5, id: 'SampleMotion' },
            { t: 10, id: 'RollingStop' },
          ],
        },
        url: 'https://s3.example/clip.mp4',
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<TryItOut />)
    expect(await screen.findByText('clip-10')).toBeTruthy()
    const checkbox = screen.getByRole('checkbox', { name: 'Detailed Analysis' })
    expect(checkbox).toBeChecked()
    expect(screen.getByLabelText('Event clip slot').className).toContain('w-full')
    expect(screen.getByText('Monitoring').className).not.toContain('border-amber-400')
    vi.useFakeTimers()
    fireEvent.click(screen.getByText('clip-10'))
    await flushMintDebounce()
    const video = screen.getByLabelText('Event clip')
    expect(video.getAttribute('src')).toBe('https://s3.example/clip.mp4')
    expect(video.hasAttribute('controls')).toBe(true)
    expect(video.className).toContain('playback-no-seek')
    expect(screen.getByLabelText('Event clip slot').className).toContain('w-full')
    expect(screen.queryByLabelText('Play clip')).toBeNull()
    expect(screen.getByLabelText('Stop-sign encounter states')).toBeTruthy()
    expect(screen.getByText('Sign Area and Motion')).toBeTruthy()
    expect(document.querySelectorAll('[data-accent-border*="border-violet-600"]')).toHaveLength(0)
    expect(document.querySelectorAll('[data-accent-border*="border-emerald-600"]')).toHaveLength(0)
    expect(document.querySelectorAll('[data-accent-border*="border-red-600"]')).toHaveLength(0)
    fireEvent.click(checkbox)
    expect(checkbox).not.toBeChecked()
    expect(mintCalls(fetchMock)).toHaveLength(1)
    expect(screen.getByLabelText('Event clip').hasAttribute('controls')).toBe(true)
    expect(screen.getByLabelText('Event clip').className).not.toContain(
      'playback-no-seek',
    )
    expect(screen.getByLabelText('Event clip').parentElement?.className).toContain(
      'h-[calc(22rem+9rem+0.75rem)]',
    )
    expect(screen.queryByLabelText('Stop-sign encounter states')).toBeNull()
    fireEvent.click(checkbox)
    expect(checkbox).toBeChecked()
    expect(mintCalls(fetchMock)).toHaveLength(1)
    expect(screen.getByLabelText('Event clip').getAttribute('src')).toBe(
      'https://s3.example/clip.mp4',
    )
  })

  it('accents borders only after the state diagram classifies', () => {
    expect(playbackAccentClass('')).toBeUndefined()
    expect(playbackAccentClass('Monitoring')).toBeUndefined()
    expect(playbackAccentClass('SampleMotion')).toBeUndefined()
    expect(playbackAccentClass('CompleteStop')).toContain('border-emerald-600')
    expect(playbackAccentClass('RollingStop')).toContain('border-violet-600')
    expect(playbackAccentClass('RunThrough')).toContain('border-red-600')
  })
})
