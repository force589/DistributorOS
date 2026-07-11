import { fireEvent, render } from '@testing-library/react-native';

import { RadioListItem } from '@/design-system';

import { SettingsButton } from './SettingsButton';

describe('Settings navigation controls', () => {
  it('exposes the global gear as a labelled one-tap button', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <SettingsButton
        hint="Open business, appearance, language, and account settings."
        label="Settings"
        onPress={onPress}
      />,
    );

    fireEvent.press(screen.getByLabelText('Settings'));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('announces and changes a selected settings option', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <RadioListItem
        description="Always use the dark color theme."
        label="Dark"
        onPress={onPress}
        selected
      />,
    );
    const option = screen.getByRole('radio', { name: 'Dark' });

    expect(option.props.accessibilityState).toEqual({ checked: true });
    fireEvent.press(option);

    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
