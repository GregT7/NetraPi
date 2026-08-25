import { Github, Linkedin } from 'lucide-react'

const GITHUB_URL = 'https://github.com/GregT7/NetraPi'
const LINKEDIN_URL = 'https://www.linkedin.com/in/gregterrell7/'

export default function Links() {
  return (
    <section className="scroll-mt-20 px-6 pb-16 pt-6" id="links">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Links
        </h2>
        <ul className="mt-6 space-y-3">
          <li>
            <a
              className="inline-flex items-center gap-2 text-amber-400 underline-offset-2 hover:text-amber-300 hover:underline"
              href={GITHUB_URL}
              rel="noreferrer"
              target="_blank"
            >
              <Github aria-hidden="true" className="h-5 w-5" />
              GitHub
            </a>
          </li>
          <li>
            <a
              className="inline-flex items-center gap-2 text-amber-400 underline-offset-2 hover:text-amber-300 hover:underline"
              href={LINKEDIN_URL}
              rel="noreferrer"
              target="_blank"
            >
              <Linkedin aria-hidden="true" className="h-5 w-5" />
              LinkedIn
            </a>
          </li>
        </ul>
      </div>
    </section>
  )
}
