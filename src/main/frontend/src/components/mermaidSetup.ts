import mermaid from 'mermaid'
import { logosPack, mdiPack } from './diagramIconPacks'

let ready = false

export function ensureMermaid() {
  if (ready) {
    return
  }

  mermaid.registerIconPacks([
    { icons: logosPack, name: logosPack.prefix },
    { icons: mdiPack, name: mdiPack.prefix },
  ])
  mermaid.initialize({
    securityLevel: 'loose',
    startOnLoad: false,
    theme: 'dark',
    themeVariables: {
      background: '#09090b',
      clusterBkg: '#27272a',
      clusterBorder: '#52525b',
      darkMode: true,
      edgeLabelBackground: '#18181b',
      fontFamily: 'ui-sans-serif, system-ui, sans-serif',
      fontSize: '16px',
      lineColor: '#a1a1aa',
      mainBkg: '#18181b',
      nodeBorder: '#f59e0b',
      primaryBorderColor: '#f59e0b',
      primaryColor: '#27272a',
      primaryTextColor: '#fafafa',
      secondaryColor: '#18181b',
      tertiaryColor: '#3f3f46',
      textColor: '#fafafa',
      titleColor: '#fbbf24',
    },
  })
  ready = true
}
