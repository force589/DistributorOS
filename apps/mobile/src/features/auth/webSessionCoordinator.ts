import type { AuthResponse } from '@distributoros/api-client';

type SessionMessage =
  | { type: 'session'; sentAt: number; session: AuthResponse }
  | { type: 'logout'; sentAt: number };

type SessionListener = (message: SessionMessage) => void;
type LockManagerLike = {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>;
};

const channelName = 'distributoros.auth.session';
const lockName = 'distributoros.auth.refresh';
const listeners = new Set<SessionListener>();
let channel: BroadcastChannel | null = null;
let latestSessionMessage: Extract<SessionMessage, { type: 'session' }> | null = null;

function webChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') return null;
  if (!channel) {
    channel = new BroadcastChannel(channelName);
    channel.addEventListener('message', (event: MessageEvent<SessionMessage>) => {
      const message = event.data;
      if (!message || !['session', 'logout'].includes(message.type)) return;
      if (message.type === 'session') latestSessionMessage = message;
      else latestSessionMessage = null;
      listeners.forEach((listener) => listener(message));
    });
  }
  return channel;
}

export function publishWebSession(session: AuthResponse): void {
  const message: Extract<SessionMessage, { type: 'session' }> = {
    type: 'session',
    sentAt: Date.now(),
    session,
  };
  latestSessionMessage = message;
  webChannel()?.postMessage(message);
}

export function publishWebLogout(): void {
  latestSessionMessage = null;
  webChannel()?.postMessage({ type: 'logout', sentAt: Date.now() } satisfies SessionMessage);
}

export function subscribeToWebSession(listener: SessionListener): () => void {
  webChannel();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function coordinateWebRefresh(
  refresh: () => Promise<AuthResponse | null>,
): Promise<AuthResponse | null> {
  if (typeof navigator === 'undefined') return refresh();
  const requestedAt = Date.now();
  const locks = (navigator as Navigator & { locks?: LockManagerLike }).locks;
  if (!locks) {
    const session = await refresh();
    if (session) publishWebSession(session);
    return session;
  }
  return locks.request(lockName, async () => {
    if (latestSessionMessage && latestSessionMessage.sentAt >= requestedAt) {
      return latestSessionMessage.session;
    }
    const session = await refresh();
    if (session) publishWebSession(session);
    return session;
  });
}

export function resetWebSessionCoordinatorForTests(): void {
  listeners.clear();
  latestSessionMessage = null;
  channel?.close();
  channel = null;
}
