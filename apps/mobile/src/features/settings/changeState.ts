import type {
  CurrencyCode,
  LanguageCode,
  ThemePreference,
} from '@distributoros/api-client';

interface SettingsSnapshot {
  businessName: string;
  currency: CurrencyCode;
  language: LanguageCode;
  themePreference: ThemePreference;
  timezone: string;
}

export function getSettingsChangeState({
  current,
  draft,
}: {
  current: SettingsSnapshot;
  draft: SettingsSnapshot;
}) {
  const hasBusinessProfileChanges =
    draft.businessName.trim() !== current.businessName ||
    draft.currency !== current.currency ||
    draft.timezone.trim() !== current.timezone;
  const hasPresentationChanges =
    draft.language !== current.language || draft.themePreference !== current.themePreference;
  return {
    hasBusinessProfileChanges,
    hasChanges: hasBusinessProfileChanges || hasPresentationChanges,
    hasPresentationChanges,
  };
}

export function getModalBackgroundAccessibilityProps(active: boolean) {
  return {
    accessibilityElementsHidden: active,
    importantForAccessibility: active ? 'no-hide-descendants' : 'auto',
    ...(active ? ({ 'aria-hidden': true } as { 'aria-hidden': boolean }) : {}),
  } as const;
}
