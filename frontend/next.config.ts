import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Next 16 blocks cross-origin requests to dev resources by default, and it
     treats 127.0.0.1 and localhost as different origins. Opening the app on
     127.0.0.1 therefore got its /_next/hmr and client chunks blocked, so the
     page server-rendered fine and then never hydrated.

     That failure is invisible everywhere except the landing page, where it is
     total: the reveal animation starts every panel at `opacity: 0` and relies
     on an effect to set data-revealed="true". No hydration, no effect, so the
     hero renders and everything below it stays blank -- which reads as a
     broken page rather than a blocked request.

     Both spellings of loopback, because the API client deliberately calls
     127.0.0.1 (uvicorn binds IPv4 only) while browsers are usually pointed at
     localhost, and either one can end up as the page's origin. */
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
