import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TryItOut from '@/components/try-it-out/TryItOut'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
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
  extras?: Partial<{ classification: string; dateTime: string; label: string }>,
) {
  return {
    classification: extras?.classification ?? 'Complete Stop',
    clip_id: clipId,
    dateTime: extras?.dateTime ?? '2026-08-16 06:00 PM',
    id: `clip-${clipId}`,
    label: extras?.label ?? 'Complete Stop',
  }
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
    fireEvent.click(screen.getByText('clip-10'))
    expect((await screen.findByLabelText('Event clip')).getAttribute('src')).toBe(
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
    fireEvent.click(await screen.findByText('clip-10'))
    expect(
      await screen.findByText('Too many playback requests. Try again shortly.'),
    ).toBeTruthy()
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
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })
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
})
