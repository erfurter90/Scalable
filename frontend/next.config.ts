import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal, self-contained server bundle for the Docker image (see frontend/Dockerfile).
  output: "standalone",
  // Allows the dev server (HMR websocket, static chunks) to be reached from other devices on the
  // LAN, e.g. a phone at http://192.168.178.34:3000 — Next.js 16 blocks cross-origin dev requests
  // by default for safety.
  allowedDevOrigins: ["192.168.178.34"],
};

export default nextConfig;
