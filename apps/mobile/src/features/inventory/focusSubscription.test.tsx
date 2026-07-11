import '@/localization/i18n';

import { useInfiniteQuery } from '@tanstack/react-query';
import { render } from '@testing-library/react-native';

import InventoryListScreen from '../../../app/(app)/inventory';

const mockUseIsFocused = jest.fn();

jest.mock('expo-router', () => ({
  useIsFocused: () => mockUseIsFocused(),
  useRouter: () => ({ dismissTo: jest.fn(), push: jest.fn() }),
}));
jest.mock('@tanstack/react-query', () => ({
  keepPreviousData: undefined,
  useInfiniteQuery: jest.fn(),
}));

describe('inventory query focus subscription', () => {
  beforeEach(() => {
    jest.mocked(useInfiniteQuery).mockReturnValue({
      isPending: true,
    } as unknown as ReturnType<typeof useInfiniteQuery>);
  });

  it.each([false, true])('subscribes only when the inventory screen focus is %s', async (focused) => {
    mockUseIsFocused.mockReturnValue(focused);

    await render(<InventoryListScreen />);

    expect(useInfiniteQuery).toHaveBeenCalledWith(
      expect.objectContaining({ subscribed: focused }),
    );
  });
});
