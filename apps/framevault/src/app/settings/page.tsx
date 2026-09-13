import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";
import { db } from "@/db";
import { creatorProfiles, profileSkills } from "@/db/schema";
import { getSessionUserId } from "@/lib/session";
import { SettingsForm } from "./settings-form";

export default async function SettingsPage() {
  const userId = await getSessionUserId();
  if (!userId) redirect("/login");

  const [profile, skills] = await Promise.all([
    db.select().from(creatorProfiles).where(eq(creatorProfiles.userId, userId)).get(),
    db.select().from(profileSkills).where(eq(profileSkills.userId, userId)),
  ]);

  return (
    <div className="space-y-8">
      <h1 className="font-display text-2xl font-semibold text-text">Settings</h1>
      <SettingsForm profile={profile ?? null} skills={skills} />
    </div>
  );
}
