import { Platform, StyleSheet, View } from 'react-native';

import { Palette } from '@/theme/tokens';

type BrandMarkProps = {
  size?: 'sm' | 'md';
};

export function BrandMark({ size = 'md' }: BrandMarkProps) {
  if (Platform.OS === 'web') {
    return (
      <span className="ss-brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    );
  }

  const barWidth = size === 'sm' ? 6 : 8;
  const barHeight = size === 'sm' ? 22 : 27;

  return (
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.mark}>
      {[Palette.green, Palette.greenMid, Palette.greenSoft].map((color) => (
        <View key={color} style={[styles.bar, { width: barWidth, height: barHeight, backgroundColor: color }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  mark: {
    width: 30,
    height: 32,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 3,
    transform: [{ rotate: '-7deg' }],
  },
  bar: {
    alignSelf: 'flex-end',
  },
});
