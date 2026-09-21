import {
  exportPublicKeyToSpkiPem,
  generateRsaKeyPair,
} from './crypto'

const DB_NAME = 'secretshare_keystore'
const DB_VERSION = 1
const STORE_NAME = 'device_keys'
const KEY_RECORD_ID = 'local_device_key'

export interface StoredDeviceKeyRecord {
  id: string
  deviceId?: string
  publicKey: CryptoKey
  privateKey: CryptoKey
  spkiPem: string
  label?: string
  createdAt: string
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' })
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

/**
 * Retrieve local device key record from IndexedDB if present
 */
export async function getStoredDeviceKey(): Promise<StoredDeviceKeyRecord | null> {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const request = store.get(KEY_RECORD_ID)

    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(request.error)
  })
}

/**
 * Save device key record to IndexedDB
 */
export async function saveDeviceKey(record: StoredDeviceKeyRecord): Promise<void> {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.put(record)

    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

/**
 * Get or generate local RSA-OAEP device key pair
 */
export async function getOrGenerateDeviceKey(
  label: string = 'Web Browser'
): Promise<StoredDeviceKeyRecord> {
  const existing = await getStoredDeviceKey()
  if (existing) {
    return existing
  }

  const keyPair = await generateRsaKeyPair()
  const spkiPem = await exportPublicKeyToSpkiPem(keyPair.publicKey)

  const record: StoredDeviceKeyRecord = {
    id: KEY_RECORD_ID,
    publicKey: keyPair.publicKey,
    privateKey: keyPair.privateKey,
    spkiPem,
    label,
    createdAt: new Date().toISOString(),
  }

  await saveDeviceKey(record)
  return record
}

/**
 * Link registered backend deviceId to local store
 */
export async function updateStoredDeviceId(deviceId: string): Promise<void> {
  const existing = await getStoredDeviceKey()
  if (existing) {
    existing.deviceId = deviceId
    await saveDeviceKey(existing)
  }
}
