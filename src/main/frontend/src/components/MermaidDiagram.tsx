import { useEffect, useId, useState } from 'react'
import mermaid from 'mermaid'
import { ensureMermaid } from './mermaidSetup'

export default function MermaidDiagram({ chart }: { chart: string }) {
  const reactId = useId().replace(/[^a-zA-Z0-9]/g, '')
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
          setSvg(next)
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

  if (error) {
    return <p className="text-center text-red-400">{error}</p>
  }
  if (!svg) {
    return <p className="text-center text-zinc-500">Loading diagram…</p>
  }

  return (
    <div
      className="overflow-x-auto [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
