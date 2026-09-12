import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Anchor the workspace root explicitly — there's an unrelated package.json
  // in the user's home directory that would otherwise confuse Next's
  // auto-detected monorepo root.
  outputFileTracingRoot: path.join(__dirname, "../.."),
  // This working tree is synced by OneDrive, which historically caused the
  // Flask dev reloader to peg 75-90% CPU per app (see repo CLAUDE.md). Webpack
  // uses native OS file-watching by default (not polling), which is normally
  // fine here, but we still exclude heavy/irrelevant paths so OneDrive's own
  // sync churn on them can't trigger rebuild storms. If `next dev` is
  // observed pegging CPU on this path (checked during verification), switch
  // to `poll` here rather than assuming native watching is the problem.
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ...config.watchOptions,
        ignored: ["**/node_modules/**", "**/.git/**", "**/*.sqlite", "**/.next/**"],
      };
    }
    return config;
  },
};

export default nextConfig;
