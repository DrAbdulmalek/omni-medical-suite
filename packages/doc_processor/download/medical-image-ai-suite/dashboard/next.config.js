/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  // Transpile recharts for proper SSR handling
  transpilePackages: ['recharts'],
};

module.exports = nextConfig;
