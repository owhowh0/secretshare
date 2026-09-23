'use client'

import { useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'

export default function ShortSecretRedirectPage() {
  const router = useRouter()
  const params = useParams()

  useEffect(() => {
    const id = params?.id
    if (id) {
      router.replace(`/?id=${encodeURIComponent(String(id))}`)
    } else {
      router.replace('/')
    }
  }, [params, router])

  return (
    <div style={{ maxWidth: '560px', margin: '4rem auto', textAlign: 'center', padding: '0 1rem' }}>
      <p className="muted">Loading secret…</p>
    </div>
  )
}
