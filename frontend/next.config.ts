import type { NextConfig } from "next";

const backendUrl = process.env.INTERNAL_API_URL ?? "http://helpdesk-backend:8004";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  allowedDevOrigins: ["helpdesk.desangosse.com.br"],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
