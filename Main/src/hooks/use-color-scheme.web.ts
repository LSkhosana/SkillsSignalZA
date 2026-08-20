import { useSyncExternalStore } from 'react';
import { useColorScheme as useRNColorScheme } from 'react-native';

function subscribe() {
  return () => undefined;
}

/**
 * Static web rendering needs a stable first paint, then the real scheme.
 */
export function useColorScheme() {
  const isHydrated = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const colorScheme = useRNColorScheme();

  if (!isHydrated) {
    return 'light';
  }

  return colorScheme;
}
