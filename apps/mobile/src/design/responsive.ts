import { useWindowDimensions } from 'react-native';

import { breakpoints } from './tokens';

export function getResponsiveLayout(width: number, height: number) {
  const isDesktop = width >= breakpoints.desktop;
  const isTablet = width >= breakpoints.tablet && !isDesktop;
  return {
    width,
    height,
    isPhone: !isTablet && !isDesktop,
    isTablet,
    isDesktop,
    isLandscape: width > height,
    contentMaxWidth: isDesktop ? 1180 : isTablet ? 920 : 680,
    columns: isDesktop ? 3 : isTablet ? 2 : 1,
    quickActionColumns: isDesktop ? 4 : isTablet ? 3 : 2,
  } as const;
}

export function useResponsiveLayout() {
  const { width, height } = useWindowDimensions();
  return getResponsiveLayout(width, height);
}
