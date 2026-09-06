import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import mermaid from 'mermaid'
import { ensureMermaid } from './mermaidSetup'
import type { HardwareNodeCard } from './hardwareNodeCards'
import { placePopup } from './mermaidPopup'

function tidySvg(svg: string) {
  return svg
    .replace(/max-width:\s*512px;?/g, 'max-width:100%;')
    .replace(/cursor:\s*grabbing?/gi, 'cursor:default')
}

function cardFromTarget(
  target: EventTarget | null,
  root: HTMLElement,
  nodeCards: Record<string, HardwareNodeCard>,
): { card: HardwareNodeCard; node: Element } | null {
  if (!(target instanceof Element) || !root.contains(target)) {
    return null
  }
  const flowchart = target.closest('.node')
  if (flowchart && root.contains(flowchart)) {
    const card = cardForNode(flowchart, nodeCards)
    if (card) {
      return { card, node: flowchart }
    }
  }
  let el: Element | null = target
  while (el && el !== root) {
    const text = el.textContent?.trim() ?? ''
    for (const card of Object.values(nodeCards)) {
      if (text === card.title) {
        return { card, node: el }
      }
    }
    el = el.parentElement
  }
  return null
}

function findHardwareNodes(
  root: HTMLElement,
  nodeCards: Record<string, HardwareNodeCard>,
): Element[] {
  const byClass = [...root.querySelectorAll('g.node, .node')].filter((node) =>
    Boolean(cardForNode(node, nodeCards)),
  )
  if (byClass.length > 0) {
    return byClass
  }
  const found: Element[] = []
  for (const [key, card] of Object.entries(nodeCards)) {
    const byId = root.querySelector(`[id*="-${key}-"], [id$="-${key}"]`)
    if (byId) {
      const group = byId.closest('g') ?? byId
      if (!found.includes(group)) {
        found.push(group)
      }
      continue
    }
    const label = [...root.querySelectorAll('*')].find(
      (el) => el.textContent?.replace(/\s+/g, ' ').trim() === card.title,
    )
    const group = label?.closest('g') ?? label
    if (group && !found.includes(group)) {
      found.push(group)
    }
  }
  return found
}

type ShineBox = {
  key: string
  top: number
  left: number
  width: number
  height: number
  delay: number
}

function cardKeyForNode(
  node: Element,
  nodeCards: Record<string, HardwareNodeCard>,
): string | null {
  return cardForNode(node, nodeCards)?.title ?? null
}

function measureShineBoxes(
  root: HTMLElement,
  nodeCards: Record<string, HardwareNodeCard>,
): ShineBox[] {
  const wrap = root.getBoundingClientRect()
  return findHardwareNodes(root, nodeCards).flatMap((node, index) => {
    const key = cardKeyForNode(node, nodeCards)
    const rect = node.getBoundingClientRect()
    const width = rect.width || 24
    const height = rect.height || 24
    if (!key || width < 2 || height < 2) {
      return []
    }
    return [
      {
        key,
        top: rect.top - wrap.top - 6,
        left: rect.left - wrap.left - 6,
        width: width + 12,
        height: height + 12,
        delay: index * 90,
      },
    ]
  })
}

function hitFromEvent(
  event: MouseEvent,
  root: HTMLElement,
  nodeCards: Record<string, HardwareNodeCard>,
): { card: HardwareNodeCard; node: Element } | null {
  const direct = cardFromTarget(event.target, root, nodeCards)
  if (direct) {
    return direct
  }
  if (typeof document.elementsFromPoint !== 'function') {
    return null
  }
  for (const el of document.elementsFromPoint(event.clientX, event.clientY)) {
    const hit = cardFromTarget(el, root, nodeCards)
    if (hit) {
      return hit
    }
  }
  return null
}

function cardForNode(
  node: Element,
  nodeCards: Record<string, HardwareNodeCard>,
): HardwareNodeCard | null {
  const id = node.id
  const dataId = node.getAttribute('data-id') ?? ''
  const text = node.textContent ?? ''
  for (const [key, card] of Object.entries(nodeCards)) {
    if (
      id.includes(`-${key}-`) ||
      id.endsWith(`-${key}`) ||
      dataId === key ||
      text.includes(card.title)
    ) {
      return card
    }
  }
  return null
}

