import { cn } from "@/lib/utils";

/**
 * Reusable wordmark. The name is configurable (settings.business_name) — no
 * brand string is hardcoded here. Accents the first character, and colors an
 * "AI" suffix with the primary when present. Used by Header and Footer.
 */
export function Brand({ name, className }: { name: string; className?: string }) {
  const aiMatch = /AI$/i.test(name);
  const head = aiMatch ? name.slice(0, -2) : name;
  const tail = aiMatch ? name.slice(-2) : "";
  const firstChar = head.charAt(0);
  const restHead = head.slice(1);

  return (
    <span className={cn("font-display text-xl tracking-tight", className)}>
      <span className="text-[var(--color-accent)]">{firstChar}</span>
      <span className="text-[var(--color-fg)]">{restHead}</span>
      {tail && <span className="text-[var(--color-primary)]">{tail}</span>}
    </span>
  );
}
