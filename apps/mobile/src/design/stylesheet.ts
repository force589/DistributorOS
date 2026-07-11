import { StyleSheet as NativeStyleSheet } from 'react-native';

import { darkColors, lightColors, type ColorPalette } from './tokens';

type StyleMap = Record<string, object>;

const colorKeys = Object.keys(lightColors) as (keyof ColorPalette)[];
const lightColorLookup = new Map<string, (keyof ColorPalette)[]>();
for (const key of colorKeys) {
  const value = lightColors[key];
  lightColorLookup.set(value, [...(lightColorLookup.get(value) ?? []), key]);
}

let activePalette: ColorPalette = lightColors;
let paletteVersion = 0;
const resolvedStyleCache = new WeakMap<object, { value: object; version: number }>();

export function setActiveStylePalette(mode: 'light' | 'dark') {
  const nextPalette = mode === 'dark' ? darkColors : lightColors;
  if (activePalette !== nextPalette) {
    activePalette = nextPalette;
    paletteVersion += 1;
  }
}

function resolveColor(value: string, styleProperty?: string): string {
  const candidates = lightColorLookup.get(value);
  if (!candidates?.length) return value;
  if (candidates.length === 1) return activePalette[candidates[0]!];

  if (styleProperty?.toLowerCase().includes('border') && candidates.includes('borderStrong')) {
    return activePalette.borderStrong;
  }
  if (
    styleProperty?.toLowerCase().includes('background') &&
    candidates.includes('surface')
  ) {
    return activePalette.surface;
  }
  if (
    (styleProperty === 'color' || styleProperty?.toLowerCase().includes('tint')) &&
    candidates.includes('textInverse')
  ) {
    return activePalette.textInverse;
  }
  return activePalette[candidates[0]!];
}

function resolveThemeValue(value: unknown, styleProperty?: string): unknown {
  if (typeof value === 'string') {
    return resolveColor(value, styleProperty);
  }
  if (Array.isArray(value)) return value.map((entry) => resolveThemeValue(entry, styleProperty));
  if (!value || typeof value !== 'object') return value;

  const cached = resolvedStyleCache.get(value);
  if (cached?.version === paletteVersion) return cached.value;

  const resolved = Object.fromEntries(
    Object.entries(value).map(([key, nestedValue]) => [key, resolveThemeValue(nestedValue, key)]),
  );
  resolvedStyleCache.set(value, { value: resolved, version: paletteVersion });
  return resolved;
}

function createThemedStyles<T extends StyleMap>(styles: T): T {
  const created = NativeStyleSheet.create(styles) as T;
  return new Proxy(created, {
    get(target, property, receiver) {
      return resolveThemeValue(Reflect.get(target, property, receiver));
    },
  });
}

/**
 * Drop-in StyleSheet for legacy token-based screens. It resolves light-token
 * values to the active palette at render time while those screens migrate to
 * first-class design-system components.
 */
export const StyleSheet = new Proxy(NativeStyleSheet, {
  get(target, property, receiver) {
    return property === 'create' ? createThemedStyles : Reflect.get(target, property, receiver);
  },
}) as typeof NativeStyleSheet;
