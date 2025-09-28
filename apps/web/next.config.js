/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    const target = (process.env.API_PROXY_URL || 'http://api:8000/api').replace(/\/$/, '');
    return [
      {
        source: '/api/:path*',
        destination: `${target}/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
