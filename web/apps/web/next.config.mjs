/** @type {import('next').NextConfig} */
const isStatic = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

const nextConfig = {
  reactStrictMode: true,
  ...(isStatic
    ? {
        output: "export",
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {}),
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // `static-data.ts` uses node's `fs`. It's only ever called from server
      // components — but webpack still walks the import graph for client
      // bundles. Stub `fs` to an empty module so the client build succeeds.
      config.resolve.fallback = {
        ...(config.resolve.fallback ?? {}),
        fs: false,
        path: false,
      };
    }
    return config;
  },
};

export default nextConfig;
