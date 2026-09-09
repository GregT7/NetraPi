import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@/App'
import { popupSide } from '@/components/diagrams/mermaidPopup'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('App', () => {
  it('renders a single NetraPi heading', () => {
    render(<App />)
    expect(screen.getAllByRole('heading', { name: 'NetraPi' })).toHaveLength(1)
    expect(screen.queryByText('GIF coming soon')).toBeNull()
    expect(
      screen.getByRole('img', {
        name: 'NetraPi watching the road and labeling a stop',
      }).getAttribute('src'),
    ).toBe('/gifs/overview.gif?v=1')
    expect(
      screen.getByRole('img', {
        name: 'NetraPi hardware mounted in the car',
      }).getAttribute('src'),
    ).toBe('/gifs/hardware-setup.gif?v=1')
    expect(
      screen.getByText(/Raspberry Pi 5, Coral TPU, dash camera/),
    ).toBeTruthy()
    expect(
      screen.getByText(/grows in view and then drops away/),
    ).toBeTruthy()
    expect(
      screen.getByRole('img', {
        name: 'Stop sign growing in the camera view, then dropping away',
      }).getAttribute('src'),
    ).toBe('/gifs/approach.gif?v=3')
    expect(
      screen.getByText(/banner is only included in gifs/),
    ).toBeTruthy()
    expect(
      screen.getByRole('img', {
        name: 'Stop labeled Complete Stop, Rolling Stop, or Run-through Stop after the approach',
      }).getAttribute('src'),
    ).toBe('/gifs/classification.gif?v=1')
    expect(
      screen.getByRole('img', {
        name: 'Clip saved locally and uploaded to S3',
      }).getAttribute('src'),
    ).toBe('/gifs/s3-persist.gif?v=1')
    expect(
      screen.getByText(/went from the Pi in the car to S3/),
    ).toBeTruthy()
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
      within(nav).getByRole('link', { name: 'How It Works' }).getAttribute('href'),
    ).toBe('#how-it-works')
    expect(
      within(nav).getByRole('link', { name: 'Try It Out' }).getAttribute('href'),
    ).toBe('#try-it-out')
    expect(within(nav).queryByRole('link', { name: 'Demo' })).toBeNull()
    expect(within(nav).getByRole('link', { name: 'Links' }).getAttribute('href')).toBe(
      '#links',
    )
  })

  it('exposes the page sections', () => {
    render(<App />)
    expect(document.getElementById('overview')).toBeTruthy()
    expect(document.getElementById('how-it-works')).toBeTruthy()
    expect(document.getElementById('demo')).toBeNull()
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
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes('/api/public/clips')) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                clips: [
                  {
                    classification: 'Complete Stop',
                    clip_id: 10,
                    dateTime: '2026-08-16 06:00 PM',
                    driving_session_id: 1,
                    flags: ['real_world', 'in_operating_envelope'],
                    id: 'clip-10',
                    label: 'Complete Stop',
                  },
                  {
                    classification: 'Complete Stop',
                    clip_id: 11,
                    dateTime: '2026-08-16 07:00 PM',
                    driving_session_id: 1,
                    flags: ['real_world'],
                    id: 'clip-11',
                    label: 'Rolling Stop',
                  },
                  {
                    classification: 'Complete Stop',
                    clip_id: 12,
                    dateTime: '2026-08-16 08:00 PM',
                    driving_session_id: 1,
                    flags: ['real_world'],
                    id: 'clip-12',
                    label: 'Unrelated',
                  },
                  {
                    classification: 'Rolling Stop',
                    clip_id: 13,
                    dateTime: '2026-08-16 09:00 PM',
                    driving_session_id: 1,
                    flags: ['synthetic'],
                    id: 'clip-13',
                    label: 'Rolling Stop',
                  },
                ],
                live_url_max: 20,
                live_urls: 0,
              }),
              { headers: { 'Content-Type': 'application/json' }, status: 200 },
            ),
          )
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              expires_in: 120,
              url: 'https://s3.example/clip.mp4',
            }),
            { headers: { 'Content-Type': 'application/json' }, status: 200 },
          ),
        )
      }),
    )

    render(<App />)
    const overview = document.getElementById('overview')
    expect(overview).toBeTruthy()
    expect(overview?.querySelector('#results')).toBeTruthy()
    expect(screen.getAllByRole('heading', { name: 'Results' }).length).toBeGreaterThan(0)
    expect(screen.getByText(/Unrelated: 96.2% \(26 clips\)/)).toBeTruthy()
    expect(screen.getByText(/Complete Stop: 75.9% \(29 clips\)/)).toBeTruthy()
    expect(screen.getByText(/Run-through Stop: 85.7% \(21 clips\)/)).toBeTruthy()
    expect(screen.getByText(/Rolling Stop: 76.9% \(26 clips\)/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Leave-One-Out Accuracy' })).toBeTruthy()
    expect(screen.getByText(/83.3% of 102 clips predicted correctly/)).toBeTruthy()
    expect(screen.getByText(/leave-one-out \(LOO\)/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Field Accuracy' })).toBeTruthy()
    expect(
      screen.getByText(
        /Complete-stop, rolling-stop, and run-through clips from the live evaluation, excluding parking-lot \/ synthetic clips. The model's prediction vs my review./,
      ),
    ).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Calibrated Accuracy' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Limitations' })).toBeTruthy()
    expect(
      screen.getByText(
        /only clips in the right-most lane with the stop line close to the sign are included. This is the accuracy after the limitations of the design are factored in./,
      ),
    ).toBeTruthy()
    expect(await screen.findByText('50% (1/2 clips predicted correctly)')).toBeTruthy()
    expect(screen.getByText('100% (1/1 clips predicted correctly)')).toBeTruthy()
    expect(screen.getByText('1 false positive (unrelated detections)')).toBeTruthy()
    expect(screen.getByText('0 false positives (unrelated detections)')).toBeTruthy()
    expect(localStorage.getItem('netrapi.resultsAccuracy.v1')).toContain('"percent":50')
    expect(screen.getByRole('heading', { name: 'What It Is' })).toBeTruthy()
    expect(
      screen.getByText(/combination of "Netradyne" and "Pi"/),
    ).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Constraints' })).toBeTruthy()
    expect(screen.getByText(/stay under \$1,000/)).toBeTruthy()
    expect(screen.getByText(/2010 Mazda3/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Why I Made It' })).toBeTruthy()
    expect(
      screen.getByText(/Amazon affiliated DSP \(Delivery Service Partner\)/),
    ).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'What It Can Do' })).toBeTruthy()
    expect(screen.getByText(/help users improve driving safety/)).toBeTruthy()
    expect(screen.queryByText(/mishaps being public/)).toBeNull()
    expect(screen.getByRole('heading', { name: 'Try It Out' })).toBeTruthy()
    expect(screen.queryByText('Demo clip coming soon')).toBeNull()
    expect(screen.queryByTitle('NetraPi demo')).toBeNull()
    expect(screen.getByRole('columnheader', { name: 'Timestamp' })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Session' })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Prediction' })).toBeTruthy()
    expect(await screen.findByText('clip-10')).toBeTruthy()
    expect(screen.getByText('clip-11')).toBeTruthy()
    expect(screen.getByText('clip-12')).toBeTruthy()
    expect(screen.queryByText('clip-13')).toBeNull()
    expect(screen.getByRole('columnheader', { name: 'Scenario' })).toBeTruthy()
    expect(screen.getByText('Calibrated')).toBeTruthy()
    expect(screen.getByText('Field Accuracy: 50% (1/2 clips)')).toBeTruthy()
    expect(screen.getByText('Calibrated Accuracy: 100% (1/1 clip)')).toBeTruthy()
    expect(screen.getByText('False Positives: 33% (1/3 clips)')).toBeTruthy()
    expect(screen.getByText('Clips Pending Labels: 0')).toBeTruthy()
  })

  it('shows cached Field Accuracy when the clips API fails', async () => {
    localStorage.setItem(
      'netrapi.resultsAccuracy.v1',
      JSON.stringify({
        field: {
          classes: [
            { count: 4, matches: 3, name: 'Complete Stop', percent: 75 },
            { count: 0, matches: 0, name: 'Rolling Stop', percent: null },
            { count: 0, matches: 0, name: 'Run-through Stop', percent: null },
          ],
          falsePositives: 2,
          labeled: 4,
          matches: 3,
          percent: 75,
          unlabeled: 0,
        },
        ideal: {
          classes: [
            { count: 1, matches: 1, name: 'Complete Stop', percent: 100 },
            { count: 0, matches: 0, name: 'Rolling Stop', percent: null },
            { count: 0, matches: 0, name: 'Run-through Stop', percent: null },
          ],
          falsePositives: 0,
          labeled: 1,
          matches: 1,
          percent: 100,
          unlabeled: 0,
        },
      }),
    )
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('offline'))),
    )

    render(<App />)
    expect(
      await screen.findByText(/Showing last saved Field and Calibrated Accuracy/),
    ).toBeTruthy()
    expect(screen.getByText('75% (3/4 clips predicted correctly)')).toBeTruthy()
    expect(screen.getByText('2 false positives (unrelated detections)')).toBeTruthy()
  })

  it('shows how-it-works copy, state diagram, shark-fin chart, and rolling vs run-through plot', async () => {
    render(<App />)
    const section = document.getElementById('how-it-works')
    expect(section).toBeTruthy()
    const how = within(section as HTMLElement)
    expect(how.getByRole('heading', { name: 'How It Works' })).toBeTruthy()
    expect(how.getByText(/live loop on the Pi/)).toBeTruthy()
    expect(how.getByText(/approach is the event we look for/)).toBeTruthy()
    expect(how.getByText(/easiest way to see the event is with a short example/)).toBeTruthy()
    expect(how.getByText(/Imagine this scenario/)).toBeTruthy()
    expect(how.getByText(/three-pronged fork in the road/)).toBeTruthy()
    expect(how.getByText(/The diagram below is that loop/)).toBeTruthy()
    expect(how.getByText('Stop-Sign Encounter States')).toBeTruthy()
    expect(
      how
        .getByRole('img', {
          name: 'Stop sign growing in the camera view, then dropping away',
        })
        .getAttribute('src'),
    ).toBe('/gifs/approach.gif?v=3')
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
    expect(how.getByText(/shark-fin-like pattern/)).toBeTruthy()
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
        'Classification Scatterplot for Rolling vs Run-through Stops',
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
    fireEvent.mouseOver(within(hardware as HTMLElement).getByText('Windshield Mount'))
    expect(
      screen.getByText(/3D-printed suction mount holds the camera/),
    ).toBeTruthy()
    expect(
      screen
        .getByRole('img', {
          name: '3D-printed suction mount for the windshield camera',
        })
        .getAttribute('src'),
    ).toBe('/gifs/cam-mount.gif?v=1')
    fireEvent.mouseLeave(wrap as HTMLElement)
    const hardwarePhotos = [
      [
        'Raspberry Pi 5',
        'Raspberry Pi 5 in the in-car build',
        '/gifs/pi.gif?v=1',
      ],
      ['Arducam USB', 'Arducam USB camera', '/images/arducam.avif?v=1'],
      ['Coral USB TPU', 'Google Coral USB TPU', '/images/coral-tpu.avif?v=1'],
      [
        'Portable Battery',
        '100W USB-C power bank with AC outlet',
        '/images/battery.avif?v=1',
      ],
      [
        'GPIO Buzzer',
        'KY-006 passive piezo buzzer module',
        '/images/buzzer.avif?v=1',
      ],
      [
        'Phone',
        'iPhone 11 used as the cellular hotspot',
        '/images/iphone-11.avif?v=1',
      ],
      [
        'Cellular Hotspot',
        'Phone hotspot used to upload clips from the car',
        '/gifs/hotspot.gif?v=1',
      ],
    ] as const
    for (const [label, alt, src] of hardwarePhotos) {
      fireEvent.mouseOver(within(hardware as HTMLElement).getByText(label))
      const photo = screen.getByRole('img', { name: alt })
      expect(photo.getAttribute('src')).toBe(src)
      if (label === 'Phone') {
        expect(photo.className).toContain('max-h-36')
        expect(photo.className).not.toContain('w-full')
      } else {
        expect(photo.className).toContain('w-full')
      }
      fireEvent.mouseLeave(wrap as HTMLElement)
    }
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
    expect(screen.queryByText('YouTube (coming soon)')).toBeNull()
  })
})
