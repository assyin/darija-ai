import { Badge } from "@/components/ui/badge";

interface StatusBadgeProps {
  isPublished: boolean;
}

export function StatusBadge({ isPublished }: StatusBadgeProps) {
  return (
    <Badge variant={isPublished ? "success" : "warning"}>
      {isPublished ? "Publié" : "Brouillon"}
    </Badge>
  );
}
