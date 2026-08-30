import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TryItOut from '@/components/try-it-out/TryItOut'

afterEach(() => {
  cleanup()
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
    classification: extras?.classification ?? 'Complete stop',
    clip_id: clipId,
    dateTime: extras?.dateTime ?? '2026-08-16 18:00',
    id: `clip-${clipId}`,
    label: extras?.label ?? 'Complete stop',
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
              classification: 'Rolling stop',
              label: 'Complete stop',
            }),
          ],
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
    fireEvent.click(screen.getByText('clip-10'))
    expect((await screen.findByLabelText('Event clip')).getAttribute('src')).toBe(
      'https://s3.example/clip.mp4',
    )
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
          return jsonResponse({ clips: [clipRow(10)] })
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
          return jsonResponse({ clips: [] })
        }
        return jsonResponse({ expires_in: 120, url: 'https://s3.example/clip.mp4' })
      }),
    )

    render(<TryItOut />)
    expect(
      await screen.findByText('No confirmed clips in the database yet.'),
    ).toBeTruthy()
    expect(screen.queryByText('clip-12')).toBeNull()
  })
})
