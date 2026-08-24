import { fireEvent, render } from '@testing-library/react-native';

import { appIcons } from '@/design/icons';
import {
  ActionCard,
  BottomNavigation,
  FilterChipGroup,
  HeadingText,
  Icon,
  IconButton,
  ListSkeleton,
  NavigationListItem,
  SectionHeader,
} from '@/design-system';

describe('commercial navigation controls', () => {
  it('exposes a persistent, accessible selected bottom-navigation destination', async () => {
    const openSales = jest.fn();
    const screen = await render(
      <BottomNavigation
        items={[
          { icon: appIcons.home, key: 'home', label: 'Home', onPress: jest.fn(), selected: true },
          { icon: appIcons.sales, key: 'sales', label: 'Sales', onPress: openSales },
          { icon: appIcons.customers, key: 'customers', label: 'Customers', onPress: jest.fn() },
          { icon: appIcons.products, key: 'products', label: 'Products', onPress: jest.fn() },
          { icon: appIcons.more, key: 'more', label: 'More', onPress: jest.fn() },
        ]}
      />,
    );

    expect(screen.getByRole('tab', { name: 'Home' }).props.accessibilityState).toEqual({
      selected: true,
    });
    fireEvent.press(screen.getByRole('tab', { name: 'Sales' }));

    expect(openSales).toHaveBeenCalledTimes(1);
  });

  it('opens a dashboard quick action with one press', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <ActionCard
        description="Create, review, and post sales."
        icon={appIcons.sales}
        onPress={onPress}
        title="Sales"
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Sales' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('renders More destinations as labelled material-style rows', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <NavigationListItem
        icon={appIcons.reports}
        onPress={onPress}
        subtitle="Open read-only business reports and exports."
        title="Reports"
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Reports' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('hides decorative vector icons from accessibility consumers', async () => {
    const screen = await render(<Icon name={appIcons.reports} />);
    const [iconProps] = findProps(
      screen.toJSON(),
      (props) => props.accessible === false,
    );

    expect(iconProps?.accessible).toBe(false);
    expect(iconProps?.accessibilityElementsHidden).toBe(true);
    expect(iconProps?.importantForAccessibility).toBe('no-hide-descendants');
  });

  it('requires an accessible label for icon-only actions', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <IconButton
        accessibilityLabel="Open settings"
        icon={appIcons.settings}
        onPress={onPress}
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Open settings' }));

    expect(onPress).toHaveBeenCalledTimes(1);
    expect(findProps(screen.toJSON(), (props) => props['aria-hidden'] === true).length).toBeGreaterThan(0);
  });

  it('gives reusable section headings explicit hierarchy levels', async () => {
    const screen = await render(<SectionHeader title="Recent Sales" />);
    const heading = screen.getByRole('header', { name: 'Recent Sales' });

    expect(heading.props['aria-level']).toBe(2);
  });

  it('allows explicit primary screen headings', async () => {
    const screen = await render(
      <HeadingText level={1}>
        Dashboard
      </HeadingText>,
    );

    expect(screen.getByRole('header', { name: 'Dashboard' }).props['aria-level']).toBe(1);
  });

  it('renders compact filter chips with an accessible selected state', async () => {
    const onSelect = jest.fn();
    const screen = await render(
      <FilterChipGroup
        label="Status"
        onSelect={onSelect}
        options={[
          { label: 'All', value: 'all' },
          { label: 'Archived', value: 'archived' },
        ]}
        selected="all"
        testIDPrefix="status"
      />,
    );

    expect(screen.getByRole('button', { name: 'All' }).props.accessibilityState).toEqual({
      selected: true,
    });
    fireEvent.press(screen.getByRole('button', { name: 'Archived' }));

    expect(onSelect).toHaveBeenCalledWith('archived');
  });

  it('announces one list-level skeleton instead of every decorative row', async () => {
    const screen = await render(<ListSkeleton accessibilityLabel="Loading customers" rows={3} />);

    expect(screen.getByRole('progressbar', { name: 'Loading customers' })).toBeTruthy();
    expect(findProps(screen.toJSON(), (props) => props['aria-hidden'] === true).length).toBeGreaterThan(0);
  });
});

function findProps(node: unknown, predicate: (props: Record<string, unknown>) => boolean): Record<string, unknown>[] {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap((child) => findProps(child, predicate));
  const props = 'props' in node && node.props && typeof node.props === 'object'
    ? node.props as Record<string, unknown>
    : {};
  const children = 'children' in node ? node.children : undefined;
  return [
    ...(predicate(props) ? [props] : []),
    ...findProps(children, predicate),
  ];
}
