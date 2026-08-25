import Demo from './components/Demo'
import Hero from './components/Hero'
import HowItWorks from './components/HowItWorks'
import Links from './components/Links'
import Overview from './components/Overview'
import SiteNav from './components/SiteNav'
import TryItOut from './components/TryItOut'

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
