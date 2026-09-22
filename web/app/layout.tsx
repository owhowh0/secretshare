import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-sans' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], display: 'swap', variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'SecretShare',
}

// The CSP in middleware.ts carries a per-request nonce, and Next can only stamp
// it onto its inline scripts while rendering. A prerendered page would be served
// from the build-time cache with a stale nonce that no longer matches the header,
// so every script on it would be blocked. Nothing here is cacheable anyway: the
// page is an authenticated client-side app that calls the API on each action.
export const dynamic = 'force-dynamic'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
