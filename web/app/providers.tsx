'use client'

import { SessionProvider } from 'next-auth/react'

export function Providers({ children }: { children: React.ReactNode }) {
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH
    ? `${process.env.NEXT_PUBLIC_BASE_PATH}/api/auth`
    : '/api/auth'

  return <SessionProvider basePath={basePath}>{children}</SessionProvider>
}
