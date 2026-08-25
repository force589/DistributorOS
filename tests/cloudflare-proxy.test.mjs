import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ProxyConfigurationError,
  createProxyRequest,
  resolveUpstreamApiBaseUrl,
} from '../functions/api/proxy-utils.mjs';

describe('Cloudflare Pages API proxy', () => {
  it('routes same-origin web API requests to the configured backend', () => {
    const request = new Request(
      'https://distributoros.pages.dev/api/v1/auth/refresh?attempt=1',
      {
        method: 'POST',
        headers: {
          cookie: 'distributoros_refresh=redacted',
          origin: 'https://distributoros.pages.dev',
          'x-client-platform': 'web',
        },
      },
    );

    const proxyRequest = createProxyRequest(request, {
      EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1',
    });

    assert.equal(
      proxyRequest.url,
      'https://api.example.com/api/v1/auth/refresh?attempt=1',
    );
    assert.equal(proxyRequest.method, 'POST');
    assert.equal(proxyRequest.headers.get('cookie'), 'distributoros_refresh=redacted');
    assert.equal(proxyRequest.headers.get('origin'), 'https://distributoros.pages.dev');
    assert.equal(proxyRequest.headers.get('x-client-platform'), 'web');
  });

  it('requires a safe HTTPS /api/v1 upstream without accepting path injection', () => {
    assert.equal(
      resolveUpstreamApiBaseUrl({ EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1' }),
      'https://api.example.com/api/v1',
    );

    assert.throws(() => resolveUpstreamApiBaseUrl({}), ProxyConfigurationError);
    assert.throws(
      () => resolveUpstreamApiBaseUrl({ EXPO_PUBLIC_API_URL: 'https://api.example.com' }),
      ProxyConfigurationError,
    );
    assert.throws(
      () => resolveUpstreamApiBaseUrl({ EXPO_PUBLIC_API_URL: 'https://api.example.com' }),
      /end with \/api\/v1/,
    );
    assert.throws(
      () => resolveUpstreamApiBaseUrl({ EXPO_PUBLIC_API_URL: 'http://api.example.com/api/v1' }),
      ProxyConfigurationError,
    );
    assert.throws(
      () => resolveUpstreamApiBaseUrl({ EXPO_PUBLIC_API_URL: 'http://api.example.com/api/v1' }),
      /HTTPS/,
    );
  });

  it('does not proxy non-DistributorOS API paths', () => {
    const request = new Request('https://distributoros.pages.dev/products/PROD-000001');

    assert.throws(() => createProxyRequest(request), /Only DistributorOS API requests/);
  });

  it('rejects unsupported methods before reaching the upstream API', async () => {
    const request = new Request('https://distributoros.pages.dev/api/v1/customers', {
      method: 'DELETE',
    });

    const response = createProxyRequest(request);
    const body = await response.json();

    assert.equal(response.status, 405);
    assert.equal(body.error.code, 'METHOD_NOT_ALLOWED');
  });
});
