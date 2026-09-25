import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { SkeletonBlock } from '@/components/system/skeleton';
import { Routes } from '@/lib/routes';
import { useAuth } from '@/services/auth/provider';
import { FontFamily, Layout, Palette } from '@/theme/tokens';

export function maskAccountLabel(email: string | null | undefined) {
  if (!email) {
    return 'Account';
  }
  const [name, domain] = email.split('@');
  if (!name || !domain) {
    return 'Account';
  }
  return `${name.slice(0, 1)}•••@${domain}`;
}

const menuItems = [
  { label: 'My Reports', href: Routes.reports },
  { label: 'Start new assessment', href: Routes.assessmentNew },
  { label: 'Account', href: Routes.account },
] as const;

export function AccountMenu() {
  const auth = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  if (auth.status === 'loading') {
    return (
      <View accessibilityLabel="Checking session" accessibilityState={{ busy: true }} style={styles.loading}>
        <SkeletonBlock height={12} width={96} />
      </View>
    );
  }

  if (auth.status !== 'signed_in') {
    return (
      <Pressable
        accessibilityRole="link"
        accessibilityLabel="Sign in"
        onPress={() => router.push(Routes.signIn)}
        style={styles.signIn}
      >
        <Text style={styles.signInLabel}>Sign in</Text>
      </Pressable>
    );
  }

  const masked = maskAccountLabel(auth.user?.email);

  return (
    <View style={styles.wrap}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Account menu for ${masked}`}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((current) => !current)}
        style={styles.identity}
        testID="account-menu-trigger"
      >
        <Text style={styles.identityLabel}>{masked}</Text>
      </Pressable>
      {open ? (
        <View accessibilityRole="menu" style={styles.menu} testID="account-menu">
          {menuItems.map((item) => (
            <Pressable
              key={item.label}
              accessibilityRole="menuitem"
              onPress={() => {
                setOpen(false);
                router.push(item.href);
              }}
              style={styles.menuItem}
            >
              <Text style={styles.menuLabel}>{item.label}</Text>
            </Pressable>
          ))}
          <Pressable
            accessibilityRole="menuitem"
            accessibilityLabel="Sign out"
            onPress={() => {
              setOpen(false);
              void auth.signOut();
            }}
            style={styles.menuItem}
          >
            <Text style={styles.menuLabel}>Sign out</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  loading: {
    minHeight: Layout.touch,
    justifyContent: 'center',
    paddingHorizontal: 8,
  },
  signIn: {
    minHeight: Layout.touch,
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  signInLabel: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '800',
  },
  wrap: {
    position: 'relative',
    zIndex: 40,
  },
  identity: {
    minHeight: Layout.touch,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: Palette.ink,
    borderRadius: 0,
    backgroundColor: Palette.surface,
  },
  identityLabel: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '800',
  },
  menu: {
    position: 'absolute',
    top: '100%',
    right: 0,
    minWidth: 220,
    marginTop: 6,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.ink,
  },
  menuItem: {
    minHeight: Layout.touch,
    justifyContent: 'center',
    paddingHorizontal: 14,
    borderTopWidth: 1,
    borderTopColor: Palette.divider,
  },
  menuLabel: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 14,
    fontWeight: '700',
  },
});
