"use client";

import { sha256HexOfBlob, signMessage } from "@/lib/browser-crypto.client";
import { loadKeyPair } from "@/lib/keystore.client";
import { useEffect, useRef, useState } from "react";

type Stage = "load-device" | "ready" | "capturing" | "attesting" | "done";

export default function AuthenticatePage() {
  const [handle, setHandle] = useState("");
  const [keyPair, setKeyPair] = useState<CryptoKeyPair | null>(null);
  const [stage, setStage] = useState<Stage>("load-device");
  const [error, setError] = useState<string | null>(null);
  const [manifestId, setManifestId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function handleLoadDevice(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const kp = await loadKeyPair(handle);
    if (!kp) {
      setError(`No device enrolled as "${handle}" on this browser — enrol first.`);
      return;
    }
    setKeyPair(kp);
    setStage("ready");
  }

  async function handleStartCamera() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStage("capturing");
    } catch {
      setError("Could not access the camera — check browser permissions.");
    }
  }

  async function handleCaptureAndAttest() {
    if (!keyPair || !videoRef.current || !canvasRef.current) return;
    setError(null);
    setStage("attesting");
    try {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(video, 0, 0);

      const frameBlob: Blob = await new Promise((resolve, reject) =>
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("could not encode frame"))), "image/png"),
      );

      const wmForm = new FormData();
      wmForm.set("file", frameBlob, "frame.png");
      const wmRes = await fetch("/api/capture/watermark", { method: "POST", body: wmForm });
      if (!wmRes.ok) throw new Error("watermark embedding failed");
      const watermarkSecret = wmRes.headers.get("x-watermark-secret")!;
      const watermarkedBlob = await wmRes.blob();

      const mediaHash = await sha256HexOfBlob(watermarkedBlob);
      const capturedAt = new Date().toISOString();

      const challengeRes = await fetch("/api/capture/challenge", { method: "POST" });
      const { nonce, manifestId: reservedId } = await challengeRes.json();

      const message = `${mediaHash}|${capturedAt}|${handle}|${nonce}`;
      const signature = await signMessage(keyPair.privateKey, message);

      const attestRes = await fetch("/api/attest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          handle,
          manifestId: reservedId,
          challenge: nonce,
          mediaHash,
          capturedAt,
          signature,
          watermarkSecret,
          label: "Live webcam capture",
        }),
      });
      const attestData = await attestRes.json();
      if (!attestRes.ok) throw new Error(attestData.error ?? "attestation failed");

      streamRef.current?.getTracks().forEach((t) => t.stop());
      setPreviewUrl(URL.createObjectURL(watermarkedBlob));
      setManifestId(attestData.manifestId);
      setStage("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "capture failed");
      setStage("ready");
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">Capture Attestation</p>
        <h1 className="font-display text-3xl font-semibold text-text">Attest a live capture</h1>
        <p className="mt-2 text-muted">
          Captures a real frame from your camera, watermarks it, hashes it, and signs it with
          your enrolled device key — proving it came from a live camera at this moment.
        </p>
      </section>

      {stage === "load-device" && (
        <form onSubmit={handleLoadDevice} className="glass-card space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm text-muted">Your handle</label>
            <input
              required
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="yourhandle"
              className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button type="submit" className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white">
            Load device key
          </button>
        </form>
      )}

      {stage === "ready" && (
        <div className="glass-card space-y-4 p-6">
          <p className="text-sm text-ok">Device key loaded for @{handle}.</p>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button onClick={handleStartCamera} className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white">
            Start camera
          </button>
        </div>
      )}

      {(stage === "capturing" || stage === "attesting") && (
        <div className="glass-card space-y-4 p-6">
          <video ref={videoRef} className="w-full rounded-sm bg-black" muted playsInline />
          {error && <p className="text-sm text-danger">{error}</p>}
          <button
            onClick={handleCaptureAndAttest}
            disabled={stage === "attesting"}
            className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {stage === "attesting" ? "Attesting…" : "Capture frame & attest"}
          </button>
        </div>
      )}

      {stage === "done" && manifestId && (
        <div className="glass-card space-y-4 p-6">
          <p className="text-sm text-ok">Attested as {manifestId}.</p>
          {previewUrl && <img src={previewUrl} alt="Watermarked capture" className="rounded-sm" />}
          <p className="text-xs text-muted">
            Right-click the image above to save it, then check it on the Verify page.
          </p>
        </div>
      )}

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
