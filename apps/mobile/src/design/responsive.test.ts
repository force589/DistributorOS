import { getResponsiveLayout } from './responsive';

describe('responsive layout', () => {
  it.each([
    [390, 844, true, false, false, 1],
    [844, 390, false, true, false, 2],
    [768, 1024, false, true, false, 2],
    [1180, 800, false, false, true, 3],
    [1440, 900, false, false, true, 3],
  ])(
    'classifies a %ix%i viewport',
    (width, height, isPhone, isTablet, isDesktop, columns) => {
      expect(getResponsiveLayout(width, height)).toMatchObject({
        isPhone,
        isTablet,
        isDesktop,
        isLandscape: width > height,
        columns,
        quickActionColumns: isDesktop ? 4 : isTablet ? 3 : 2,
      });
    },
  );
});
