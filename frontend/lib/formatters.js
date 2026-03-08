export function formatRelativeTime(dateString) {
  if (!dateString) return "Unknown time";

  const needsTimezoneSuffix =
    !dateString.includes("Z") &&
    !dateString.includes("+") &&
    !dateString.slice(10).includes("-");

  const parsed = new Date(needsTimezoneSuffix ? `${dateString}Z` : dateString);

  if (Number.isNaN(parsed.getTime())) {
    return "Invalid date";
  }

  const diffMs = Date.now() - parsed.getTime();
  const isFuture = diffMs < 0;
  const absoluteDiffMs = Math.abs(diffMs);
  const seconds = Math.floor(absoluteDiffMs / 1000);
  const minutes = Math.floor(absoluteDiffMs / 60000);
  const hours = Math.floor(absoluteDiffMs / 3600000);
  const days = Math.floor(absoluteDiffMs / 86400000);
  const years = Math.floor(days / 365);

  const formatShort = (value, unit) => (isFuture ? `in ${value}${unit}` : `${value}${unit} ago`);
  const formatLong = (value, unit) =>
    isFuture
      ? `in ${value} ${unit}${value === 1 ? "" : "s"}`
      : `${value} ${unit}${value === 1 ? "" : "s"} ago`;

  if (seconds < 30) return isFuture ? "in a few seconds" : "Just now";
  if (seconds < 60) return formatShort(seconds, "s");
  if (minutes < 60) return formatShort(minutes, "m");
  if (hours < 24) return formatShort(hours, "h");
  if (days < 7) return formatLong(days, "day");
  if (days < 30) {
    const weeks = Math.max(1, Math.floor(days / 7));
    return formatLong(weeks, "week");
  }
  if (days < 365) {
    const months = Math.max(1, Math.floor(days / 30));
    return formatLong(months, "month");
  }

  return formatLong(years, "year");
}

export function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  const sizeIdx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / 1024 ** sizeIdx;

  return `${size.toFixed(sizeIdx === 0 ? 0 : 1)} ${units[sizeIdx]}`;
}

export function truncateText(text, maxLength) {
  if (typeof text !== "string") return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

export function formatRunStatusLabel(status) {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "retrying":
      return "Retrying";
    case "succeeded":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelling":
      return "Cancelling";
    case "cancelled":
      return "Cancelled";
    default:
      return "";
  }
}

export function formatDocumentStatusLabel(status) {
  switch (status) {
    case "completed":
      return "Ready";
    case "processing":
      return "Indexing";
    case "pending":
      return "Queued";
    case "failed":
      return "Failed";
    default:
      return "Unknown";
  }
}
