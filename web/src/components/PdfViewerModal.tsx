import { useEffect } from 'react'

/** Shows a PDF (via its object URL, see api.ts's getPdfObjectUrl) in an
 * in-page overlay, not a new browser tab - modern Chromium refuses to
 * top-level-navigate a new tab/window to a blob: URL created by a
 * different browsing context (see getPdfObjectUrl's comment for how that
 * was confirmed), but a blob: URL works fine as an <iframe src> within the
 * same document that created it. Renders nothing when `url` is null, so a
 * caller can always mount this once and just toggle `url`. */
export function PdfViewerModal({
  url,
  title,
  onClose,
}: {
  url: string | null
  title: string
  onClose: () => void
}) {
  useEffect(() => {
    if (!url) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [url, onClose])

  if (!url) return null

  return (
    <div className="pdf-modal-backdrop" onClick={onClose}>
      <div
        className="pdf-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="pdf-modal-header">
          <span>{title}</span>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <iframe src={url} title={title} className="pdf-modal-frame" />
      </div>
    </div>
  )
}
