import { getLocales } from 'expo-localization';
import { createInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';

import { en } from './resources/en';
import { ml } from './resources/ml';

const deviceLanguage = getLocales()[0]?.languageCode ?? 'en';
const i18n = createInstance();

void i18n.use(initReactI18next).init({
  initAsync: false,
  lng: deviceLanguage,
  fallbackLng: 'en',
  supportedLngs: ['en', 'ml'],
  resources: {
    en: { translation: en },
    ml: { translation: ml },
  },
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
