/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Публичният базов адрес на API (SSR го чете за server-side извличане).
  env: {
    OHDP_API_BASE: process.env.OHDP_API_BASE ?? "http://127.0.0.1:8000",
  },
};

export default nextConfig;
