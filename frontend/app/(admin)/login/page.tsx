"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const [submitting, setSubmitting] = useState(false);

  async function handleDevLogin() {
    setSubmitting(true);
    await signIn("dev-bypass", { redirectTo: "/admin/articles" });
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
        <CardContent className="space-y-6">
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            ⚠️ <strong>Mode développement</strong> — Resend n&apos;est pas encore
            configuré. Le magic link est désactivé. Cliquez ci-dessous pour vous
            connecter automatiquement comme administrateur local.
          </div>
          <Button
            className="w-full"
            size="lg"
            onClick={handleDevLogin}
            disabled={submitting}
          >
            {submitting ? "Connexion…" : "Se connecter en mode DEV"}
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
