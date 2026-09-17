import { useRouter } from 'expo-router';
import type { Href } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AccountBar } from '@/components/account-bar';
import { ScreenShell } from '@/components/screen-shell';
import { UiButton } from '@/components/ui-button';
import { useTheme } from '@/hooks/use-theme';
import { REPORT_PRICE_COPY, TRACK_OPTIONS, type TrackId } from '@/lib/constants';

export default function LandingScreen() {
  const theme = useTheme();
  const router = useRouter();
  const [track, setTrack] = useState<TrackId>('software_engineering');

  return (
    <ScreenShell
      title="SkillSignalZA"
      subtitle="Evaluate demonstrated application-readiness evidence from a CV and candidate-provided links."
      headerRight={<AccountBar />}
      testID="landing-screen"
    >
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        SkillSignalZA reviews the evidence you submit. It does not estimate hiring probability, guarantee
        interviews, measure hidden capability, or make AI hiring decisions.
      </Text>
      <Text style={[styles.section, { color: theme.text }]}>Choose a track</Text>
      {TRACK_OPTIONS.map((option) => {
        const selected = option.id === track;
        return (
          <Pressable
            key={option.id}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={option.label}
            onPress={() => setTrack(option.id)}
            testID={`track-${option.id}`}
            style={[
              styles.track,
              {
                borderColor: selected ? theme.accent : theme.border,
                backgroundColor: theme.background,
              },
            ]}
          >
            <Text style={[styles.trackLabel, { color: theme.text }]}>
              {selected ? 'Selected: ' : ''}
              {option.label}
            </Text>
            <Text style={[styles.body, { color: theme.textSecondary }]}>{option.description}</Text>
          </Pressable>
        );
      })}
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        The free preview is included with your assessment. The full Readiness Report costs {REPORT_PRICE_COPY}{' '}
        once.
      </Text>
      <View>
        <UiButton
          label="Start assessment"
          testID="start-assessment"
          onPress={() =>
            router.push({
              pathname: '/assessment/new',
              params: { track },
            } as unknown as Href)
          }
        />
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  body: {
    fontSize: 16,
    lineHeight: 24,
  },
  section: {
    fontSize: 18,
    fontWeight: '700',
  },
  track: {
    borderWidth: 2,
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  trackLabel: {
    fontSize: 16,
    fontWeight: '700',
  },
});
