import { environment, validateApiUrl } from './environment';

describe('API environment configuration', () => {
  it('loads a platform-specific absolute native API URL', () => {
    expect(environment.apiUrl).toMatch(/^https?:\/\//);
  });

  it('rejects relative and insecure production native URLs', () => {
    expect(() => validateApiUrl('/api/v1', 'android', 'development')).toThrow(
      'absolute http or https URL',
    );
    expect(() => validateApiUrl('http://api.example.com', 'ios', 'production')).toThrow(
      'must use HTTPS',
    );
    expect(() => validateApiUrl('https://api.example.com', 'ios', 'production')).not.toThrow();
  });
});
