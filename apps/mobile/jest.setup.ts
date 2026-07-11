process.env.EXPO_PUBLIC_APP_ENV = 'development';
process.env.EXPO_PUBLIC_WEB_API_URL = 'http://localhost:8000/api/v1';
process.env.EXPO_PUBLIC_ANDROID_API_URL = 'http://10.0.2.2:8000/api/v1';
process.env.EXPO_PUBLIC_IOS_API_URL = 'http://localhost:8000/api/v1';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));
