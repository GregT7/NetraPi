import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '@/App'
import { popupSide } from '@/components/diagrams/mermaidPopup'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
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
        name: 'Stop labeled Complete Stop, Rolling Stop, or Run-through Stop after the approach',
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
    expect(screen.getByText(/Complete Stop: 75.9%/)).toBeTruthy()
    expect(screen.getByText(/Run-through Stop: 85.7%/)).toBeTruthy()
    expect(screen.getByText(/Rolling Stop: 76.9%/)).toBeTruthy()
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

  it('shows how-it-works copy, state diagram, shark-fin chart, and rolling vs run-through plot', async () => {
    render(<App />)
    const section = document.getElementById('how-it-works')
    expect(section).toBeTruthy()
    const how = within(section as HTMLElement)
    expect(how.getByRole('heading', { name: 'How it works' })).toBeTruthy()
    expect(how.getByText(/consistent, repeatable event/)).toBeTruthy()
    expect(how.getByText(/easiest to see by thinking through an example/)).toBeTruthy()
    expect(how.getByText(/Imagine this scenario/)).toBeTruthy()
    expect(how.getByText(/3-pronged fork in the road/)).toBeTruthy()
    expect(how.getByText(/The diagram below is that loop/)).toBeTruthy()
    expect(how.getByText('Stop-Sign Encounter States')).toBeTruthy()
    expect(how.queryByText('Start')).toBeNull()
    expect(
      (await how.findAllByText('Monitoring', {}, { timeout: 14_000 })).length,
    ).toBeGreaterThan(0)
    expect((await how.findAllByText("Sample Car's Motion")).length).toBeGreaterThan(0)
    expect((await how.findAllByText('Complete Stop')).length).toBeGreaterThan(0)
    expect((await how.findAllByText('Rolling Stop')).length).toBeGreaterThan(0)
    expect((await how.findAllByText('Run-through Stop')).length).toBeGreaterThan(0)
    expect((await how.findAllByText('Approach Stop Sign Detected')).length).toBeGreaterThan(0)
    expect((await how.findAllByText('Under 5 seconds')).length).toBeGreaterThan(0)
    expect((await how.findAllByText('5 seconds passed')).length).toBeGreaterThan(0)
    expect(how.queryByText('Approach detected')).toBeNull()
    expect(how.queryByText('Unsafe')).toBeNull()
    expect(how.queryByText('Safe')).toBeNull()
    expect(how.queryByText('Box grows then drops after peak')).toBeNull()
    expect(how.getByText(/3 bins shown in the diagram/)).toBeTruthy()
    expect(how.getByText(/returns to monitoring and waits for the next approach/)).toBeTruthy()
    expect(how.getByText(/pretrained TFLite model/)).toBeTruthy()
    expect(how.getByText(/"shark-fin" like pattern/)).toBeTruthy()
    expect(how.getByText('Sign Area and Motion Over Time')).toBeTruthy()
    expect(how.getByText('Sign Area (% of Frame)')).toBeTruthy()
    expect(how.getAllByText('Motion (px / Frame)').length).toBeGreaterThan(0)
    expect(how.getByText(/called the "peak\."/)).toBeTruthy()
    expect(how.getByText(/Farneback Optical Flow Algorithm/)).toBeTruthy()
    expect(how.getByText(/k-nearest neighbors \(k-NN\)/)).toBeTruthy()
    expect(how.getByText(/multi-stage and uses five features in total/)).toBeTruthy()
    expect(how.getByText(/the second stage uses just two of those values/)).toBeTruthy()
    expect(
      how.getByText(
        'Rolling Stop vs Run-through Stop by Minimum Motion and Total Sign Area',
      ),
    ).toBeTruthy()
    expect(how.getByText('Minimum Motion (px / Frame)')).toBeTruthy()
    expect(how.getByText('Total Sign Area (%)')).toBeTruthy()
    expect(how.getByText(/cellular hotspot my phone is hosting/)).toBeTruthy()
    expect(how.queryByText('Video coming soon')).toBeNull()
    expect(how.queryByText('Approach to classification')).toBeNull()
    expect(how.queryByText('Keep Polling')).toBeNull()
    expect(how.queryByText('Hierarchical KNN')).toBeNull()
    expect(how.queryByText('The five features')).toBeNull()
    expect(how.queryByText('Stage 1 PCA')).toBeNull()
    expect(how.queryByText('Stage 2 Features')).toBeNull()
    expect(how.queryByText('Mean Motion vs Min Motion')).toBeNull()
    expect(screen.queryByText('104 clips')).toBeNull()
    expect(screen.queryByText('Coming soon.')).toBeNull()
  }, 15_000)

  it('shows stacked architecture figure captions', async () => {
    render(<App />)
    expect(screen.getByText('Hardware Architecture')).toBeTruthy()
    expect(screen.getByText('Software Architecture')).toBeTruthy()
    expect(screen.queryByRole('img', { name: 'Hardware Architecture' })).toBeNull()
    expect(screen.queryByRole('img', { name: 'Software Architecture' })).toBeNull()
    expect(
      (await screen.findAllByText('Raspberry Pi 5', {}, { timeout: 14_000 }))
        .length,
    ).toBeGreaterThan(0)
    expect(
      (await screen.findAllByText('Windshield Mount', {}, { timeout: 14_000 }))
        .length,
    ).toBeGreaterThan(0)
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
    expect((await screen.findAllByText('GPIO Buzzer')).length).toBeGreaterThan(0)
  }, 15_000)

  it('shows a hardware hover card and not a software-diagram card', async () => {
    render(<App />)
    const hardware = screen.getByText('Hardware Architecture').closest('figure')
    expect(hardware).toBeTruthy()
    const piLabel = await within(hardware as HTMLElement).findByText(
      'Raspberry Pi 5',
      {},
      { timeout: 14_000 },
    )
    const wrap = (hardware as HTMLElement).querySelector('[data-diagram-wrap]')
    expect(wrap).toBeTruthy()
    expect(wrap?.classList.contains('hardware-diagram')).toBe(true)
    await waitFor(() => {
      expect(wrap?.classList.contains('is-in-view')).toBe(true)
      expect(wrap?.querySelector('.hardware-shine-ring')).toBeTruthy()
    })
    fireEvent.mouseOver(within(hardware as HTMLElement).getByText('Raspberry Pi 5'))
    expect(
      screen.getByText(/runs capture, Coral inference, and local SQLite/),
    ).toBeTruthy()
    expect(wrap?.querySelector('[data-shine-key="Raspberry Pi 5"]')).toBeNull()
    expect(wrap?.querySelector('.hardware-shine-ring')).toBeTruthy()
    fireEvent.mouseLeave(wrap as HTMLElement)
    expect(
      screen.queryByText(/runs capture, Coral inference, and local SQLite/),
    ).toBeNull()
    expect(popupSide(100, 500)).toBe('right')
    expect(popupSide(800, 500)).toBe('left')
    const hotspot = within(hardware as HTMLElement).getByText('Cellular Hotspot')
    const hotspotNode = hotspot.closest('.node') ?? hotspot
    vi.spyOn(hotspotNode, 'getBoundingClientRect').mockReturnValue({
      x: 800,
      y: 40,
      top: 40,
      left: 800,
      right: 920,
      bottom: 100,
      width: 120,
      height: 60,
      toJSON: () => ({}),
    })
    fireEvent.mouseOver(hotspot)
    const card = document.querySelector('[data-hardware-card]')
    expect(card?.getAttribute('data-side')).toBe('left')
    expect((card as HTMLElement).style.top).toBe('40px')
    expect(Number.parseFloat((card as HTMLElement).style.left)).toBeLessThan(800)
    const software = screen.getByText('Software Architecture').closest('figure')
    expect(software).toBeTruthy()
    expect(
      (software as HTMLElement)
        .querySelector('[data-diagram-wrap]')
        ?.classList.contains('hardware-diagram'),
    ).toBe(false)
    fireEvent.mouseOver(
      within(software as HTMLElement).getByText('SQLAlchemy'),
    )
    expect(
      within(software as HTMLElement).queryByText(
        /runs capture, Coral inference, and local SQLite/,
      ),
    ).toBeNull()
    expect(
      within(hardware as HTMLElement).getByText('GPIO Buzzer'),
    ).toBeTruthy()
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
