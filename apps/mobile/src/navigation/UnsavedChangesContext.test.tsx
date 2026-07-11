import '@/localization/i18n';

import { act, fireEvent, render } from '@testing-library/react-native';
import { Pressable, Text } from 'react-native';

import {
  UnsavedChangesProvider,
  useDirtyFormGuard,
} from './UnsavedChangesContext';

const mockDispatch = jest.fn();
const mockPreventRemove = jest.fn();

jest.mock('expo-router', () => {
  const React = jest.requireActual('react');
  return {
    useFocusEffect: (callback: () => void | (() => void)) => React.useEffect(callback, [callback]),
    useNavigation: () => ({ dispatch: mockDispatch, setOptions: jest.fn() }),
    useRouter: () => ({ back: jest.fn() }),
  };
});
jest.mock('expo-router/react-navigation', () => ({
  usePreventRemove: (prevent: boolean, callback: unknown) =>
    mockPreventRemove(prevent, callback),
}));

function DirtyHarness({ onSaved }: { onSaved: () => void }) {
  const leaveAfterSave = useDirtyFormGuard(true);
  return (
    <Pressable accessibilityRole="button" onPress={() => leaveAfterSave(onSaved)}>
      <Text>Complete Save</Text>
    </Pressable>
  );
}

describe('unsaved changes navigation protection', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockDispatch.mockClear();
    mockPreventRemove.mockClear();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('guards router and browser history removal actions', async () => {
    const screen = await render(
      <UnsavedChangesProvider>
        <DirtyHarness onSaved={jest.fn()} />
      </UnsavedChangesProvider>,
    );
    const preventCallback = mockPreventRemove.mock.calls.at(-1)?.[1] as (
      event: { data: { action: { type: string } } },
    ) => void;

    await act(async () => {
      preventCallback({ data: { action: { type: 'GO_BACK' } } });
    });
    expect(screen.getByText('Discard unsaved changes?')).toBeTruthy();

    await fireEvent.press(screen.getByRole('button', { name: 'Discard Changes' }));
    jest.runOnlyPendingTimers();
    expect(mockDispatch).toHaveBeenCalledWith({ type: 'GO_BACK' });
  });

  it('allows a successful save redirect without a discard dialog', async () => {
    const onSaved = jest.fn();
    const screen = await render(
      <UnsavedChangesProvider>
        <DirtyHarness onSaved={onSaved} />
      </UnsavedChangesProvider>,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Complete Save' }));
    jest.runOnlyPendingTimers();

    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Discard unsaved changes?')).toBeNull();
  });
});
