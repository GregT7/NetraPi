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

  it('shows results labels and the try-it-out stub', async () => {
    render(<App />)
    expect(screen.getAllByRole('heading', { name: 'Results' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Unrelated').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Complete stop').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Run-through').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rolling stop').length).toBeGreaterThan(0)
    expect(await screen.findByText('104 clips', undefined, { timeout: 10_000 })).toBeTruthy()
    expect(await screen.findByText('Hierarchical kNN')).toBeTruthy()
    expect(screen.getAllByText('Rolling / run-through').length).toBeGreaterThan(0)
    expect(screen.getByText(/PC1 is 72%/)).toBeTruthy()
    expect(screen.getByText(/PC2 is 21%/)).toBeTruthy()
    expect(screen.getByText(/principal components/)).toBeTruthy()
    expect(screen.getByText(/every pair of those four raw numbers/)).toBeTruthy()
    expect(screen.getByText(/mean motion, min motion, p95 motion, and stop fraction/)).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Classification' })).toBeTruthy()
    fireEvent.click(screen.getByText('clip-12'))
    expect(screen.getByText('Playback not wired yet')).toBeTruthy()
    expect(screen.getByText('clip-70')).toBeTruthy()
    expect(screen.queryByText('clip-81')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText('clip-81')).toBeTruthy()
    expect(screen.queryByText('clip-12')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    expect(screen.getByText('clip-12')).toBeTruthy()
  }, 20_000)

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
  })

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
