const links = [
  { href: '#overview', label: 'Overview' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#demo', label: 'Demo' },
  { href: '#try-it-out', label: 'Try it out' },
  { href: '#links', label: 'Links' },
] as const

export default function SiteNav() {
  return (
    <nav
      aria-label="On this page"
      className="sticky top-0 z-20 border-b border-amber-500/30 bg-zinc-950/95 backdrop-blur"
    >
      <ul className="mx-auto flex max-w-5xl flex-wrap gap-x-6 gap-y-2 px-6 py-4 text-base text-zinc-300">
        {links.map((link) => (
          <li key={link.href}>
            <a className="hover:text-amber-400" href={link.href}>
              {link.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
