'use client'

import { useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'

export default function SecretRedirectPage() {
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
    <div style={{ maxWidth: '640px', margin: '3rem auto', textAlign: 'center', fontFamily: 'sans-serif' }}>
      <p style={{ color: '#4a5568' }}>Loading secret…</p>
    </div>
  )
}
