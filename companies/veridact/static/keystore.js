// Veridact device keystore — IndexedDB, not localStorage/paste-a-textbox.
//
// Why IndexedDB and not localStorage: only IndexedDB's structured-clone
// algorithm can store a Web Crypto CryptoKey object directly, including a
// NON-EXTRACTABLE one (decisions/0008). localStorage can only hold strings,
// so anything put there has to already be exportable text — which is exactly
// the property we're removing for ECDSA keys. Storing the CryptoKey object
// itself means the raw key bytes never exist as a JS string at all, not even
// transiently.
//
// This module only stores/retrieves key material. It does not change what
// gets signed or how signatures are verified (crypto.py / crypto_ecdsa.py /
// device.js / ecdsa.js are untouched).

const VD_DB_NAME = "veridact-keystore";
const VD_DB_VERSION = 1;
const VD_STORE = "devices";

function vdOpenDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(VD_DB_NAME, VD_DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(VD_STORE)) {
        db.createObjectStore(VD_STORE, { keyPath: "handle" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function vdTx(mode, fn) {
  const db = await vdOpenDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VD_STORE, mode);
    const store = tx.objectStore(VD_STORE);
    const result = fn(store);
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
  });
}

// record shape: { handle, algorithm, publicKey, cryptoKey?, privateScalar?, createdAt }
// - ecdsa-p256 devices carry `cryptoKey` (a CryptoKey, generated non-extractable —
//   see ecdsa.js's generateEcdsaDeviceKey). It can be used to sign but never
//   exported back out, by this page or any other script (decisions/0008).
// - schnorr devices carry `privateScalar` (a decimal string) — Schnorr is
//   hand-rolled BigInt math, not a Web Crypto key object, so there is no
//   non-extractable form available for it; this is stated plainly in
//   decisions/0008 rather than implying a protection that isn't there.
function vdSaveDevice(record) {
  return vdTx("readwrite", (store) => store.put(record));
}

function vdGetDevice(handle) {
  return new Promise(async (resolve, reject) => {
    const db = await vdOpenDb();
    const tx = db.transaction(VD_STORE, "readonly");
    const req = tx.objectStore(VD_STORE).get(handle);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

function vdListDevices() {
  return new Promise(async (resolve, reject) => {
    const db = await vdOpenDb();
    const tx = db.transaction(VD_STORE, "readonly");
    const req = tx.objectStore(VD_STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

// Which handle to pre-select next time. This is just a name — not key
// material — so plain localStorage is fine for it.
function vdSetLastHandle(handle) {
  try { localStorage.setItem("veridact_last_handle", handle); } catch { /* ignore */ }
}
function vdGetLastHandle() {
  try { return localStorage.getItem("veridact_last_handle"); } catch { return null; }
}
