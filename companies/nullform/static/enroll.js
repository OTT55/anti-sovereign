const $ = (id) => document.getElementById(id);

$("generate").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const handle = $("handle").value.trim();
  if (!handle) return showErr("Choose a handle.");

  $("generate").disabled = true;
  $("generate").textContent = "Generating keypair…";
  // Yield so the button text paints before the (fast) big-int math runs.
  await new Promise(r => setTimeout(r, 20));
  const { x, y } = generateKeypair();

  const res = await fetch("/enroll", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle, public_key: y }),
  });
  const d = await res.json();
  $("generate").disabled = false;
  $("generate").textContent = "Generate keypair & enrol";
  if (!res.ok) return showErr(d.error);

  $("c_id").textContent = d.identity_id;
  $("c_handle").textContent = d.handle;
  $("c_time").textContent = d.created_at;
  $("c_secret").textContent = x;
  $("c_pub").textContent = y;
  $("copy").onclick = () => navigator.clipboard.writeText(x);
  $("result").classList.remove("hidden");
  $("result").scrollIntoView({ behavior: "smooth" });
});

function showErr(m) { $("err").textContent = m; $("err").classList.remove("hidden"); }
