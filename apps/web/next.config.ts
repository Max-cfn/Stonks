import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  transpilePackages: ["@stonks/shared-types"],
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },
};

export default withNextIntl(nextConfig);
