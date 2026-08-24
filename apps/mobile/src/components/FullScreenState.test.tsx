import '@/localization/i18n';

import { render } from '@testing-library/react-native';

import { SessionRestoreShell } from './FullScreenState';

describe('SessionRestoreShell', () => {
  it('shows non-sensitive application chrome while session restoration is pending', async () => {
    const screen = await render(
      <SessionRestoreShell
        message="DistributorOS is securely restoring your account."
        title="Checking your session"
      />,
    );

    expect(screen.getByRole('header', { name: 'DistributorOS' })).toBeTruthy();
    expect(screen.getByText('Checking your session')).toBeTruthy();
    expect(screen.getByText('DistributorOS is securely restoring your account.')).toBeTruthy();
    expect(screen.queryByText('Welcome back')).toBeNull();
    expect(screen.queryByText('Quick Actions')).toBeNull();
  });
});
