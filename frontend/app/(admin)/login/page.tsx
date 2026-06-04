"use client";

import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Accept callbackUrl when redirected here by an expired session, so the user
// lands back on the page they were on (e.g. /admin/articles/16). Restrict to
// internal admin paths — never honor an attacker-supplied external URL.
function sanitizeCallbackUrl(value: string | null): string {
  if (!value) return "/admin/articles";
  if (!value.startsWith("/admin")) return "/admin/articles";
  return value;
}

export default function LoginPage() {
  const router = useRouter();
  const search = useSearchParams();
  const callbackUrl = sanitizeCallbackUrl(search.get("callbackUrl"));
  const isExpired = search.get("expired") === "1";
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const form = new FormData(e.currentTarget);
    const res = await signIn("credentials", {
      email: form.get("email"),
      password: form.get("password"),
      redirect: false,
    });

    if (res?.error) {
      setError("Email ou mot de passe incorrect.");
      setSubmitting(false);
      return;
    }
    router.push(callbackUrl);
    router.refresh();
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-widest text-[var(--color-muted-foreground)]">
            DarijaAI
          </p>
          <CardTitle className="text-2xl">Connexion administrateur</CardTitle>
          <CardDescription>
            Outil éditorial réservé au propriétaire du site.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {(isExpired || callbackUrl !== "/admin/articles") && (
            <p
              role="status"
              className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            >
              Votre session a expiré pour des raisons de sécurité. Reconnectez-vous
              pour continuer.
            </p>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                required
                disabled={submitting}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                disabled={submitting}
              />
            </div>
            {error && (
              <p className="text-sm text-red-600" role="alert">
                {error}
              </p>
            )}
            <Button className="w-full" size="lg" type="submit" disabled={submitting}>
              {submitting ? "Connexion…" : "Se connecter"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
