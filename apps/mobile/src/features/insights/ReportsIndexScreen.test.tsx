import '@/localization/i18n';

import { fireEvent, render } from '@testing-library/react-native';

import ReportsIndexScreen from '../../../app/(app)/reports';

const mockPush = jest.fn();
const mockDismissTo = jest.fn();

jest.setTimeout(15000);

jest.mock('expo-router', () => ({
  useRouter: () => ({
    dismissTo: mockDismissTo,
    push: mockPush,
  }),
}));

jest.mock('@/navigation/UnsavedChangesContext', () => ({
  useUnsavedChanges: () => ({
    guardNavigation: (action: () => void) => action(),
  }),
}));

jest.mock('@/design/responsive', () => ({
  useResponsiveLayout: () => ({
    contentMaxWidth: 680,
    isDesktop: false,
    isPhone: true,
    isTablet: false,
    quickActionColumns: 2,
  }),
}));

describe('reports index production navigation', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockDismissTo.mockClear();
  });

  it('uses production wording and material-style report rows', async () => {
    const screen = await render(<ReportsIndexScreen />);

    expect(screen.queryByText('Phase 8 reports are read-only')).toBeNull();
    expect(screen.getByText('Reports are read-only summaries')).toBeTruthy();

    fireEvent.press(screen.getByRole('button', { name: 'Sales Report' }));

    expect(mockPush).toHaveBeenCalledWith('/reports/sales');
  });
});
