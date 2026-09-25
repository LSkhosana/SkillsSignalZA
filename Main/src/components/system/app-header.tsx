import { usePathname, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AccountMenu } from '@/components/system/account-menu';
import { BrandMark } from '@/components/system/brand-mark';
import { Button } from '@/components/system/button';
import { Routes } from '@/lib/routes';
import { FontFamily, Layout, Palette } from '@/theme/tokens';

function contextLabel(pathname: string) {
  if (pathname.startsWith('/assessment/new')) {
    return 'Assessment';
  }
  if (pathname.includes('/preview')) {
    return 'Preview';
  }
  if (pathname.includes('/payment')) {
    return 'Checkout';
  }
  if (pathname.includes('/report')) {
    return 'Report';
  }
  if (pathname.startsWith('/sign-in') || pathname.startsWith('/sign-up')) {
    return 'Account access';
  }
  if (pathname.startsWith('/dashboard')) {
    return 'Account';
  }
  return null;
}

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const marketing = pathname === '/';
  const compact = width < Layout.tablet;
  const context = marketing ? null : contextLabel(pathname);

  return (
    <View accessibilityRole="header" style={styles.header} testID="app-header">
      <View style={[styles.inner, compact ? styles.innerCompact : null]}>
        <Pressable
          accessibilityRole="link"
          accessibilityLabel="SkillSignalZA home"
          onPress={() => router.push(Routes.home)}
          style={styles.brand}
        >
          <BrandMark />
          <Text style={styles.brandText}>SkillSignalZA</Text>
        </Pressable>
        {context ? <Text style={styles.context}>{context}</Text> : null}
        <View style={styles.actions}>
          {marketing ? (
            <Button label="Career Map Pack" href={Routes.mapPack} variant="ghost" />
          ) : null}
          {marketing ? <Button label="Start assessment" href={Routes.assessmentNew} testID="header-start-assessment" /> : null}
          <AccountMenu />
        </View>
      </View>
    </View>
  );
}

export function MarketingHeader() {
  return <AppHeader />;
}

const styles = StyleSheet.create({
  header: {
    zIndex: 30,
    backgroundColor: 'rgba(255,255,255,0.92)',
    borderBottomWidth: 1,
    borderBottomColor: Palette.divider,
  },
  inner: {
    minHeight: Layout.header,
    width: '100%',
    maxWidth: Layout.canvas,
    alignSelf: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  innerCompact: {
    paddingHorizontal: 16,
  },
  brand: {
    minHeight: Layout.touch,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flexShrink: 1,
  },
  brandText: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  context: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
    letterSpacing: -0.4,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 12,
    marginLeft: 'auto',
  },
});
