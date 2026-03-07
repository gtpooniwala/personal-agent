export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const RUNTIME_API_BASE_FROM_ENV = (process.env.NEXT_PUBLIC_RUNTIME_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function deriveRuntimeBase(apiBase) {
  if (!apiBase) {
    return undefined;
  }

  if (apiBase.endsWith("/api/v1")) {
    return apiBase.slice(0, -7);
  }

  return apiBase;
}

export const RUNTIME_API_BASE = RUNTIME_API_BASE_FROM_ENV || deriveRuntimeBase(API_BASE);

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

function extractErrorMessage(response, payload) {
  if (payload && typeof payload.detail === "string") {
    return payload.detail;
  }

  if (payload && typeof payload.message === "string") {
    return payload.message;
  }

  return `HTTP ${response.status} ${response.statusText}`;
}

async function callApi(baseUrl, endpoint, options = {}, missingBaseMessage) {
  if (baseUrl === undefined || baseUrl === null) {
    throw new Error(missingBaseMessage);
  }

  const url = `${baseUrl}${endpoint}`;
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const hasBody = options.body !== undefined && options.body !== null;
  const headers = new Headers(options.headers || {});

  if (!isFormData && hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const payload = await parseResponse(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(response, payload));
  }

  return payload;
}

export async function apiCall(endpoint, options = {}) {
  return callApi(API_BASE, endpoint, options, "NEXT_PUBLIC_API_BASE_URL is not configured.");
}

export async function runtimeApiCall(endpoint, options = {}) {
  return callApi(
    RUNTIME_API_BASE,
    endpoint,
    options,
    "Runtime API base is not configured. Set NEXT_PUBLIC_RUNTIME_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL.",
  );
}

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiCall("/documents/upload", {
    method: "POST",
    body: formData,
  });
}
