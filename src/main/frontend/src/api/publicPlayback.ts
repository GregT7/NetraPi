export function apiUrl(path: string): string {
  const base = String(import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

export type PublicClipRow = {
  classification: string
  clipId: number
  dateTime: string
  id: string
  label: string
}

export type PublicClipList = {
  clips: PublicClipRow[]
  liveUrlMax: number
  liveUrls: number
}

type PublicClipListResponse = {
  clips: Array<{
    classification: string
    clip_id: number
    dateTime: string
    id: string
    label: string
  }>
  live_url_max?: number
  live_urls?: number
}

type PublicMintResponse = {
  areas?: PlaybackSeriesFile | null
  expires_in: number
  live_url_max?: number
  live_urls?: number
  motion?: PlaybackSeriesFile | null
  transitions?: PlaybackTransitionsFile | null
  url: string
}

export type PlaybackSeriesPoint = {
  area?: number
  score?: number
  t: number
}

export type PlaybackSeriesFile = {
  classification?: string
  points: PlaybackSeriesPoint[]
  sample_end_s: number
  schema_version: number
  t0_s: number
}

export type PlaybackTransitionState = {
  id: string
  t: number
}

export type PlaybackTransitionsFile = {
  classification?: string
  schema_version: number
  states: PlaybackTransitionState[]
}

export async function fetchPublicClips(signal?: AbortSignal): Promise<PublicClipList> {
  let response: Response
  try {
    response = await fetch(apiUrl('/api/public/clips'), { signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new Error('Could not load clips from the database.')
  }
  if (!response.ok) {
    throw new Error('Could not load clips from the database.')
  }
  const body = (await response.json()) as PublicClipListResponse
  if (!Array.isArray(body.clips)) {
    throw new Error('Could not load clips from the database.')
  }
  return {
    clips: body.clips.map((clip) => ({
      classification: clip.classification,
      clipId: clip.clip_id,
      dateTime: clip.dateTime,
      id: clip.id,
      label: clip.label,
    })),
    liveUrlMax: body.live_url_max ?? 20,
    liveUrls: body.live_urls ?? 0,
  }
}

export async function mintPublicClipUrl(
  clipId: number,
  signal?: AbortSignal,
): Promise<PublicMintResponse> {
  let response: Response
  try {
    response = await fetch(apiUrl('/api/public/clip-download-url'), {
      body: JSON.stringify({ clip_id: clipId }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new Error('Could not reach the playback API.')
  }
  if (response.status === 429) {
    throw new Error('Too many playback requests. Try again shortly.')
  }
  if (response.status === 400) {
    throw new Error('This clip is not available for playback.')
  }
  if (response.status === 404) {
    throw new Error('Clip not found.')
  }
  if (response.status === 503) {
    throw new Error('Playback is temporarily unavailable.')
  }
  if (!response.ok) {
    throw new Error(`Could not mint a playback URL (${response.status}).`)
  }
  const body = (await response.json()) as PublicMintResponse
  if (!body.url) {
    throw new Error('Playback URL missing from the response.')
  }
  return body
}
