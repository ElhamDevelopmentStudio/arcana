import { format } from "date-fns";

export function formatTimestamp(isoTimestamp: string | null): string {
  if (!isoTimestamp) {
    return "-";
  }

  const parsed = new Date(isoTimestamp);
  if (Number.isNaN(parsed.getTime())) {
    return isoTimestamp;
  }

  return format(parsed, "yyyy-MM-dd HH:mm:ss");
}
