import { ApiClient } from '@distributoros/api-client';
import { Platform } from 'react-native';

import { environment } from '@/config/environment';

export const apiClient = new ApiClient({
  baseUrl: environment.apiUrl,
  platform: Platform.OS,
});

