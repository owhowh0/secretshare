/**
 * Pure-JS SHA-256 fallback for non-secure HTTP contexts where
 * window.crypto.subtle is unavailable (e.g. plain-HTTP staging previews).
 */
export function sha256Sync(ascii: string): Uint8Array {
  function rightRotate(value: number, amount: number) {
    return (value >>> amount) | (value << (32 - amount))
  }

  const mathPow = Math.pow
  const maxWord = mathPow(2, 32)
  let i, j

  const words: number[] = []
  const asciiBitLength = ascii.length * 8

  const hash: number[] = []
  const k: number[] = []
  let primeCounter = 0

  const isComposite: Record<number, number> = {}
  for (let candidate = 2; primeCounter < 64; candidate++) {
    if (!isComposite[candidate]) {
      for (i = 0; i < 313; i += candidate) {
        isComposite[i] = candidate
      }
      hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0
      k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0
    }
  }

  let str = ascii + '\x80'
  while ((str.length % 64) - 56) str += '\x00'
  for (i = 0; i < str.length; i++) {
    j = str.charCodeAt(i)
    words[i >> 2] |= j << ((3 - i) % 4) * 8
  }
  words[words.length] = (asciiBitLength / maxWord) | 0
  words[words.length] = asciiBitLength

  let currentHash = [...hash]
  for (j = 0; j < words.length; ) {
    const w = words.slice(j, (j += 16))
    const oldHash = [...currentHash]
    currentHash = currentHash.slice(0, 8)

    for (i = 0; i < 64; i++) {
      const w15 = w[i - 15], w2 = w[i - 2]
      const s0 = rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3)
      const s1 = rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10)
      w[i] = (i < 16) ? (w[i] || 0) : (w[i - 16] + s0 + w[i - 7] + s1) | 0

      const s1h = rightRotate(currentHash[4], 6) ^ rightRotate(currentHash[4], 11) ^ rightRotate(currentHash[4], 25)
      const ch = (currentHash[4] & currentHash[5]) ^ (~currentHash[4] & currentHash[6])
      const temp1 = currentHash[7] + s1h + ch + k[i] + w[i]
      const s0h = rightRotate(currentHash[0], 2) ^ rightRotate(currentHash[0], 13) ^ rightRotate(currentHash[0], 22)
      const maj = (currentHash[0] & currentHash[1]) ^ (currentHash[0] & currentHash[2]) ^ (currentHash[1] & currentHash[2])
      const temp2 = s0h + maj

      currentHash = [(temp1 + temp2) | 0, ...currentHash]
      currentHash[4] = (currentHash[4] + temp1) | 0
    }

    for (i = 0; i < 8; i++) {
      currentHash[i] = (currentHash[i] + oldHash[i]) | 0
    }
  }

  const rawBytes: number[] = []
  for (i = 0; i < 8; i++) {
    for (let b = 3; b >= 0; b--) {
      rawBytes.push((currentHash[i] >> (b * 8)) & 255)
    }
  }
  return new Uint8Array(rawBytes)
}

export function randomString(length = 64): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
  const bytes = new Uint8Array(length)
  if (typeof window !== 'undefined' && window.crypto?.getRandomValues) {
    window.crypto.getRandomValues(bytes)
  } else {
    for (let i = 0; i < length; i++) bytes[i] = Math.floor(Math.random() * 256)
  }
  return Array.from(bytes).map(b => chars[b % chars.length]).join('')
}

export async function sha256Challenge(verifier: string): Promise<string> {
  let hashBytes: Uint8Array

  if (typeof window !== 'undefined' && window.crypto?.subtle?.digest) {
    try {
      const data = new TextEncoder().encode(verifier)
      const hash = await window.crypto.subtle.digest('SHA-256', data)
      hashBytes = new Uint8Array(hash)
    } catch {
      hashBytes = sha256Sync(verifier)
    }
  } else {
    hashBytes = sha256Sync(verifier)
  }

  let binary = ''
  for (let i = 0; i < hashBytes.byteLength; i++) {
    binary += String.fromCharCode(hashBytes[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
