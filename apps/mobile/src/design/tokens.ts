export const lightColors = {
  background: '#F7F8FA',
  surface: '#FFFFFF',
  surfaceElevated: '#FFFFFF',
  surfaceSubtle: '#EEF2F6',
  primary: '#155EEF',
  primaryPressed: '#004EEB',
  primarySubtle: '#EAF2FF',
  text: '#182230',
  textMuted: '#475467',
  textInverse: '#FFFFFF',
  border: '#D0D5DD',
  borderStrong: '#98A2B3',
  danger: '#B42318',
  dangerBackground: '#FEF3F2',
  warning: '#B54708',
  warningBackground: '#FFFAEB',
  success: '#067647',
  successBackground: '#ECFDF3',
  disabled: '#98A2B3',
  overlay: 'rgba(16, 24, 40, 0.55)',
} as const;

export const darkColors: ColorPalette = {
  background: '#0B1220',
  surface: '#111B2E',
  surfaceElevated: '#17233A',
  surfaceSubtle: '#1D2A42',
  primary: '#75A7FF',
  primaryPressed: '#9ABFFF',
  primarySubtle: '#172B4D',
  text: '#F2F4F7',
  textMuted: '#B7C0CE',
  textInverse: '#09111F',
  border: '#344054',
  borderStrong: '#667085',
  danger: '#FDA29B',
  dangerBackground: '#3A1D23',
  warning: '#FEC84B',
  warningBackground: '#352A13',
  success: '#75E0A7',
  successBackground: '#143326',
  disabled: '#667085',
  overlay: 'rgba(3, 7, 18, 0.76)',
};

export type ColorPalette = {
  [Key in keyof typeof lightColors]: string;
};

// Backward-compatible light palette for legacy styles while screens migrate to useTheme().
export const colors = lightColors;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  xxxl: 64,
} as const;

export const radii = {
  sm: 8,
  md: 12,
  lg: 20,
  xl: 28,
  full: 999,
} as const;

export const typography = {
  display: { fontSize: 36, lineHeight: 44, fontWeight: '800' as const },
  title: { fontSize: 28, lineHeight: 36, fontWeight: '800' as const },
  heading: { fontSize: 20, lineHeight: 28, fontWeight: '700' as const },
  body: { fontSize: 16, lineHeight: 24, fontWeight: '400' as const },
  label: { fontSize: 14, lineHeight: 20, fontWeight: '600' as const },
  caption: { fontSize: 12, lineHeight: 18, fontWeight: '500' as const },
} as const;

export const elevations = {
  none: {},
  sm: { boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)', elevation: 1 },
  md: { boxShadow: '0 3px 8px rgba(0, 0, 0, 0.12)', elevation: 3 },
  lg: { boxShadow: '0 6px 16px rgba(0, 0, 0, 0.16)', elevation: 6 },
} as const;

export const animation = {
  fast: 120,
  normal: 200,
  slow: 320,
} as const;

export const iconSizes = {
  sm: 16,
  md: 20,
  lg: 24,
  xl: 32,
} as const;

export const breakpoints = {
  phone: 0,
  tablet: 768,
  desktop: 1180,
} as const;
