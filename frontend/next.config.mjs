/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/',
          destination: '/index-veritas.html',
        },
      ],
    };
  },
};

export default nextConfig;
