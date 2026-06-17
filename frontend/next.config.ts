import type { NextConfig } from "next";

// In production the frontend is a static export served by the FastAPI backend at
// the same origin, so no rewrites are needed. In development `next dev` runs a
// server on :3000 while the backend runs on :8000; proxying /api keeps requests
// same-origin so the session cookie is sent and CORS is not required.
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = isDev
  ? {
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: "http://127.0.0.1:8000/api/:path*",
          },
        ];
      },
    }
  : {
      output: "export",
    };

export default nextConfig;
