import { useCallback, useRef, useState } from 'react';

interface SingleFlightAction {
  pending: boolean;
  run: (action: () => Promise<void>) => Promise<boolean>;
}

export function useSingleFlightAction(): SingleFlightAction {
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);

  const run = useCallback(async (action: () => Promise<void>): Promise<boolean> => {
    if (inFlight.current) {
      return false;
    }
    inFlight.current = true;
    setPending(true);
    try {
      await action();
      return true;
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }, []);

  return { pending, run };
}

