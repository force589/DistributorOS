import type {
  CurrencyCode,
  LanguageCode,
  ThemePreference,
} from '@distributoros/api-client';
import * as SecureStore from 'expo-secure-store';
import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Platform, useColorScheme } from 'react-native';

import { useAuth } from '@/features/auth/AuthContext';
import i18n from '@/localization/i18n';
import { setPresentationPreferences } from '@/formatting/presentation';

import {
  animation,
  breakpoints,
  type ColorPalette,
  darkColors,
  elevations,
  iconSizes,
  lightColors,
  radii,
  spacing,
  typography,
} from './tokens';
import { setActiveStylePalette } from './stylesheet';

const storageKey = 'distributoros.preferences';

export interface AppPreferences {
  currency: CurrencyCode;
  language: LanguageCode;
  themePreference: ThemePreference;
  timezone: string;
}

export interface AppTheme {
  mode: 'light' | 'dark';
  colors: ColorPalette;
  spacing: typeof spacing;
  radii: typeof radii;
  typography: typeof typography;
  elevations: typeof elevations;
  animation: typeof animation;
  iconSizes: typeof iconSizes;
  breakpoints: typeof breakpoints;
}

interface PreferencesContextValue extends AppPreferences {
  locale: 'en-IN' | 'ml-IN';
  theme: AppTheme;
  updatePreferences: (changes: Partial<AppPreferences>) => void;
  clearPreviewPreferences: () => void;
}

const defaults: AppPreferences = {
  currency: 'INR',
  language: 'en',
  themePreference: 'system',
  timezone: 'Asia/Kolkata',
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);
const fallbackTheme: AppTheme = {
  mode: 'light',
  colors: lightColors,
  spacing,
  radii,
  typography,
  elevations,
  animation,
  iconSizes,
  breakpoints,
};

export function resolveThemeMode(
  preference: ThemePreference,
  systemTheme: 'light' | 'dark' | 'unspecified' | null | undefined,
): 'light' | 'dark' {
  return preference === 'system' ? (systemTheme === 'dark' ? 'dark' : 'light') : preference;
}

function readWebPreferences(): AppPreferences {
  if (Platform.OS !== 'web' || typeof localStorage === 'undefined') return defaults;
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(storageKey) ?? '{}') };
  } catch {
    return defaults;
  }
}

export function AppPreferencesProvider({ children }: PropsWithChildren) {
  const { user } = useAuth();
  const systemTheme = useColorScheme();
  const [preferences, setPreferences] = useState<AppPreferences>(readWebPreferences);
  const [previewPreferences, setPreviewPreferences] = useState<{
    businessId: string | null;
    changes: Partial<AppPreferences>;
  }>({ businessId: null, changes: {} });
  const businessId = user?.business.id ?? null;
  const activePreview = useMemo(
    () => (
      previewPreferences.businessId === businessId ? previewPreferences.changes : {}
    ),
    [businessId, previewPreferences],
  );

  useEffect(() => {
    if (Platform.OS === 'web' || user) return;
    void SecureStore.getItemAsync(storageKey).then((stored) => {
      if (!stored) return;
      try {
        setPreferences((current) => ({ ...current, ...JSON.parse(stored) }));
      } catch {
        // Invalid local preferences are ignored in favor of safe defaults.
      }
    });
  }, [user]);

  const effectivePreferences = useMemo<AppPreferences>(
    () =>
      user
        ? {
            currency: user.business.currency,
            language: user.business.language,
            themePreference: user.business.theme,
            timezone: user.business.timezone,
            ...activePreview,
          }
        : preferences,
    [activePreview, preferences, user],
  );

  useEffect(() => {
    void i18n.changeLanguage(effectivePreferences.language);
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      document.documentElement.lang = effectivePreferences.language;
      document.documentElement.dir = 'ltr';
    }
    setPresentationPreferences(
      effectivePreferences.currency,
      effectivePreferences.language,
      effectivePreferences.timezone,
    );
    const serialized = JSON.stringify(effectivePreferences);
    if (Platform.OS === 'web' && typeof localStorage !== 'undefined') {
      localStorage.setItem(
        businessId ? `${storageKey}.${businessId}` : storageKey,
        serialized,
      );
    } else {
      void SecureStore.setItemAsync(storageKey, serialized);
    }
  }, [businessId, effectivePreferences]);

  const updatePreferences = useCallback((changes: Partial<AppPreferences>) => {
    setPreferences((current) => ({ ...current, ...changes }));
    if (businessId) {
      setPreviewPreferences((current) => ({
        businessId,
        changes: {
          ...(current.businessId === businessId ? current.changes : {}),
          ...changes,
        },
      }));
    }
  }, [businessId]);

  const clearPreviewPreferences = useCallback(() => {
    setPreviewPreferences({ businessId: null, changes: {} });
  }, []);

  const mode = resolveThemeMode(effectivePreferences.themePreference, systemTheme);
  setActiveStylePalette(mode);
  const theme = useMemo<AppTheme>(
    () => ({
      mode,
      colors: mode === 'dark' ? darkColors : lightColors,
      spacing,
      radii,
      typography,
      elevations,
      animation,
      iconSizes,
      breakpoints,
    }),
    [mode],
  );

  const value = useMemo<PreferencesContextValue>(
    () => ({
      ...effectivePreferences,
      locale: effectivePreferences.language === 'ml' ? 'ml-IN' : 'en-IN',
      theme,
      updatePreferences,
      clearPreviewPreferences,
    }),
    [clearPreviewPreferences, effectivePreferences, theme, updatePreferences],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): PreferencesContextValue {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error('usePreferences must be used inside AppPreferencesProvider.');
  return context;
}

export function useTheme(): AppTheme {
  return useContext(PreferencesContext)?.theme ?? fallbackTheme;
}
