/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // "standalone" solo para la imagen de Docker (NEXT_OUTPUT=standalone); `next start` local no lo admite.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
};

export default nextConfig;
