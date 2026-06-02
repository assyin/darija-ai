import Image from "next/image";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

/**
 * Branded 404 — full-bleed cinematic asset (lost astronaut + Moroccan cosmic
 * portal) with text overlay on the start side. Shared by both
 * `[locale]/not-found.tsx` (notFound() inside locale pages) and
 * `app/not-found.tsx` (unmatched top-level routes). Both routes flow through
 * the next-intl middleware so `getTranslations` resolves the right locale.
 */
export async function NotFoundContent() {
  const t = await getTranslations("not_found");

  return (
    <section
      dir="ltr"
      className="relative isolate flex min-h-[86vh] items-center overflow-hidden bg-[#0a0418]"
    >
      {/* Scene */}
      <div aria-hidden className="absolute inset-0 -z-20">
        <Image
          src="/404/lost-astronaut.png"
          alt=""
          fill
          sizes="100vw"
          priority
          className="object-cover object-[78%_50%]"
        />
      </div>

      {/* Soft scrim on the start side — keeps text readable without splitting */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 55% 65% at 22% 50%, rgba(10,4,24,0.65) 0%, rgba(10,4,24,0.3) 50%, transparent 80%)," +
            "linear-gradient(to top, rgba(10,4,24,0.35) 0%, transparent 55%)",
        }}
      />

      <div className="container-wide relative w-full py-20 lg:py-24">
        <div className="max-w-md lg:max-w-xl" style={{ textAlign: "left" }}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/90">
            {t("kicker")}
          </p>
          <p
            aria-hidden
            className="mt-4 bg-gradient-to-r from-violet-400 via-fuchsia-400 to-pink-400 bg-clip-text font-extrabold leading-none tracking-tighter text-transparent text-[7rem] md:text-[9rem] lg:text-[10rem]"
          >
            404
          </p>
          <h1
            dir="auto"
            className="font-arabic-display mt-2 text-3xl font-extrabold leading-tight text-white md:text-4xl"
          >
            {t("title")}
          </h1>
          <p
            dir="auto"
            className="font-arabic mt-5 max-w-md text-base leading-relaxed text-white/75 md:text-lg"
          >
            {t("message")}
          </p>
          <div className="mt-9">
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-md border-0 bg-gradient-to-r from-violet-600 to-fuchsia-500 px-7 py-3 text-sm font-semibold text-white shadow-[0_0_32px_-4px_rgba(168,85,247,0.75)] transition hover:brightness-110 hover:shadow-[0_0_44px_-2px_rgba(168,85,247,0.9)]"
            >
              <ArrowLeft className="h-4 w-4 rtl:rotate-180" aria-hidden />
              {t("back_button")}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
