/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    API_URL: process.env.API_URL || 'http://localhost:8000'
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://traderai-api:8000/api/:path*'
      }
    ]
  }
}

module.exports = nextConfig
