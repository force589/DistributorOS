process.env.EXPO_PUBLIC_APP_ENV = 'development';
process.env.EXPO_PUBLIC_WEB_API_URL = 'https://api.example.com/api/v1';
process.env.EXPO_PUBLIC_ANDROID_API_URL = 'https://api.example.com/api/v1';
process.env.EXPO_PUBLIC_IOS_API_URL = 'https://api.example.com/api/v1';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));
