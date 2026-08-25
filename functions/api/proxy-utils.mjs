const API_PREFIX = '/api/v1';
const ALLOWED_METHODS = new Set(['GET', 'HEAD', 'POST', 'PATCH', 'OPTIONS']);

export class ProxyConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ProxyConfigurationError';
  }
}

export function resolveUpstreamApiBaseUrl(env = {}) {
  const configuredBaseUrl =
    env.DISTRIBUTOROS_API_BASE_URL ?? env.EXPO_PUBLIC_API_URL ?? env.EXPO_PUBLIC_WEB_API_URL;
  let parsed;

  try {
    parsed = new URL(configuredBaseUrl);
  } catch {
    throw new ProxyConfigurationError(
      'The Cloudflare API proxy requires a valid HTTPS API base URL.',
    );
  }

  const normalizedPath = parsed.pathname.replace(/\/$/, '');
  if (
    parsed.protocol !== 'https:' ||
    normalizedPath !== API_PREFIX ||
    parsed.search ||
    parsed.hash
  ) {
    throw new ProxyConfigurationError(
      'The Cloudflare API proxy base URL must be HTTPS and end with /api/v1.',
    );
  }

  return `${parsed.origin}${API_PREFIX}`;
}

export function createProxyRequest(request, env = {}) {
  const incomingUrl = new URL(request.url);

  if (
    incomingUrl.pathname !== API_PREFIX &&
    !incomingUrl.pathname.startsWith(`${API_PREFIX}/`)
  ) {
    throw new Error('Only DistributorOS API requests can be proxied.');
  }

  if (!ALLOWED_METHODS.has(request.method.toUpperCase())) {
    return new Response(
      JSON.stringify({
        error: {
          code: 'METHOD_NOT_ALLOWED',
          message: 'This request method is not supported.',
        },
      }),
      {
        status: 405,
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  const upstreamUrl =
    `${resolveUpstreamApiBaseUrl(env)}${incomingUrl.pathname.slice(API_PREFIX.length)}` +
    incomingUrl.search;
  const headers = new Headers(request.headers);
  headers.delete('host');

  return new Request(upstreamUrl, {
    method: request.method,
    headers,
    body: ['GET', 'HEAD'].includes(request.method.toUpperCase()) ? undefined : request.body,
    redirect: 'manual',
  });
}

export function invalidApiResponse() {
  return new Response(
    JSON.stringify({
      error: {
        code: 'INVALID_API_PROXY_REQUEST',
        message: 'The requested API path is not available.',
      },
    }),
    {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    },
  );
}

export function apiProxyConfigurationErrorResponse() {
  return new Response(
    JSON.stringify({
      error: {
        code: 'API_PROXY_CONFIGURATION_ERROR',
        message: 'The API proxy is not configured correctly.',
      },
    }),
    {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    },
  );
}

export function upstreamUnavailableResponse() {
  return new Response(
    JSON.stringify({
      error: {
        code: 'UPSTREAM_UNAVAILABLE',
        message: 'The server could not be reached. Check your connection and try again.',
      },
    }),
    {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    },
  );
}
