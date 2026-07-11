const http = require('node:http');

const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
const existingEnhancer = config.server?.enhanceMiddleware;

config.server = {
  ...config.server,
  enhanceMiddleware(middleware, metroServer) {
    const metroMiddleware = existingEnhancer
      ? existingEnhancer(middleware, metroServer)
      : middleware;

    return (request, response, next) => {
      if (!request.url?.startsWith('/api/')) {
        return metroMiddleware(request, response, next);
      }

      const headers = { ...request.headers, host: 'localhost:8000' };
      delete headers.connection;

      const upstream = http.request(
        {
          family: 4,
          headers,
          hostname: '127.0.0.1',
          method: request.method,
          path: request.url,
          port: 8000,
        },
        (upstreamResponse) => {
          response.writeHead(
            upstreamResponse.statusCode ?? 502,
            upstreamResponse.statusMessage,
            upstreamResponse.headers,
          );
          upstreamResponse.pipe(response);
        },
      );

      upstream.on('error', () => {
        if (response.headersSent) {
          response.destroy();
          return;
        }
        response.writeHead(502, { 'Content-Type': 'application/json' });
        response.end(
          JSON.stringify({
            error: {
              code: 'NETWORK_ERROR',
              message: 'The local API could not be reached. Try again.',
            },
          }),
        );
      });

      request.pipe(upstream);
    };
  },
};

module.exports = config;
