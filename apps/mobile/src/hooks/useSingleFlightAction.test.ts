import { act, renderHook } from '@testing-library/react-native';

import { useSingleFlightAction } from './useSingleFlightAction';

describe('useSingleFlightAction', () => {
  it('suppresses a second action while the first is unresolved', async () => {
    let release: (() => void) | undefined;
    const action = jest.fn(
      () =>
        new Promise<void>((resolve) => {
          release = resolve;
        }),
    );
    const hook = await renderHook(() => useSingleFlightAction());

    let first: Promise<boolean> | undefined;
    let second: Promise<boolean> | undefined;
    await act(async () => {
      first = hook.result.current.run(action);
      second = hook.result.current.run(action);
      await second;
    });

    expect(await second).toBe(false);
    expect(action).toHaveBeenCalledTimes(1);

    await act(async () => {
      release?.();
      await first;
    });
    expect(await first).toBe(true);
  });
});

