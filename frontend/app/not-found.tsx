import { NotFoundContent } from "@/components/shared/not-found-content";

// Global 404 for unmatched top-level routes (renders in the root layout,
// which sets <html lang/dir> from the next-intl locale header).
export default function NotFound() {
  return <NotFoundContent />;
}
