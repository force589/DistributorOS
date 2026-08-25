type EnvironmentModule = typeof import('./environment');

const ENV_KEYS = [
  'EXPO_PUBLIC_APP_ENV',
  'EXPO_PUBLIC_API_URL',
  'EXPO_PUBLIC_WEB_API_URL',
  'EXPO_PUBLIC_ANDROID_API_URL',
  'EXPO_PUBLIC_IOS_API_URL',
] as const;

const originalEnv = Object.fromEntries(
  ENV_KEYS.map((key) => [key, process.env[key]]),
) as Partial<Record<(typeof ENV_KEYS)[number], string | undefined>>;

function setEnv(values: Partial<Record<(typeof ENV_KEYS)[number], string>>): void {
  for (const key of ENV_KEYS) {
    delete process.env[key];
  }
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) {
      process.env[key] = value;
    }
  }
}

function loadEnvironment(
  platform: string,
  values: Partial<Record<(typeof ENV_KEYS)[number], string>>,
): EnvironmentModule {
  jest.resetModules();
  jest.doMock('react-native', () => ({
    Platform: { OS: platform },
  }));
  setEnv({
    EXPO_PUBLIC_APP_ENV: 'production',
    ...values,
  });
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require('./environment') as EnvironmentModule;
}

afterEach(() => {
  jest.dontMock('react-native');
  jest.resetModules();
  setEnv(originalEnv);
});

describe('API environment configuration', () => {
  it('uses the same-origin API proxy for production web builds', () => {
    const { environment } = loadEnvironment('web', {
      EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1',
    });

    expect(environment.apiUrl).toBe('/api/v1');
  });

  it('does not let production web override the same-origin API proxy with an absolute URL', () => {
    const { environment } = loadEnvironment('web', {
      EXPO_PUBLIC_WEB_API_URL: 'https://api.example.com/api/v1',
    });

    expect(environment.apiUrl).toBe('/api/v1');
  });

  it('loads development web builds from EXPO_PUBLIC_API_URL', () => {
    const { environment } = loadEnvironment('web', {
      EXPO_PUBLIC_APP_ENV: 'development',
      EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1',
    });

    expect(environment.apiUrl).toBe('https://api.example.com/api/v1');
  });

  it('rejects missing development web API URLs', () => {
    expect(() => loadEnvironment('web', { EXPO_PUBLIC_APP_ENV: 'development' })).toThrow(
      'An API URL is required for the web platform.',
    );
  });

  it('preserves platform-specific native URLs and generic native fallback', () => {
    const androidEnvironment = loadEnvironment('android', {
      EXPO_PUBLIC_APP_ENV: 'development',
      EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1',
      EXPO_PUBLIC_ANDROID_API_URL: 'http://10.0.2.2:8000/api/v1',
    }).environment;

    expect(androidEnvironment.apiUrl).toBe('http://10.0.2.2:8000/api/v1');

    const iosEnvironment = loadEnvironment('ios', {
      EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1',
    }).environment;

    expect(iosEnvironment.apiUrl).toBe('https://api.example.com/api/v1');
  });

  it('rejects relative and insecure production native URLs', () => {
    const { validateApiUrl } = loadEnvironment('web', {
      EXPO_PUBLIC_API_URL: 'https://api.example.com/api/v1',
    });

    expect(() => validateApiUrl('/api/v1', 'android', 'development')).toThrow(
      'absolute http or https URL',
    );
    expect(() => validateApiUrl('http://api.example.com', 'ios', 'production')).toThrow(
      'must use HTTPS',
    );
    expect(() => validateApiUrl('https://api.example.com', 'ios', 'production')).not.toThrow();
  });
});
