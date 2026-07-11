import { shareBytes } from './fileSharing';

jest.mock('react-native', () => {
  const reactNative = jest.requireActual('react-native');
  Object.defineProperty(reactNative.Platform, 'OS', { configurable: true, value: 'web' });
  return reactNative;
});

jest.mock('expo-file-system/legacy', () => ({}));
jest.mock('expo-sharing', () => ({}));

describe('web file sharing', () => {
  const originalDocument = globalThis.document;
  const originalFile = globalThis.File;
  const originalNavigator = globalThis.navigator;
  const originalCreateObjectUrl = URL.createObjectURL;
  const originalRevokeObjectUrl = URL.revokeObjectURL;
  const click = jest.fn();

  beforeEach(() => {
    click.mockClear();
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: {
        body: { appendChild: jest.fn() },
        createElement: () => ({
          click,
          download: '',
          href: '',
          remove: jest.fn(),
          style: { display: '' },
        }),
      },
    });
    URL.createObjectURL = jest.fn(() => 'blob:invoice');
    URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    Object.defineProperty(globalThis, 'document', { configurable: true, value: originalDocument });
    Object.defineProperty(globalThis, 'File', { configurable: true, value: originalFile });
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator });
    URL.createObjectURL = originalCreateObjectUrl;
    URL.revokeObjectURL = originalRevokeObjectUrl;
  });

  it('downloads when the browser does not expose the File API', async () => {
    Object.defineProperty(globalThis, 'File', { configurable: true, value: undefined });
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} });

    await expect(
      shareBytes('invoice.pdf', new ArrayBuffer(4), 'application/pdf', 'Invoice'),
    ).resolves.toBe('downloaded');
    expect(click).toHaveBeenCalledTimes(1);
  });

  it('uses Web Share when file sharing is supported', async () => {
    class TestFile {}
    const share = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(globalThis, 'File', { configurable: true, value: TestFile });
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { canShare: jest.fn(() => true), share },
    });

    await expect(
      shareBytes('invoice.pdf', new ArrayBuffer(4), 'application/pdf', 'Invoice'),
    ).resolves.toBe('shared');
    expect(share).toHaveBeenCalledTimes(1);
    expect(click).not.toHaveBeenCalled();
  });
});
