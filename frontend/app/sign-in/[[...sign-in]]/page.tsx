import { SignIn } from "@clerk/nextjs";
import { AuthNotConfigured } from "@/components/AuthNotConfigured";
import { clerkConfigured } from "@/lib/clerkConfigured";

export default function SignInPage() {
  /* <SignIn /> needs a publishable key to mount. On a deployment without
     Clerk credentials it cannot render, and proxy.ts sends every protected
     path here, so this is where that state has to be explained rather than
     thrown. */
  if (!clerkConfigured()) {
    return <AuthNotConfigured action="Signing in" />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn />
    </div>
  );
}
