import { fireEvent, render } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import { ConfirmationDialog } from './ConfirmationDialog';

jest.mock('react-native/Libraries/Modal/Modal', () => ({
  __esModule: true,
  default: ({ children, visible }: { children: ReactNode; visible: boolean }) =>
    visible ? children : null,
}));

describe('ConfirmationDialog', () => {
  it('requires explicit confirmation before a destructive action', async () => {
    const cancel = jest.fn();
    const confirm = jest.fn();
    const screen = await render(
      <ConfirmationDialog
        cancelLabel="Cancel"
        confirmLabel="Sign Out"
        loadingLabel="Signing Out…"
        message="Are you sure you want to sign out?"
        onCancel={cancel}
        onConfirm={confirm}
        title="Sign out of DistributorOS?"
        visible
      />,
    );

    await fireEvent.press(screen.getByText('Cancel'));
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(confirm).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByText('Sign Out'));
    expect(confirm).toHaveBeenCalledTimes(1);
  });
});
