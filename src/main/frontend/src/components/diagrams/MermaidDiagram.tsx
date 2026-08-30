import { useEffect, useId, useRef, useState } from 'react'
import mermaid from 'mermaid'
import { ensureMermaid } from './mermaidSetup'

function tidySvg(svg: string) {
  return svg.replace(/max-width:\s*512px;?/g, 'max-width:100%;')
}

export default function MermaidDiagram({
  chart,
  plainLinks = false,
}: {
  chart: string
  plainLinks?: boolean
}) {
  const reactId = useId().replace(/[^a-zA-Z0-9]/g, '')
  const rootRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const renderId = `mermaid${reactId}${Math.random().toString(36).slice(2, 8)}`

    async function run() {
      try {
        ensureMermaid()
        const { svg: next } = await mermaid.render(renderId, chart)
        if (!cancelled) {
          setSvg(tidySvg(next))
          setError('')
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Diagram failed to render')
        }
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [chart, reactId])

  useEffect(() => {
    const root = rootRef.current
    if (!root || !svg) {
      return
    }
    root.querySelectorAll('.cluster-label').forEach((label) => {
      if (!label.textContent?.trim()) {
        label.setAttribute('display', 'none')
      }
    })
  }, [svg])

  if (error) {
    return <p className="text-center text-red-400">{error}</p>
  }
  if (!svg) {
    return <p className="text-center text-zinc-500">Loading diagram…</p>
  }

  return (
    <div
      ref={rootRef}
      className={`overflow-x-auto [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full ${
        plainLinks
          ? '[&_marker]:hidden [&_path]:[marker-end:none] [&_path]:[marker-start:none]'
          : ''
      }`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
