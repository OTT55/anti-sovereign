import { notFound } from "next/navigation";
import { getPublicProfile } from "@/lib/profile";

export default async function PublicProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const profile = await getPublicProfile(handle);
  if (!profile) notFound();

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">
          {profile.profile?.availability ?? "open"}
          {profile.verified ? " · verified" : ""}
        </p>
        <h1 className="font-display text-3xl font-semibold text-text">{profile.displayName}</h1>
        <p className="font-mono text-sm text-muted">@{profile.handle}</p>
        {profile.profile?.headline && <p className="mt-2 text-text">{profile.profile.headline}</p>}
        {profile.profile?.bio && <p className="mt-2 text-muted">{profile.profile.bio}</p>}
        <p className="mt-4 font-mono text-xs text-muted">
          Reputation {profile.reputation}
          {profile.averageRating !== null && ` · ${profile.averageRating.toFixed(1)}★ (${profile.reviews.length} reviews)`}
        </p>
      </section>

      {profile.skills.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {profile.skills.map((s) => (
            <span key={s.id} className="rounded-pill bg-accent-subtle px-3 py-1 text-xs text-accent">
              {s.skill}
            </span>
          ))}
        </div>
      )}

      <section className="space-y-2">
        <h2 className="font-display text-lg font-semibold text-text">Portfolio</h2>
        {profile.provenance.map((p) => (
          <div key={p.registryId} className="glass-card p-4 text-sm">
            <p className="font-mono text-text">{p.registryId}</p>
            <p className="text-xs text-muted">{p.title ?? p.filename}</p>
          </div>
        ))}
        {profile.provenance.length === 0 && <p className="text-sm text-muted">Nothing registered yet.</p>}
      </section>

      {profile.reviews.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-display text-lg font-semibold text-text">Reviews</h2>
          {profile.reviews.map((r) => (
            <div key={r.id} className="glass-card p-4 text-sm">
              <p className="text-text">
                {"★".repeat(r.rating)}
                {"☆".repeat(5 - r.rating)}
              </p>
              {r.body && <p className="mt-1 text-muted">{r.body}</p>}
              <p className="mt-1 font-mono text-xs text-muted">— {r.authorName}</p>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
