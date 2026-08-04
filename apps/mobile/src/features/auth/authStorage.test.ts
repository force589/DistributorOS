import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { authStorage } from './authStorage';

function setPlatform(os: string): void {
  Object.defineProperty(Platform, 'OS', {
    configurable: true,
    get: () => os,
  });
}

describe('authentication storage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    setPlatform('ios');
  });

  it('keeps web refresh sessions in HttpOnly cookies instead of JavaScript storage', async () => {
    setPlatform('web');

    await expect(authStorage.getRefreshToken()).resolves.toBeNull();
    await authStorage.setRefreshToken('web-refresh-token');
    await authStorage.clearRefreshToken();

    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
    expect(SecureStore.deleteItemAsync).not.toHaveBeenCalled();
  });

  it('continues using SecureStore for native refresh sessions', async () => {
    setPlatform('android');
    jest.mocked(SecureStore.getItemAsync).mockResolvedValue('native-refresh-token');

    await expect(authStorage.getRefreshToken()).resolves.toBe('native-refresh-token');
    await authStorage.setRefreshToken('rotated-native-token');
    await authStorage.clearRefreshToken();

    expect(SecureStore.getItemAsync).toHaveBeenCalledWith('distributoros.refresh-token');
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'distributoros.refresh-token',
      'rotated-native-token',
    );
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('distributoros.refresh-token');
  });
});
