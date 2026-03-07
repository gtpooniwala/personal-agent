export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
const RUNTIME_API_BASE_FROM_ENV = process.env.NEXT_PUBLIC_RUNTIME_API_BASE_URL?.replace(/\/$/, "");

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

export async function apiCall(endpoint, options = {}) {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  const url = `${API_BASE}${endpoint}`;
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

export async function runtimeApiCall(endpoint, options = {}) {
  if (!RUNTIME_API_BASE) {
    throw new Error(
      "Runtime API base is not configured. Set NEXT_PUBLIC_RUNTIME_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL.",
    );
  }

  const url = `${RUNTIME_API_BASE}${endpoint}`;
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

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiCall("/documents/upload", {
    method: "POST",
    body: formData,
  });
}
