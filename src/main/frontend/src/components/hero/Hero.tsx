export default function Hero() {
  return (
    <header className="flex flex-col items-center gap-4 px-6 pb-2 pt-8">
      <h1 className="text-center text-5xl font-semibold tracking-tight text-zinc-50 md:text-7xl">
        Netra<span className="text-amber-400">Pi</span>
      </h1>
      <div className="flex aspect-video w-full max-w-3xl items-center justify-center rounded-xl border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
        GIF coming soon
      </div>
    </header>
  )
}
