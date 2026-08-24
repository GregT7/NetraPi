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

  it('shows results labels and the try-it-out stub', () => {
    render(<App />)
    expect(screen.getAllByRole('heading', { name: 'Results' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Unrelated').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Complete stop').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Run-through').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rolling stop').length).toBeGreaterThan(0)
    expect(screen.getByRole('columnheader', { name: 'Date + time' })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Classification' })).toBeTruthy()
    fireEvent.click(screen.getByText('clip-12'))
    expect(screen.getByText('Playback not wired yet')).toBeTruthy()
  })

  it('shows stacked architecture figure captions', () => {
    render(<App />)
    expect(screen.getByText('Hardware architecture')).toBeTruthy()
    expect(screen.getByText('Software architecture')).toBeTruthy()
    expect(screen.queryByRole('img', { name: 'Hardware architecture' })).toBeNull()
    expect(screen.queryByRole('img', { name: 'Software architecture' })).toBeNull()
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
