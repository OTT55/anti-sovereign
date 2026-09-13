"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

interface Profile {
  headline: string | null;
  bio: string | null;
  location: string | null;
  availability: "open" | "selective" | "booked";
}

interface Skill {
  id: number;
  skill: string;
  level: string;
}

export function SettingsForm({ profile, skills }: { profile: Profile | null; skills: Skill[] }) {
  const router = useRouter();
  const [headline, setHeadline] = useState(profile?.headline ?? "");
  const [bio, setBio] = useState(profile?.bio ?? "");
  const [location, setLocation] = useState(profile?.location ?? "");
  const [availability, setAvailability] = useState(profile?.availability ?? "open");
  const [newSkill, setNewSkill] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ headline, bio, location, availability }),
      });
      if (!res.ok) throw new Error((await res.json()).error ?? "save failed");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "save failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddSkill(e: React.FormEvent) {
    e.preventDefault();
    if (!newSkill.trim()) return;
    await fetch("/api/skills", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ skill: newSkill.trim(), level: "intermediate" }),
    });
    setNewSkill("");
    router.refresh();
  }

  async function handleRemoveSkill(id: number) {
    await fetch(`/api/skills/${id}`, { method: "DELETE" });
    router.refresh();
  }

  return (
    <div className="space-y-8">
      <form onSubmit={handleSaveProfile} className="glass-card space-y-4 p-6">
        <div>
          <label className="mb-1 block text-sm text-muted">Headline</label>
          <input
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-muted">Bio</label>
          <textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            rows={4}
            className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location"
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
          <select
            value={availability}
            onChange={(e) => setAvailability(e.target.value as typeof availability)}
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          >
            <option value="open">Open</option>
            <option value="selective">Selective</option>
            <option value="booked">Booked</option>
          </select>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save profile"}
        </button>
      </form>

      <div className="glass-card space-y-4 p-6">
        <h2 className="font-display text-lg font-semibold text-text">Skills</h2>
        <div className="flex flex-wrap gap-2">
          {skills.map((s) => (
            <span key={s.id} className="flex items-center gap-2 rounded-pill bg-accent-subtle px-3 py-1 text-xs text-accent">
              {s.skill}
              <button onClick={() => handleRemoveSkill(s.id)} className="text-accent/70 hover:text-accent">
                ×
              </button>
            </span>
          ))}
        </div>
        <form onSubmit={handleAddSkill} className="flex gap-2">
          <input
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
            placeholder="Add a skill…"
            className="flex-1 rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
          <button type="submit" className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white">
            Add
          </button>
        </form>
      </div>
    </div>
  );
}
