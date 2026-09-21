// Helper functions for Base64 and ArrayBuffer conversion
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

export function base64ToArrayBuffer(base64: string): ArrayBuffer {
  let normalized = base64.replace(/-/g, '+').replace(/_/g, '/')
  while (normalized.length % 4 !== 0) {
    normalized += '='
  }
  const binary = atob(normalized)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}


/**
 * Generate an RSA-OAEP 2048-bit key pair using SHA-256
 */
export async function generateRsaKeyPair(): Promise<CryptoKeyPair> {
  return await window.crypto.subtle.generateKey(
    {
      name: 'RSA-OAEP',
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]), // 65537
      hash: 'SHA-256',
    },
    true, // extractable
    ['encrypt', 'decrypt']
  )
}

/**
 * Export RSA public key to SPKI PEM format matching backend regex
 */
export async function exportPublicKeyToSpkiPem(publicKey: CryptoKey): Promise<string> {
  const spkiBuffer = await window.crypto.subtle.exportKey('spki', publicKey)
  const base64 = arrayBufferToBase64(spkiBuffer)
  const lines = base64.match(/.{1,64}/g) || []
  return `-----BEGIN PUBLIC KEY-----\n${lines.join('\n')}\n-----END PUBLIC KEY-----`
}

/**
 * Import SPKI PEM formatted RSA public key
 */
export async function importPublicKeyFromSpkiPem(pem: string): Promise<CryptoKey> {
  const cleanBase64 = pem
    .replace(/-----BEGIN PUBLIC KEY-----/, '')
    .replace(/-----END PUBLIC KEY-----/, '')
    .replace(/\s+/g, '')
  const buffer = base64ToArrayBuffer(cleanBase64)

  return await window.crypto.subtle.importKey(
    'spki',
    buffer,
    {
      name: 'RSA-OAEP',
      hash: 'SHA-256',
    },
    true,
    ['encrypt']
  )
}

/**
 * Encrypt plaintext using AES-256-GCM with a random 12-byte IV
 */
export async function encryptAesGcm(plaintext: string): Promise<{
  ciphertext: string
  iv: string
  rawAesKey: ArrayBuffer
}> {
  const rawAesKey = window.crypto.getRandomValues(new Uint8Array(32)) // 256-bit key
  const iv = window.crypto.getRandomValues(new Uint8Array(12)) // 96-bit IV

  const aesCryptoKey = await window.crypto.subtle.importKey(
    'raw',
    rawAesKey,
    { name: 'AES-GCM' },
    false,
    ['encrypt']
  )

  const encodedPlaintext = new TextEncoder().encode(plaintext)
  const cipherBuffer = await window.crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv,
    },
    aesCryptoKey,
    encodedPlaintext
  )

  return {
    ciphertext: arrayBufferToBase64(cipherBuffer),
    iv: arrayBufferToBase64(iv.buffer),
    rawAesKey: rawAesKey.buffer,
  }
}

/**
 * Encrypt raw AES key bytes with RSA-OAEP recipient public key
 */
export async function encryptAesKeyWithRsa(
  rawAesKey: ArrayBuffer,
  rsaPublicKey: CryptoKey
): Promise<string> {
  const encryptedKeyBuffer = await window.crypto.subtle.encrypt(
    { name: 'RSA-OAEP' },
    rsaPublicKey,
    rawAesKey
  )
  return arrayBufferToBase64(encryptedKeyBuffer)
}

/**
 * Decrypt RSA-OAEP encrypted AES key with local device private key
 */
export async function decryptAesKeyWithRsa(
  encryptedAesKeyBase64: string,
  rsaPrivateKey: CryptoKey
): Promise<ArrayBuffer> {
  const buffer = base64ToArrayBuffer(encryptedAesKeyBase64)
  return await window.crypto.subtle.decrypt(
    { name: 'RSA-OAEP' },
    rsaPrivateKey,
    buffer
  )
}

/**
 * Decrypt AES-256-GCM ciphertext using unwrapped raw AES key and IV
 */
export async function decryptAesGcm(
  ciphertextBase64: string,
  ivBase64: string,
  rawAesKey: ArrayBuffer
): Promise<string> {
  const cipherBuffer = base64ToArrayBuffer(ciphertextBase64)
  const ivBuffer = base64ToArrayBuffer(ivBase64)

  const aesCryptoKey = await window.crypto.subtle.importKey(
    'raw',
    rawAesKey,
    { name: 'AES-GCM' },
    false,
    ['decrypt']
  )

  const decryptedBuffer = await window.crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: new Uint8Array(ivBuffer),
    },
    aesCryptoKey,
    cipherBuffer
  )

  return new TextDecoder().decode(decryptedBuffer)
}
