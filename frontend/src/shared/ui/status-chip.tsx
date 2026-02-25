import type { PropsWithChildren } from "react";

import { Badge } from "@/components/ui/badge";

type StatusChipProps = PropsWithChildren<{
  tone?: "neutral" | "success" | "danger" | "accent";
}>;

function StatusChip({ tone = "neutral", children }: StatusChipProps) {
  return <Badge className={`status-chip status-chip--${tone}`}>{children}</Badge>;
}

export default StatusChip;
