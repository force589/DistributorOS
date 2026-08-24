import {
  getModalBackgroundAccessibilityProps,
  getSettingsChangeState,
} from './changeState';

const current = {
  businessName: 'QA Business',
  currency: 'INR' as const,
  language: 'en' as const,
  themePreference: 'system' as const,
  timezone: 'Asia/Kolkata',
};

describe('settings dirty-state classification', () => {
  it('allows immediate theme changes without arming business dirty protection', () => {
    expect(
      getSettingsChangeState({
        current,
        draft: { ...current, themePreference: 'dark' },
      }),
    ).toEqual({
      hasBusinessProfileChanges: false,
      hasChanges: true,
      hasPresentationChanges: true,
    });
  });

  it('allows immediate language changes without arming business dirty protection', () => {
    expect(
      getSettingsChangeState({
        current,
        draft: { ...current, language: 'ml' },
      }),
    ).toEqual({
      hasBusinessProfileChanges: false,
      hasChanges: true,
      hasPresentationChanges: true,
    });
  });

  it('keeps genuine business/profile edits protected from accidental navigation', () => {
    expect(
      getSettingsChangeState({
        current,
        draft: { ...current, businessName: 'Unsaved QA Business' },
      }),
    ).toMatchObject({
      hasBusinessProfileChanges: true,
      hasChanges: true,
    });
  });

  it('hides Settings background controls from assistive tech when logout confirmation is open', () => {
    expect(getModalBackgroundAccessibilityProps(true)).toMatchObject({
      'aria-hidden': true,
      accessibilityElementsHidden: true,
      importantForAccessibility: 'no-hide-descendants',
    });
    expect(getModalBackgroundAccessibilityProps(false)).toMatchObject({
      accessibilityElementsHidden: false,
      importantForAccessibility: 'auto',
    });
  });
});
