const $ = (id) => document.getElementById(id);

$("prove").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  $("result").classList.add("hidden");
  const handle = $("handle").value.trim();
  const secret = $("secret").value.trim();
  const message = $("message").value.trim();
  if (!handle || !secret || !message) return showErr("Handle, private key, and message are all required.");

  let proof;
  try {
    proof = await proveKnowledge(secret, message);
  } catch (e) {
    return showErr("Could not parse that private key.");
  }

  const res = await fetch("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle, message, t: proof.t, s: proof.s }),
  });
  const d = await res.json();
  if (!res.ok) return showErr(d.error);

  const box = $("result");
  box.classList.remove("result-ok", "result-bad");
  if (d.valid) {
    box.classList.add("result-ok");
    $("verdict").innerHTML = '<span class="badge-ok">✓ IDENTITY PROVEN</span>';
    $("detail").textContent = "The server confirmed you hold the private key for this identity — without ever seeing it.";
  } else {
    box.classList.add("result-bad");
    $("verdict").innerHTML = '<span class="badge-bad">✗ PROOF REJECTED</span>';
    $("detail").textContent = "The proof did not verify against the enrolled public key. Wrong private key, or altered message.";
  }
  $("c_id").textContent = (d.identity_id || "—") + "  ·  @" + d.handle;
  $("c_msg").textContent = d.message;
  $("c_t").textContent = proof.t;
  $("c_s").textContent = proof.s;
  box.classList.remove("hidden");
  box.scrollIntoView({ behavior: "smooth" });
});

function showErr(m) { $("err").textContent = m; $("err").classList.remove("hidden"); }
