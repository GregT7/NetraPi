import Demo from './components/demo/Demo'
import Hero from './components/hero/Hero'
import HowItWorks from './components/how-it-works/HowItWorks'
import Links from './components/links/Links'
import Overview from './components/overview/Overview'
import SiteNav from './components/layout/SiteNav'
import TryItOut from './components/try-it-out/TryItOut'

export default function App() {
  return (
    <div className="min-h-svh bg-zinc-950 text-base text-zinc-100 [background-image:radial-gradient(ellipse_at_top,rgba(245,158,11,0.08),transparent_55%)]">
      <SiteNav />
      <Hero />
      <Overview />
      <HowItWorks />
      <Demo />
      <TryItOut />
      <Links />
    </div>
  )
}
