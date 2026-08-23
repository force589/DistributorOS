export function shouldShowGlobalSettingsButton(pathname: string): boolean {
  return pathname !== '/settings' && pathname !== '/more';
}
