const DB_NAME = "veridact-keys";
const STORE_NAME = "device-keys";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE_NAME);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** IndexedDB supports structured-cloning a CryptoKeyPair directly — the non-extractable private key survives the round-trip without ever being exportable. */
export async function saveKeyPair(handle: string, keyPair: CryptoKeyPair): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(keyPair, handle);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function loadKeyPair(handle: string): Promise<CryptoKeyPair | null> {
  const db = await openDb();
  const result = await new Promise<CryptoKeyPair | null>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).get(handle);
    req.onsuccess = () => resolve((req.result as CryptoKeyPair | undefined) ?? null);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return result;
}
