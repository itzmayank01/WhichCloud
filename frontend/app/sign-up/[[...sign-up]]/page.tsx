import { SignUp } from "@clerk/nextjs";
import { AuthNotConfigured } from "@/components/AuthNotConfigured";
import { clerkConfigured } from "@/lib/clerkConfigured";

export default function SignUpPage() {
  /* Same reason as /sign-in: <SignUp /> cannot mount without a publishable
     key, so an unconfigured deployment gets an explanation instead of a
     500. */
  if (!clerkConfigured()) {
    return <AuthNotConfigured action="Creating an account" />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignUp />
    </div>
  );
}
