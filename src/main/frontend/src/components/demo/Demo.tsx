const YOUTUBE_VIDEO_ID = 'VPODr7JDU3w'

export default function Demo() {
  const embedUrl = YOUTUBE_VIDEO_ID
    ? `https://www.youtube-nocookie.com/embed/${YOUTUBE_VIDEO_ID}`
    : ''

  return (
    <section className="scroll-mt-20 px-6 py-16" id="demo">
      <div className="mx-auto max-w-3xl space-y-10">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Demo
        </h2>

        {embedUrl ? (
          <iframe
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="aspect-video w-full rounded-lg border border-zinc-800"
            src={embedUrl}
            title="NetraPi demo"
          />
        ) : (
          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
            Demo clip coming soon
          </div>
        )}
      </div>
    </section>
  )
}
