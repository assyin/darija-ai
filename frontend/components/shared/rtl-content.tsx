"use client";

import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

interface RtlContentProps {
  markdown: string;
  className?: string;
}

export function RtlContent({ markdown, className }: RtlContentProps) {
  return (
    <div className={cn("prose-rtl", className)} dir="rtl">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
