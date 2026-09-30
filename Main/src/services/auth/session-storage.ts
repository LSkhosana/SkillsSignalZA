import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

export type AuthSessionStorage = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

/**
 * Persistent storage for the Supabase Auth session so sign-in survives reloads.
 * Native uses AsyncStorage. Web uses localStorage when available, otherwise AsyncStorage.
 */
export function createAuthSessionStorage(): AuthSessionStorage {
  if (Platform.OS === 'web' && typeof localStorage !== 'undefined') {
    return {
      getItem: async (key) => localStorage.getItem(key),
      setItem: async (key, value) => {
        localStorage.setItem(key, value);
      },
      removeItem: async (key) => {
        localStorage.removeItem(key);
      },
    };
  }

  return AsyncStorage;
}
