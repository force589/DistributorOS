import { shouldShowGlobalSettingsButton } from '@/navigation/settingsVisibility';

describe('global Settings access visibility', () => {
  it('keeps the global Settings button on ordinary screens', () => {
    expect(shouldShowGlobalSettingsButton('/customers')).toBe(true);
  });

  it('does not duplicate Settings access on the More screen', () => {
    expect(shouldShowGlobalSettingsButton('/more')).toBe(false);
  });

  it('hides the global Settings button while already on Settings', () => {
    expect(shouldShowGlobalSettingsButton('/settings')).toBe(false);
  });
});
