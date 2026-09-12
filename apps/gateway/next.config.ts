import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Anchor the workspace root explicitly — there's an unrelated package.json
  // in the user's home directory that would otherwise confuse Next's
  // auto-detected monorepo root.
  outputFileTracingRoot: path.join(__dirname, "../.."),
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
