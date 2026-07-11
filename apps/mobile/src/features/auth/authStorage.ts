import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const refreshTokenKey = 'distributoros.refresh-token';

export const authStorage = {
  async getRefreshToken(): Promise<string | null> {
    if (Platform.OS === 'web') {
      return null;
    }
    return SecureStore.getItemAsync(refreshTokenKey);
  },

  async setRefreshToken(value: string): Promise<void> {
    if (Platform.OS !== 'web') {
      await SecureStore.setItemAsync(refreshTokenKey, value);
    }
  },

  async clearRefreshToken(): Promise<void> {
    if (Platform.OS !== 'web') {
      await SecureStore.deleteItemAsync(refreshTokenKey);
    }
  },
};

export type AuthStorage = typeof authStorage;

