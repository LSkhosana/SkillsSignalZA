import { Link } from 'expo-router';
import { Platform, StyleSheet, Text, View } from 'react-native';

import { BrandMark } from '@/components/system/brand-mark';
import { Routes } from '@/lib/routes';
import { FontFamily, Layout, Palette } from '@/theme/tokens';

const links = [
  { label: 'Privacy', href: Routes.privacy },
  { label: 'Terms', href: Routes.terms },
  { label: 'Refund policy', href: Routes.refunds },
  { label: 'Support', href: Routes.support },
] as const;

export function GlobalFooter() {
  return (
    <View {...(Platform.OS === 'web' ? { className: 'ss-footer' } : {})} style={styles.footer} testID="global-footer">
      <View style={styles.inner}>
        <View style={styles.brandBlock}>
          <View style={styles.brand}>
            <BrandMark size="sm" />
            <Text style={styles.wordmark}>SkillSignalZA</Text>
          </View>
          <Text style={styles.note}>
            Application evidence benchmark for entry-level Software Engineering and Data Analytics candidates in South
            Africa.
          </Text>
        </View>
        <View {...(Platform.OS === 'web' ? { className: 'ss-footer-links' } : {})} style={styles.links}>
          {links.map((link) => (
            <Link key={link.label} href={link.href} accessibilityRole="link" style={styles.link}>
              {link.label}
            </Link>
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  footer: {
    backgroundColor: Palette.ink,
    borderTopWidth: 1,
    borderTopColor: '#2F3632',
  },
  inner: {
    width: '100%',
    maxWidth: Layout.canvas,
    alignSelf: 'center',
    gap: 18,
    paddingVertical: 28,
    paddingHorizontal: 24,
  },
  brandBlock: {
    gap: 8,
    flexShrink: 1,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  wordmark: {
    color: Palette.surface,
    fontFamily: FontFamily.serif,
    fontSize: 22,
    letterSpacing: -0.4,
  },
  note: {
    maxWidth: 640,
    color: Palette.footerMuted,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    lineHeight: 18,
  },
  links: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  link: {
    minHeight: Layout.touch,
    justifyContent: 'center',
    paddingRight: 12,
    color: '#E0E5E2',
    fontFamily: FontFamily.sans,
    fontSize: 13,
    fontWeight: '700',
  },
});
