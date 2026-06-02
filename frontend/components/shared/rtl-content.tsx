"use client";

import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

interface RtlContentProps {
  markdown: string;
  className?: string;
  /** Render direction. Default "rtl" (Darija); pass "ltr" for French. */
  dir?: "rtl" | "ltr";
}

export function RtlContent({ markdown, className, dir = "rtl" }: RtlContentProps) {
  return (
    <div
      className={cn(dir === "rtl" ? "prose-rtl" : "prose-ltr", className)}
      dir={dir}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
