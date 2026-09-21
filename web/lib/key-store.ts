import {
  exportPublicKeyToSpkiPem,
  generateRsaKeyPair,
} from './crypto'

const DB_NAME = 'secretshare_keystore'
const DB_VERSION = 1
const STORE_NAME = 'device_keys'

export interface StoredDeviceKeyRecord {
  id: string // username: e.g. "calin", "ilie"
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

export async function getStoredDeviceKey(username: string): Promise<StoredDeviceKeyRecord | null> {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const request = store.get(username)

    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(request.error)
  })
}

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

export async function getOrGenerateDeviceKey(
  username: string,
  label: string = 'Web Browser'
): Promise<StoredDeviceKeyRecord> {
  const existing = await getStoredDeviceKey(username)
  if (existing) {
    return existing
  }

  const keyPair = await generateRsaKeyPair()
  const spkiPem = await exportPublicKeyToSpkiPem(keyPair.publicKey)

  const record: StoredDeviceKeyRecord = {
    id: username,
    publicKey: keyPair.publicKey,
    privateKey: keyPair.privateKey,
    spkiPem,
    label,
    createdAt: new Date().toISOString(),
  }

  await saveDeviceKey(record)
  return record
}

export async function updateStoredDeviceId(username: string, deviceId: string): Promise<void> {
  const existing = await getStoredDeviceKey(username)
  if (existing) {
    existing.deviceId = deviceId
    await saveDeviceKey(existing)
  }
}
