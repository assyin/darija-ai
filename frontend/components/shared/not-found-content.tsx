import Link from "next/link";

// Branded Darija 404 content, shared by the locale-scoped not-found
// (notFound() inside [locale] pages) and the global app/not-found.tsx
// (unmatched top-level routes).
export function NotFoundContent() {
  return (
    <main className="container-wide flex min-h-[60vh] flex-col items-center justify-center py-24 text-center">
      <p className="font-arabic-display text-7xl font-bold text-[var(--color-primary)]">
        404
      </p>
      <h1 dir="rtl" className="font-arabic-display mt-6 text-3xl md:text-4xl">
        الصفحة ما لقيناهاش
      </h1>
      <p
        dir="rtl"
        className="font-arabic mt-4 max-w-md text-lg text-[var(--color-muted-foreground)]"
      >
        يمكن الرابط قديم ولا الصفحة تبدلات. رجع للصفحة الرئيسية وكمّل القراءة.
      </p>
      <Link
        href="/"
        className="mt-10 inline-flex items-center justify-center rounded-md bg-[var(--color-primary)] px-7 py-3 text-base font-semibold text-white transition-colors hover:bg-[var(--color-primary-dark)]"
      >
        الرجوع للرئيسية
      </Link>
    </main>
  );
}
