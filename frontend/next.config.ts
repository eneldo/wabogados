import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  compress: true,
  async headers() {
    return ["/olvide-contrasena", "/restablecer-contrasena", "/api/recuperacion/:path*"].map((source) => ({
      source,
      headers: [
        { key: "Cache-Control", value: "no-store" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Robots-Tag", value: "noindex, nofollow" },
        { key: "X-Frame-Options", value: "DENY" },
      ],
    }));
  },
  images: {
    formats: ["image/avif", "image/webp"],
    deviceSizes: [320, 390, 640, 768, 1024, 1280, 1440, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256],
  },
};

export default nextConfig;
