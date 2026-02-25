import type { PropsWithChildren } from "react";

type StatusChipProps = PropsWithChildren<{
  tone?: "neutral" | "success" | "danger" | "accent";
}>;

function StatusChip({ tone = "neutral", children }: StatusChipProps) {
  return <span className={`status-chip status-chip--${tone}`}>{children}</span>;
}

export default StatusChip;
