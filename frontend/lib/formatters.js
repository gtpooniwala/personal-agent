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
  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(diffMs / 86400000);
  const years = Math.floor(days / 365);

  if (seconds < 30) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  if (days < 30) {
    const weeks = Math.max(1, Math.floor(days / 7));
    return `${weeks} week${weeks === 1 ? "" : "s"} ago`;
  }
  if (days < 365) {
    const months = Math.max(1, Math.floor(days / 30));
    return `${months} month${months === 1 ? "" : "s"} ago`;
  }

  return `${years} year${years === 1 ? "" : "s"} ago`;
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
