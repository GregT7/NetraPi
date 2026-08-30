import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import App from '@/App'

afterEach(() => {
  cleanup()
})

describe('App', () => {
  it('renders a single NetraPi heading', () => {
    render(<App />)
    expect(screen.getAllByRole('heading', { name: 'NetraPi' })).toHaveLength(1)
    expect(screen.getAllByText('GIF coming soon').length).toBeGreaterThan(0)
    expect(
      screen.getByText(/grow in view and then drop away/),
    ).toBeTruthy()
    expect(
      screen.getByRole('img', {
        name: 'Stop sign growing in the camera view, then dropping away',
      }).getAttribute('src'),
    ).toBe('/gifs/approach.gif?v=3')
    expect(
      screen.getByText(/records motion for five seconds/),
    ).toBeTruthy()
    expect(
      screen.getByRole('img', {
        name: 'Stop labeled complete, rolling, or run-through after the approach',
      }).getAttribute('src'),
    ).toBe('/gifs/classification.gif?v=1')
    expect(screen.queryByText('Finding a stop sign')).toBeNull()
    expect(screen.queryByText('Labeling the stop')).toBeNull()
  })

  it('has in-page nav links', () => {
    render(<App />)
    const nav = screen.getByRole('navigation', { name: 'On this page' })
    expect(within(nav).getByRole('link', { name: 'Overview' }).getAttribute('href')).toBe(
      '#overview',
    )
    expect(
      within(nav).getByRole('link', { name: 'How it works' }).getAttribute('href'),
    ).toBe('#how-it-works')
    expect(within(nav).getByRole('link', { name: 'Demo' }).getAttribute('href')).toBe(
      '#demo',
    )
    expect(
      within(nav).getByRole('link', { name: 'Try it out' }).getAttribute('href'),
    ).toBe('#try-it-out')
    expect(within(nav).getByRole('link', { name: 'Links' }).getAttribute('href')).toBe(
      '#links',
    )
  })

  it('exposes the page sections', () => {
    render(<App />)
    expect(document.getElementById('overview')).toBeTruthy()
    expect(document.getElementById('how-it-works')).toBeTruthy()
    expect(document.getElementById('demo')).toBeTruthy()
    expect(document.getElementById('results')).toBeTruthy()
    expect(document.getElementById('try-it-out')).toBeTruthy()
    expect(document.getElementById('links')).toBeTruthy()
  })

  it('does not show the old subtitle', () => {
    render(<App />)
    expect(
      screen.queryByText('Stop-sign event detection at the edge'),
    ).toBeNull()
  })

  it('shows overview results and the try-it-out table', async () => {
    render(<App />)
    const overview = document.getElementById('overview')
    expect(overview).toBeTruthy()
    expect(overview?.querySelector('#results')).toBeTruthy()
    expect(screen.getAllByRole('heading', { name: 'Results' }).length).toBeGreaterThan(0)
    expect(screen.getByText(/Unrelated: 96.2%/)).toBeTruthy()
    expect(screen.getByText(/Complete stop: 75.9%/)).toBeTruthy()
    expect(screen.getByText(/Run-through: 85.7%/)).toBeTruthy()
    expect(screen.getByText(/Rolling stop: 76.9%/)).toBeTruthy()
    expect(screen.getByText(/83.3%/)).toBeTruthy()
    expect(screen.queryByText('Demo clip coming soon')).toBeNull()
    expect(screen.getByTitle('NetraPi demo').getAttribute('src')).toBe(
      'https://www.youtube-nocookie.com/embed/VPODr7JDU3w',
    )
    expect(screen.getByRole('columnheader', { name: 'Timestamp' })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Prediction' })).toBeTruthy()
    expect(await screen.findByText('Could not load clips from the database.')).toBeTruthy()
    expect(screen.queryByText('clip-12')).toBeNull()
  })

  it('shows how-it-works hierarchy, Farneback, and feature plots', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'How it works' })).toBeTruthy()
    expect(screen.getByText('Keep Polling')).toBeTruthy()
    expect(screen.getByText('Approach Detected?')).toBeTruthy()
    expect(screen.getByText('Collect Motion (5 s)')).toBeTruthy()
    expect(screen.getByText('Hierarchical KNN')).toBeTruthy()
    expect(screen.getByText('Unsafe')).toBeTruthy()
    expect(screen.getByText(/Farneback/)).toBeTruthy()
    expect(screen.getByText('Sign Area and Motion')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'The five features' })).toBeTruthy()
    expect(screen.getByText(/Stage 1 uses four of them/)).toBeTruthy()
    expect(screen.getByText(/Stage 2 only runs on Unsafe/)).toBeTruthy()
    expect(screen.getByText('Stage 1 and 2')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Keep Polling' }))
    expect(screen.getByText(/Idle loop/)).toBeTruthy()
    fireEvent.pointerDown(screen.getByText('False'))
    expect(screen.queryByText(/Idle loop/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Approach Detected?' }))
    expect(screen.getByText(/grew then shrank/)).toBeTruthy()
    expect(screen.getByText(/Labeled unrelated clips/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Collect Motion (5 s)' }))
    expect(screen.getByText(/records motion for 5 seconds/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Stage 1 KNN' }))
    expect(screen.getByText('Mean motion')).toBeTruthy()
    expect(screen.getByText('Min motion')).toBeTruthy()
    expect(screen.getByText('P95 motion')).toBeTruthy()
    expect(screen.getByText('Stop fraction')).toBeTruthy()
    expect(screen.getByText(/quietest moment/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Stage 2 KNN' }))
    expect(screen.getByText('Sign area')).toBeTruthy()
    expect(screen.getByText(/sign-box size/)).toBeTruthy()
    expect(screen.getByText(/PC1 is 72%/)).toBeTruthy()
    expect(screen.getByText(/PC2 is 21%/)).toBeTruthy()
    expect(screen.getByText(/principal components/)).toBeTruthy()
    expect(screen.getByText(/every pair of those four raw numbers/)).toBeTruthy()
    expect(screen.getByText('Stage 1 PCA')).toBeTruthy()
    expect(screen.getByText('Stage 2 Features')).toBeTruthy()
    expect(screen.getByText('Mean Motion vs Min Motion')).toBeTruthy()
    const placeholder = screen.getByText('Video coming soon')
    const videoLabel = screen.getByText('Approach to classification')
    const pollingCopy = screen.getByText(/The Pi keeps polling for an approach/)
    expect(placeholder.compareDocumentPosition(videoLabel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(videoLabel.compareDocumentPosition(pollingCopy) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText('104 clips')).toBeNull()
    expect(screen.queryByText('Coming soon.')).toBeNull()
  })

  it('shows stacked architecture figure captions', async () => {
    render(<App />)
    expect(screen.getByText('Hardware architecture')).toBeTruthy()
    expect(screen.getByText('Software architecture')).toBeTruthy()
    expect(screen.queryByRole('img', { name: 'Hardware architecture' })).toBeNull()
    expect(screen.queryByRole('img', { name: 'Software architecture' })).toBeNull()
    expect((await screen.findAllByText('Raspberry Pi 5')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Windshield Mount')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Portable Battery')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Cellular Hotspot')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('SQLAlchemy')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('SQLModel')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Alembic')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Uvicorn')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Vercel')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('TypeScript')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Render')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Shadcn')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Docker')).length).toBeGreaterThan(0)
  }, 15_000)

  it('links GitHub and LinkedIn', () => {
    render(<App />)
    expect(screen.getByRole('link', { name: 'GitHub' }).getAttribute('href')).toBe(
      'https://github.com/GregT7/NetraPi',
    )
    expect(screen.getByRole('link', { name: 'LinkedIn' }).getAttribute('href')).toBe(
      'https://www.linkedin.com/in/gregterrell7/',
    )
    expect(screen.queryByRole('link', { name: 'YouTube' })).toBeNull()
    expect(screen.getByText('YouTube (coming soon)')).toBeTruthy()
  })
})
