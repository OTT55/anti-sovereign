const $ = (id) => document.getElementById(id);

$("algorithm").addEventListener("change", () => {
  $("scheme-label").textContent = $("algorithm").value === "schnorr"
    ? "Schnorr / 2048-bit" : "ECDSA P-256";
});

$("enrol").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const handle = $("handle").value.trim();
  const algorithm = $("algorithm").value;
  if (!handle) return showErr("Choose a device handle.");

  $("enrol").disabled = true;
  $("enrol").textContent = "Generating device key…";
  await new Promise(r => setTimeout(r, 20));

  let publicKey, storeRecord;
  if (algorithm === "schnorr") {
    // Hand-rolled BigInt math, not a Web Crypto key — no non-extractable form
    // exists for it (decisions/0008). Stored as-is in IndexedDB, which still
    // removes the copy/paste step even though it can't get the same
    // can-never-be-exported guarantee ECDSA gets below.
    const pair = generateDeviceKey();
    publicKey = pair.publicKey;
    storeRecord = { privateScalar: pair.privateKey };
  } else {
    const pair = await generateEcdsaDeviceKeyStored();
    publicKey = pair.publicKey;
    storeRecord = { cryptoKey: pair.cryptoKey };
  }

  let d;
  try {
    const res = await fetch("/enroll", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ handle, public_key: publicKey, algorithm }),
    });
    d = await res.json();
    $("enrol").disabled = false;
    $("enrol").textContent = "Generate device key & enrol";
    if (!res.ok) return showErr(d.error);

    await vdSaveDevice({
      handle, algorithm, publicKey,
      ...storeRecord,
      createdAt: new Date().toISOString(),
    });
    vdSetLastHandle(handle);
  } catch (e) {
    $("enrol").disabled = false;
    $("enrol").textContent = "Generate device key & enrol";
    return showErr("Enrolment didn't complete: " + e.message);
  }

  $("c_handle").textContent = d.handle;
  $("c_algorithm").textContent = algorithm;
  $("c_pub").textContent = publicKey;
  $("ecdsa-note").classList.toggle("hidden", algorithm !== "ecdsa-p256");
  $("schnorr-note").classList.toggle("hidden", algorithm !== "schnorr");
  if (algorithm === "schnorr") {
    $("c_secret").textContent = storeRecord.privateScalar;
    $("copy").onclick = () => navigator.clipboard.writeText(storeRecord.privateScalar);
  }
  $("result").classList.remove("hidden");
  $("result").scrollIntoView({ behavior: "smooth" });
});

// Bridge for a device enrolled before this browser had IndexedDB storage:
// paste the saved key once, it's imported into secure storage, and the
// Capture page never asks for it again (decisions/0008).
$("import_btn").addEventListener("click", async () => {
  $("import_err").classList.add("hidden");
  $("import_ok").classList.add("hidden");
  const handle = $("import_handle").value.trim();
  const algorithm = $("import_algorithm").value;
  const secret = $("import_secret").value.trim();
  if (!handle || !secret) return showImportErr("Device handle and private key are both required.");

  try {
    let storeRecord;
    if (algorithm === "schnorr") {
      storeRecord = { privateScalar: secret };
    } else {
      // Imported non-extractable: this browser's copy can never be exported
      // again from this point on, even though the pasted text obviously
      // already exists wherever it was saved before (decisions/0008).
      const cryptoKey = await importEcdsaPrivateKey(secret);
      storeRecord = { cryptoKey };
    }
    await vdSaveDevice({ handle, algorithm, publicKey: "", ...storeRecord, createdAt: new Date().toISOString() });
    vdSetLastHandle(handle);
    $("import_secret").value = "";
    $("import_ok").classList.remove("hidden");
  } catch {
    showImportErr("Could not parse that private key for the selected scheme.");
  }
});

function showErr(m) { $("err").textContent = m; $("err").classList.remove("hidden"); }
function showImportErr(m) { $("import_err").textContent = m; $("import_err").classList.remove("hidden"); }
