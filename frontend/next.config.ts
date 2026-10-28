import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep optional verification/preview builds separate from a user's running dev build.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
};

export default nextConfig;
