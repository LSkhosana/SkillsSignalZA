import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export type SecretStore = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

const WEB_SESSION_PREFIX = 'ssza.claim.token.';

function webSessionStore(): SecretStore {
  return {
    getItem: async (key) => {
      if (typeof sessionStorage === 'undefined') {
        return null;
      }
      return sessionStorage.getItem(key);
    },
    setItem: async (key, value) => {
      if (typeof sessionStorage === 'undefined') {
        return;
      }
      sessionStorage.setItem(key, value);
    },
    removeItem: async (key) => {
      if (typeof sessionStorage === 'undefined') {
        return;
      }
      sessionStorage.removeItem(key);
    },
  };
}

function nativeSecureStore(): SecretStore {
  return {
    getItem: (key) => SecureStore.getItemAsync(key),
    setItem: (key, value) => SecureStore.setItemAsync(key, value),
    removeItem: (key) => SecureStore.deleteItemAsync(key),
  };
}

let store: SecretStore = Platform.OS === 'web' ? webSessionStore() : nativeSecureStore();

export function setClaimTokenStoreForTests(next: SecretStore | null): void {
  store = next ?? (Platform.OS === 'web' ? webSessionStore() : nativeSecureStore());
}

export function claimTokenStorageKey(assessmentId: string): string {
  return `${WEB_SESSION_PREFIX}${assessmentId}`;
}

export async function saveClaimToken(assessmentId: string, claimToken: string): Promise<void> {
  await store.setItem(claimTokenStorageKey(assessmentId), claimToken);
}

export async function loadClaimToken(assessmentId: string): Promise<string | null> {
  return store.getItem(claimTokenStorageKey(assessmentId));
}

export async function deleteClaimToken(assessmentId: string): Promise<void> {
  await store.removeItem(claimTokenStorageKey(assessmentId));
}
