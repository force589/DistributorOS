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
        confirmAccessibilityLabel="Confirm Sign Out"
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

    await fireEvent.press(screen.getByRole('button', { name: 'Confirm Sign Out' }));
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it('marks the confirmation surface as modal dialog content', async () => {
    const screen = await render(
      <ConfirmationDialog
        cancelLabel="Cancel"
        confirmAccessibilityLabel="Confirm Sign Out"
        confirmLabel="Sign Out"
        loadingLabel="Signing Out…"
        message="Are you sure you want to sign out?"
        onCancel={jest.fn()}
        onConfirm={jest.fn()}
        title="Sign out of DistributorOS?"
        visible
      />,
    );

    expect(findProps(screen.toJSON(), (props) => props.role === 'dialog')).toHaveLength(1);
    expect(
      findProps(screen.toJSON(), (props) => props['aria-modal'] === true),
    ).toHaveLength(1);
  });
});

function findProps(
  node: unknown,
  predicate: (props: Record<string, unknown>) => boolean,
): Record<string, unknown>[] {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap((child) => findProps(child, predicate));
  const props =
    'props' in node && node.props && typeof node.props === 'object'
      ? (node.props as Record<string, unknown>)
      : {};
  const children = 'children' in node ? node.children : undefined;
  return [
    ...(predicate(props) ? [props] : []),
    ...findProps(children, predicate),
  ];
}
