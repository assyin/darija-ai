import Image from "next/image";

import { cn } from "@/lib/utils";

/**
 * Brand logo mark — the glowing neon AI brain shipped under `/logo-mark.png`.
 * Shared by Header, Footer, and anywhere else the mark appears with the
 * wordmark. Size + extra glow shadow are configurable; default is 36 px
 * which matches the header wordmark baseline.
 */
export function LogoMark({
  size = 36,
  className,
  priority = false,
}: {
  size?: number;
  className?: string;
  priority?: boolean;
}) {
  return (
    <span
      className={cn("relative inline-block shrink-0", className)}
      style={{ width: size, height: size }}
    >
      <Image
        src="/logo-mark.png"
        alt=""
        fill
        sizes={`${size}px`}
        priority={priority}
        className="object-contain drop-shadow-[0_0_10px_rgba(216,80,255,0.55)]"
      />
    </span>
  );
}
