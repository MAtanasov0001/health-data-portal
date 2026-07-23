/** @type {import('next').NextConfig} */

// Продукцията върви като SSR (SEO, чл. 41). За жива демо/staging среда (OpenKBS: статичен
// S3+CloudFront) се произвежда статичен експорт с `STATIC_EXPORT=1` — само за визуален
// преглед на дизайна; данните са замразени към момента на билда.
const STATIC_EXPORT = process.env.STATIC_EXPORT === "1";

const nextConfig = {
  reactStrictMode: true,
  // Публичният базов адрес на API (SSR го чете за server-side извличане).
  env: {
    OHDP_API_BASE: process.env.OHDP_API_BASE ?? "http://127.0.0.1:8000",
    OHDP_CKAN_URL: process.env.OHDP_CKAN_URL ?? "http://127.0.0.1:5000",
  },
  ...(STATIC_EXPORT
    ? { output: "export", trailingSlash: true, images: { unoptimized: true } }
    : {}),
};

export default nextConfig;
