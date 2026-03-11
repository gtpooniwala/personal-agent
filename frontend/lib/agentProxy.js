const VERSIONED_ROOTS = new Set(["conversations", "tools", "documents", "health", "observability"]);
const RUNTIME_ROOTS = new Set(["chat", "runs"]);
const BLOCKED_REQUEST_HEADERS = new Set([
  "authorization",
  "connection",
  "content-length",
  "cookie",
  "host",
  "x-forwarded-for",
  "x-forwarded-host",
  "x-forwarded-port",
  "x-forwarded-proto",
]);
const RESPONSE_HEADER_ALLOWLIST = new Set([
  "cache-control",
  "content-type",
  "location",
  "vary",
  "www-authenticate",
  "x-request-id",
]);

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

function normalizePathSegments(path) {
  if (Array.isArray(path)) {
    return path.filter(Boolean);
  }

  if (typeof path !== "string") {
    return [];
  }

  return path.split("/").filter(Boolean);
}

function hasUnsafePathSegments(pathSegments) {
  return pathSegments.some((segment) => segment === "." || segment === "..");
}

function backendPathForSegments(pathSegments) {
  const [root, ...rest] = pathSegments;
  if (!root) {
    return null;
  }

  const suffix = rest.length > 0 ? `/${rest.join("/")}` : "";

  if (VERSIONED_ROOTS.has(root)) {
    return `/api/v1/${root}${suffix}`;
  }

  if (RUNTIME_ROOTS.has(root)) {
    return `/${root}${suffix}`;
  }

  return null;
}

function proxyConfig(env) {
  const apiBaseUrl = trimTrailingSlash(env.API_BASE_URL || "");
  const agentApiKey = (env.AGENT_API_KEY || "").trim();

  if (!apiBaseUrl) {
    return { error: "API_BASE_URL must be configured for the Next.js agent proxy." };
  }

  if (!agentApiKey) {
    return { error: "AGENT_API_KEY must be configured for the Next.js agent proxy." };
  }

  return { apiBaseUrl, agentApiKey };
}

async function readRequestBody(request) {
  if (request.method === "GET" || request.method === "HEAD" || request.method === "OPTIONS") {
    return { body: undefined, dropContentType: false };
  }

  const contentType = request.headers.get("content-type") || "";

  if (contentType.includes("multipart/form-data")) {
    return {
      body: await request.formData(),
      dropContentType: true,
    };
  }

  if (
    contentType.includes("application/json") ||
    contentType.includes("text/") ||
    contentType.includes("application/x-www-form-urlencoded")
  ) {
    return {
      body: await request.text(),
      dropContentType: false,
    };
  }

  return {
    body: await request.arrayBuffer(),
    dropContentType: false,
  };
}

function buildUpstreamHeaders(requestHeaders, agentApiKey, { dropContentType = false } = {}) {
  const headers = new Headers();

  for (const [key, value] of requestHeaders.entries()) {
    const normalizedKey = key.toLowerCase();
    if (BLOCKED_REQUEST_HEADERS.has(normalizedKey)) {
      continue;
    }
    if (dropContentType && normalizedKey === "content-type") {
      continue;
    }
    headers.set(key, value);
  }

  headers.set("Authorization", `Bearer ${agentApiKey}`);
  return headers;
}

function rewriteLocationHeader(value, apiBaseUrl) {
  if (!value) {
    return null;
  }

  let backendBaseUrl;
  let resolvedUrl;

  try {
    backendBaseUrl = new URL(`${apiBaseUrl}/`);
    resolvedUrl = new URL(value, backendBaseUrl);
  } catch {
    return value;
  }

  if (resolvedUrl.origin !== backendBaseUrl.origin) {
    return value;
  }

  let proxyPath = null;
  if (resolvedUrl.pathname.startsWith("/api/v1/")) {
    proxyPath = `/api/agent${resolvedUrl.pathname.slice("/api/v1".length)}`;
  } else if (resolvedUrl.pathname === "/chat" || resolvedUrl.pathname.startsWith("/runs/")) {
    proxyPath = `/api/agent${resolvedUrl.pathname}`;
  }

  if (!proxyPath) {
    return null;
  }

  return `${proxyPath}${resolvedUrl.search}${resolvedUrl.hash}`;
}

function buildResponseHeaders(upstreamHeaders, apiBaseUrl) {
  const headers = new Headers();

  for (const [key, value] of upstreamHeaders.entries()) {
    const normalizedKey = key.toLowerCase();
    if (!RESPONSE_HEADER_ALLOWLIST.has(normalizedKey)) {
      continue;
    }

    if (normalizedKey === "location") {
      const rewrittenLocation = rewriteLocationHeader(value, apiBaseUrl);
      if (rewrittenLocation) {
        headers.set(key, rewrittenLocation);
      }
      continue;
    }

    headers.set(key, value);
  }

  return headers;
}

function buildBackendUrl(apiBaseUrl, backendPath, requestUrl) {
  const url = new URL(backendPath, `${apiBaseUrl}/`);
  url.search = new URL(requestUrl).search;
  return url;
}

export async function proxyAgentRequest(request, path, { env = process.env, fetchImpl = fetch } = {}) {
  const config = proxyConfig(env);
  if (config.error) {
    return Response.json({ detail: config.error }, { status: 500 });
  }

  const pathSegments = normalizePathSegments(path);
  if (hasUnsafePathSegments(pathSegments)) {
    return Response.json({ detail: "Unsafe agent proxy route." }, { status: 400 });
  }
  const backendPath = backendPathForSegments(pathSegments);
  if (!backendPath) {
    return Response.json({ detail: "Unknown agent proxy route." }, { status: 404 });
  }

  const targetUrl = buildBackendUrl(config.apiBaseUrl, backendPath, request.url);
  const { body, dropContentType } = await readRequestBody(request);
  const headers = buildUpstreamHeaders(request.headers, config.agentApiKey, { dropContentType });
  const upstreamResponse = await fetchImpl(targetUrl, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
    redirect: "manual",
    signal: request.signal,
  });

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: buildResponseHeaders(upstreamResponse.headers, config.apiBaseUrl),
  });
}

export const __testOnly__ = {
  backendPathForSegments,
  buildBackendUrl,
  buildResponseHeaders,
  buildUpstreamHeaders,
  hasUnsafePathSegments,
  normalizePathSegments,
  proxyConfig,
  readRequestBody,
  rewriteLocationHeader,
};
