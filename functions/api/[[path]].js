import {
  ProxyConfigurationError,
  apiProxyConfigurationErrorResponse,
  createProxyRequest,
  invalidApiResponse,
  upstreamUnavailableResponse,
} from './proxy-utils.mjs';

export async function onRequest({ request, env }) {
  let proxyRequest;

  try {
    proxyRequest = createProxyRequest(request, env);
  } catch (error) {
    if (error instanceof ProxyConfigurationError) {
      return apiProxyConfigurationErrorResponse();
    }
    return invalidApiResponse();
  }

  if (proxyRequest instanceof Response) {
    return proxyRequest;
  }

  try {
    return await fetch(proxyRequest);
  } catch {
    return upstreamUnavailableResponse();
  }
}