export default function MermaidDiagram({
  chart,
  plainLinks = false,
  nodeCards,
}: {
  chart: string
  plainLinks?: boolean
  nodeCards?: Record<string, HardwareNodeCard>
}) {
  const reactId = useId().replace(/[^a-zA-Z0-9]/g, '')
  const rootRef = useRef<HTMLDivElement>(null)
  const hideTimer = useRef<number | null>(null)
  const shineMeasured = useRef(false)
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const [inView, setInView] = useState(false)
  const [dismissedShine, setDismissedShine] = useState<Set<string>>(() => new Set())
  const [shineBoxes, setShineBoxes] = useState<ShineBox[]>([])
  const [hover, setHover] = useState<{
    card: HardwareNodeCard
    top: number
    left: number
    side: 'left' | 'right'
  } | null>(null)

  function cancelHide() {
    if (hideTimer.current !== null) {
      window.clearTimeout(hideTimer.current)
      hideTimer.current = null
    }
  }

  function scheduleHide() {
    cancelHide()
    hideTimer.current = window.setTimeout(() => {
      setHover(null)
      hideTimer.current = null
    }, 80)
  }

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
          setHover(null)
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

  useEffect(() => {
    const root = rootRef.current
    if (!root || !svg || !nodeCards) {
      return
    }

    if (typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        setInView(entries.some((entry) => entry.isIntersecting))
      },
      { threshold: 0 },
    )
    observer.observe(root)
    return () => observer.disconnect()
  }, [svg, nodeCards])

  useEffect(() => {
    const root = rootRef.current
    if (!root || !svg || !nodeCards || !inView || shineMeasured.current) {
      return
    }
    let cancelled = false
    let frame = 0
    const apply = () => {
      if (cancelled || shineMeasured.current) {
        return
      }
      const boxes = measureShineBoxes(root, nodeCards)
      if (boxes.length === 0) {
        frame = window.requestAnimationFrame(apply)
        return
      }
      shineMeasured.current = true
      setShineBoxes(boxes)
    }
    apply()
    frame = window.requestAnimationFrame(apply)
    return () => {
      cancelled = true
      window.cancelAnimationFrame(frame)
    }
  }, [inView, nodeCards, svg])

  useEffect(() => {
    const root = rootRef.current
    if (!root || !svg || !nodeCards) {
      return
    }
    const svgRoot = root
    const cards = nodeCards

    function dismissShine(title: string) {
      setDismissedShine((prev) => {
        if (prev.has(title)) {
          return prev
        }
        const next = new Set(prev)
        next.add(title)
        return next
      })
    }

    function onOver(event: MouseEvent) {
      const hit = hitFromEvent(event, svgRoot, cards)
      if (!hit) {
        scheduleHide()
        return
      }
      cancelHide()
      dismissShine(hit.card.title)
      setHover({
        card: hit.card,
        ...placePopup(hit.node.getBoundingClientRect()),
      })
    }

    function onOut(event: MouseEvent) {
      const next = event.relatedTarget
      if (next instanceof Element && cardFromTarget(next, svgRoot, cards)) {
        return
      }
      scheduleHide()
    }

    function onLeave() {
      cancelHide()
      setHover(null)
    }

    root.addEventListener('mouseover', onOver, true)
    root.addEventListener('mouseout', onOut, true)
    root.addEventListener('mouseleave', onLeave)
    return () => {
      cancelHide()
      root.removeEventListener('mouseover', onOver, true)
      root.removeEventListener('mouseout', onOut, true)
      root.removeEventListener('mouseleave', onLeave)
    }
  }, [svg, nodeCards])

  if (error) {
    return <p className="text-center text-red-400">{error}</p>
  }
  if (!svg) {
    return <p className="text-center text-zinc-500">Loading diagram…</p>
  }

  return (
    <>
      <div
        className={`relative overflow-visible [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full ${
          nodeCards ? 'hardware-diagram' : ''
        } ${nodeCards && inView ? 'is-in-view' : ''} ${
          plainLinks
            ? '[&_marker]:hidden [&_path]:[marker-end:none] [&_path]:[marker-start:none]'
            : ''
        }`}
        data-diagram-wrap=""
        ref={rootRef}
      >
        <div dangerouslySetInnerHTML={{ __html: svg }} />
        {shineBoxes
          .filter((box) => !dismissedShine.has(box.key))
          .map((box) => (
          <span
            className="hardware-shine-ring"
            data-shine-key={box.key}
            key={box.key}
            style={{
              animationDelay: `${box.delay}ms`,
              height: box.height,
              left: box.left,
              pointerEvents: 'none',
              top: box.top,
              width: box.width,
            }}
          />
        ))}
      </div>
      {hover
        ? createPortal(
            <div
              className="pointer-events-none fixed z-50 w-80 max-w-[calc(100vw-1rem)] rounded-lg border border-amber-400 bg-zinc-950 p-3 text-left text-sm leading-relaxed text-zinc-300 shadow-lg"
              data-hardware-card=""
              data-side={hover.side}
              style={{ left: hover.left, top: hover.top }}
            >
              <p className="font-medium text-zinc-50">{hover.card.title}</p>
              <p className="mt-1">{hover.card.body}</p>
              {hover.card.imageSrc ? (
                <img
                  alt={hover.card.imageAlt ?? hover.card.title}
                  className="mt-2 w-full rounded-md"
                  src={hover.card.imageSrc}
                />
              ) : null}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
