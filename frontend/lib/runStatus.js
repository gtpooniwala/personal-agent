import { formatRunStatusLabel } from "@/lib/formatters";

export const RUN_IN_PROGRESS_STATUSES = new Set(["queued", "running", "retrying", "cancelling"]);

const RUN_STATUS_CLASSNAMES = new Set([
  "queued",
  "running",
  "retrying",
  "succeeded",
  "failed",
  "cancelling",
  "cancelled",
  "idle",
  "degraded",
]);

function titleCaseWords(value) {
  return value
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function formatToolLabel(toolName) {
  if (!toolName) {
    return "";
  }

  return titleCaseWords(String(toolName).replace(/[_-]+/g, " ").trim());
}

export function getRunTone(status, transport) {
  if (transport === "degraded" && RUN_IN_PROGRESS_STATUSES.has(status)) {
    return "degraded";
  }

  return RUN_STATUS_CLASSNAMES.has(status) ? status : "idle";
}

export function getRunStatusClassName(status, transport) {
  return getRunTone(status, transport);
}

export function getRunPresentation(runState) {
  const status = runState?.status || "";
  const latestEvent = runState?.latestEvent || null;
  const transport = runState?.transport || "";
  const transportMessage = runState?.transportMessage || "";
  const error = runState?.error || "";

  if (!status && !transportMessage) {
    return null;
  }

  const isTerminal = Boolean(status) && !RUN_IN_PROGRESS_STATUSES.has(status);
  const tone = getRunTone(status, transport);

  if (transport === "degraded" && !isTerminal) {
    return {
      tone,
      label: "Live updates lost",
      shortLabel: "Updates lost",
      detail:
        transportMessage ||
        "The run may still be in progress. Refresh the conversation to check the final response.",
      status,
      transport,
      isTerminal,
    };
  }

  let label = formatRunStatusLabel(status) || "Working";
  let shortLabel = label;
  let detail = "";

  switch (status) {
    case "queued":
      label = "Queued";
      shortLabel = "Queued";
      detail = "Waiting for an execution slot.";
      break;
    case "running":
      label = "Working";
      shortLabel = "Working";
      detail = "The agent is processing your request.";
      break;
    case "retrying":
      label = "Retrying";
      shortLabel = "Retrying";
      detail = "Retrying after a runtime error.";
      break;
    case "cancelling":
      label = "Cancelling";
      shortLabel = "Cancelling";
      detail = "Cancellation is in progress.";
      break;
    case "succeeded":
      label = "Completed";
      shortLabel = "Completed";
      detail = "The latest run finished successfully.";
      break;
    case "failed":
      label = "Failed";
      shortLabel = "Failed";
      detail = error || "The latest run failed.";
      break;
    case "cancelled":
      label = "Cancelled";
      shortLabel = "Cancelled";
      detail = "The latest run was cancelled.";
      break;
    default:
      break;
  }

  if (latestEvent?.type === "queued") {
    label = "Queued";
    shortLabel = "Queued";
  } else if (latestEvent?.type === "started") {
    label = status === "retrying" ? "Retrying" : "Starting";
    shortLabel = label;
  } else if (latestEvent?.type === "retrying") {
    label = "Retrying";
    shortLabel = "Retrying";
  }

  if (latestEvent?.type === "tool_result") {
    const toolLabel = formatToolLabel(latestEvent.tool);
    if (!isTerminal) {
      label = "Working";
      shortLabel = "Working";
    }
    detail = toolLabel ? `Latest completed step: ${toolLabel}.` : latestEvent.message || detail;
  } else if (latestEvent?.message) {
    detail = latestEvent.message;
  }

  if (transport === "polling" && !isTerminal) {
    detail = transportMessage || "Live stream unavailable. Checking status in the background.";
  }

  return {
    tone,
    label,
    shortLabel,
    detail: detail || transportMessage,
    status,
    transport,
    isTerminal,
  };
}
