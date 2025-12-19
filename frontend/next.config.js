/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    serverActions: {
      allowedOrigins: ['localhost:3000'],
    },
  },
  async rewrites() {
    // Only enable API proxy in development - production uses direct API URLs
    if (process.env.NODE_ENV === 'development') {
      const apiTarget = process.env.DEV_API_URL || 'http://localhost:8000';
      return [
        {
          source: '/api/:path*',
          destination: `${apiTarget}/api/:path*`,
        },
      ];
    }
    return [];
  },
}

module.exports = nextConfig
