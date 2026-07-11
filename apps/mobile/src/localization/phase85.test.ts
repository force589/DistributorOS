import { darkColors, lightColors } from '@/design/tokens';
import { resolveThemeMode } from '@/design/theme';
import { setActiveStylePalette, StyleSheet } from '@/design/stylesheet';
import { formatCurrency, formatNumber } from '@/formatting/presentation';

import { en } from './resources/en';
import { ml } from './resources/ml';

function leafKeys(value: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(value).flatMap(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return child && typeof child === 'object' && !Array.isArray(child)
      ? leafKeys(child as Record<string, unknown>, path)
      : [path];
  });
}

describe('Phase 8.5 presentation architecture', () => {
  it('keeps Malayalam localization structurally complete', () => {
    expect(leafKeys(ml as unknown as Record<string, unknown>).sort()).toEqual(
      leafKeys(en as unknown as Record<string, unknown>).sort(),
    );
    expect(ml.login.title).toBe('വീണ്ടും സ്വാഗതം');
    expect(ml.settings.title).toBe('ക്രമീകരണങ്ങൾ');
    expect(ml.settings.currency).toBe('കറൻസി');
    expect(ml.insights.reports.title).toBe('റിപ്പോർട്ടുകൾ');
  });

  it('formats supported currencies and localized numbers without conversion', () => {
    expect(formatCurrency('1234.50', 'USD', 'en')).toContain('$');
    expect(formatCurrency('1234.50', 'AED', 'en')).toContain('AED');
    expect(formatCurrency('1234.50', 'INR', 'ml')).toContain('₹');
    expect(formatNumber('1234.5', 'ml')).toBeTruthy();
  });

  it('resolves light, dark, and system themes from centralized palettes', () => {
    expect(resolveThemeMode('light', 'dark')).toBe('light');
    expect(resolveThemeMode('dark', 'light')).toBe('dark');
    expect(resolveThemeMode('system', 'dark')).toBe('dark');
    expect(resolveThemeMode('system', null)).toBe('light');
    expect(lightColors.background).not.toBe(darkColors.background);
  });

  it('applies theme changes to token-styled legacy screens without an app restart', () => {
    const styles = StyleSheet.create({
      card: { backgroundColor: lightColors.surface, borderColor: lightColors.border },
    });

    setActiveStylePalette('dark');
    expect(styles.card.backgroundColor).toBe(darkColors.surface);
    expect(styles.card.borderColor).toBe(darkColors.border);

    setActiveStylePalette('light');
    expect(styles.card.backgroundColor).toBe(lightColors.surface);
  });
});
