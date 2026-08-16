import NextAuth, { type NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";
import GitHub from "next-auth/providers/github";

/**
 * Authentication, self-hosted.
 *
 * Replaced Clerk, which required a phone number at sign-up and refused Indian
 * numbers on a development instance -- a combination that made the product
 * unreachable for the people building it. That requirement is configurable
 * only from Clerk's dashboard, not through its API, so there was no way to fix
 * it from this repository.
 *
 * Sessions are JWTs rather than database rows. This app has nothing per-user
 * to store yet, so a session table would be four migrations and an adapter
 * carrying no data. When saved architectures arrive, that is the moment to add
 * one -- not before.
 *
 * Providers are declared only when their credentials are present. Auth.js
 * otherwise throws at import time on a missing secret, which takes down every
 * page rather than just the sign-in button, and a contributor without GitHub
 * credentials should still be able to run the site.
 */
const providers: NextAuthConfig["providers"] = [];

if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) {
  providers.push(
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
    }),
  );
}

if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  providers.push(
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
    }),
  );
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  session: { strategy: "jwt" },
  pages: { signIn: "/sign-in" },
  trustHost: true,
});

/** Which providers are usable right now, so the sign-in page can say so. */
export function configuredProviders(): string[] {
  return providers
    .map((p) => (typeof p === "function" ? "" : String(p.id ?? "")))
    .filter(Boolean);
}
