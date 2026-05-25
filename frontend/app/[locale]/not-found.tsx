import { NotFoundContent } from "@/components/shared/not-found-content";

// Renders inside the [locale] layout (inherits lang/dir + Tajawal).
// Triggered by notFound() in locale pages, e.g. a missing article slug.
export default function NotFound() {
  return <NotFoundContent />;
}
