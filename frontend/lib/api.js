export const API_BASE = "/api/agent";
export const RUNTIME_API_BASE = API_BASE;

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

function normalizeEndpoint(endpoint) {
  if (typeof endpoint !== "string" || !endpoint) {
    throw new Error("API endpoint must be a non-empty string.");
  }

  return endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
}

async function callApi(baseUrl, endpoint, options = {}) {
  const url = `${baseUrl}${normalizeEndpoint(endpoint)}`;
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
  return callApi(API_BASE, endpoint, options);
}

export async function runtimeApiCall(endpoint, options = {}) {
  return callApi(RUNTIME_API_BASE, endpoint, options);
}

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiCall("/documents/upload", {
    method: "POST",
    body: formData,
  });
}
