const POPUP_GAP = 8
const POPUP_WIDTH = 320

export function popupSide(
  nodeRight: number,
  viewportWidth: number,
  popupWidth = POPUP_WIDTH,
  gap = POPUP_GAP,
): 'left' | 'right' {
  return nodeRight + gap + popupWidth > viewportWidth ? 'left' : 'right'
}

export function placePopup(nodeRect: DOMRect): {
  top: number
  left: number
  side: 'left' | 'right'
} {
  const side = popupSide(nodeRect.right, window.innerWidth)
  let left =
    side === 'right'
      ? nodeRect.right + POPUP_GAP
      : nodeRect.left - POPUP_GAP - POPUP_WIDTH
  left = Math.max(POPUP_GAP, Math.min(left, window.innerWidth - POPUP_WIDTH - POPUP_GAP))
  const top = Math.max(
    POPUP_GAP,
    Math.min(nodeRect.top, window.innerHeight - POPUP_GAP),
  )
  return { top, left, side }
}
