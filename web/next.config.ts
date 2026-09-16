import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? '',
  trailingSlash: true,
  output: 'standalone',
}

export default nextConfig
