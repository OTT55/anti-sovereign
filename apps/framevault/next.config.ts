import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname, "../.."),
  // Gives creators a vanity profile URL without a literal "@" folder, which
  // Next.js reserves for parallel-route slots.
  async rewrites() {
    return [{ source: "/@:handle", destination: "/profile/:handle" }];
  },
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
