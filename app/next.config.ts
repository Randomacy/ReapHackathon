import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  allowedDevOrigins: ["tough-rubber-interval-councils.trycloudflare.com"],
};

export default nextConfig;
