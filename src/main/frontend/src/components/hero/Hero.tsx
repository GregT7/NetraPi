export default function Hero() {
  return (
    <header className="flex flex-col items-center gap-4 px-6 pb-2 pt-8">
      <h1 className="text-center text-5xl font-semibold tracking-tight text-zinc-50 md:text-7xl">
        Netra<span className="text-amber-400">Pi</span>
      </h1>
      <img
        alt="NetraPi watching the road and labeling a stop"
        className="w-full max-w-3xl rounded-xl border border-zinc-800 bg-zinc-900"
        src="/gifs/overview.gif?v=1"
      />
    </header>
  )
}
