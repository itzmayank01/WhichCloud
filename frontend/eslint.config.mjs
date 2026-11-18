import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Promoted back to error: there is no longer a single explicit `any` in
      // the codebase. The ELK layers now use elkjs's own ElkNode, the API
      // client describes its own responses (CloudResource, FinOpsIssue,
      // IacLiveResources), and genuinely opaque payloads are `unknown`, which
      // forces a check at the point of use. An error here keeps a new one from
      // arriving unnoticed -- the previous 29 accumulated exactly that way.
      "@typescript-eslint/no-explicit-any": "error",
      // Still a warning: 19 of these remain, and they sit in the effect logic
      // that Phase 1 stabilised against stale results, so they need fixing
      // one call site at a time with the Playwright suite as the check --
      // not a sweep. Promote this the moment that count reaches zero.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "test-results/**",
    "playwright-report/**",
  ]),
]);

export default eslintConfig;
