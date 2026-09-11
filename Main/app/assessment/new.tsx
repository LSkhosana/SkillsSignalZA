import * as DocumentPicker from 'expo-document-picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AccountBar } from '@/components/account-bar';
import { ScreenShell } from '@/components/screen-shell';
import { StatusBanner } from '@/components/status-banner';
import { UiButton } from '@/components/ui-button';
import { UiTextField } from '@/components/ui-text-field';
import { useTheme } from '@/hooks/use-theme';
import {
  DECLARED_LINK_TYPES,
  LINK_TYPE_LABELS,
  MAX_LINKS,
  TRACK_OPTIONS,
  type DeclaredLinkType,
  type TrackId,
} from '@/lib/constants';
import { mediaTypeFromName, validatePickedCv } from '@/lib/cv';
import { toHref } from '@/lib/href';
import {
  customerMessageForCode,
  customerMessageFromError,
  submitAssessment,
  type CandidateLinkInput,
  type PickedCvDocument,
} from '@/services/api';
import { getAccessToken } from '@/services/auth';
import { continueAfterAuthentication, saveClaimToken, savePendingAssessment } from '@/services/flow';

type LinkDraft = {
  submitted_url: string;
  declared_type: DeclaredLinkType;
};

function isTrackId(value: unknown): value is TrackId {
  return value === 'software_engineering' || value === 'data_analytics';
}

export default function NewAssessmentScreen() {
  const theme = useTheme();
  const router = useRouter();
  const params = useLocalSearchParams<{ track?: string | string[] }>();
  const initialTrack = Array.isArray(params.track) ? params.track[0] : params.track;
  const [track, setTrack] = useState<TrackId>(isTrackId(initialTrack) ? initialTrack : 'software_engineering');
  const [cv, setCv] = useState<PickedCvDocument | null>(null);
  const [links, setLinks] = useState<LinkDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const trackLabel = useMemo(
    () => TRACK_OPTIONS.find((option) => option.id === track)?.label ?? track,
    [track],
  );

  async function pickCv() {
    setError(null);
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets[0]) {
      return;
    }
    const asset = result.assets[0];
    const picked: PickedCvDocument = {
      uri: asset.uri,
      name: asset.name ?? 'cv',
      mimeType: mediaTypeFromName(asset.name ?? 'cv', asset.mimeType),
      size: asset.size ?? null,
    };
    const validationError = validatePickedCv(picked);
    if (validationError) {
      setCv(null);
      setError(validationError);
      return;
    }
    setCv(picked);
  }

  function updateLink(index: number, patch: Partial<LinkDraft>) {
    setLinks((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  async function onSubmit() {
    setError(null);
    setInfo(null);
    if (!cv) {
      setError('Choose a PDF or DOCX CV before submitting.');
      return;
    }
    const validationError = validatePickedCv(cv);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (links.length > MAX_LINKS) {
      setError('You can add up to five links.');
      return;
    }
    const preparedLinks: CandidateLinkInput[] = [];
    for (const link of links) {
      const submitted_url = link.submitted_url.trim();
      if (!submitted_url) {
        continue;
      }
      preparedLinks.push({ submitted_url, declared_type: link.declared_type });
    }
    if (preparedLinks.length > MAX_LINKS) {
      setError('You can add up to five links.');
      return;
    }

    setBusy(true);
    setInfo('Assessing your CV and submitted links. This can take a short while.');
    try {
      const result = await submitAssessment({ track, cv, links: preparedLinks });
      if (!result.ok) {
        setError(customerMessageFromError(result.error, 'The assessment could not be submitted.'));
        return;
      }
      if (result.data.state === 'REVIEW_REQUIRED') {
        setError(customerMessageForCode('REVIEW_REQUIRED', 'This assessment needs review.'));
        return;
      }
      if (result.data.state !== 'COMPLETED' || !result.data.preview || !result.data.claim_token) {
        setError(
          customerMessageForCode(
            result.data.error_code ?? 'NOT_SCORABLE',
            'This submission could not produce a preview.',
          ),
        );
        return;
      }

      const assessmentId = result.data.assessment_id;
      await savePendingAssessment({
        assessment_id: assessmentId,
        preview: result.data.preview,
        claimed: false,
      });
      await saveClaimToken(assessmentId, result.data.claim_token);

      const accessToken = await getAccessToken();
      if (accessToken) {
        const claim = await continueAfterAuthentication(assessmentId, { accessToken });
        if (claim.status === 'blocked') {
          setError(claim.message);
          return;
        }
      }

      router.replace(toHref(`/assessment/${assessmentId}/preview`));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell
      title="New assessment"
      subtitle={`Track: ${trackLabel}`}
      headerRight={<AccountBar />}
      testID="assessment-form-screen"
    >
      <View style={styles.trackRow}>
        {TRACK_OPTIONS.map((option) => (
          <Pressable
            key={option.id}
            accessibilityRole="radio"
            accessibilityState={{ selected: option.id === track }}
            accessibilityLabel={option.label}
            disabled={busy}
            onPress={() => setTrack(option.id)}
            testID={`form-track-${option.id}`}
            style={[
              styles.trackChip,
              {
                borderColor: option.id === track ? theme.accent : theme.border,
                backgroundColor: theme.background,
              },
            ]}
          >
            <Text style={[styles.chipLabel, { color: theme.text }]}>{option.label}</Text>
          </Pressable>
        ))}
      </View>
      <UiButton
        label={cv ? 'Replace CV' : 'Choose CV (PDF or DOCX)'}
        variant="secondary"
        disabled={busy}
        testID="pick-cv"
        onPress={() => void pickCv()}
      />
      <Text style={[styles.body, { color: theme.textSecondary }]} testID="cv-filename">
        {cv ? `Selected file: ${cv.name}` : 'No CV selected yet.'}
      </Text>
      <Text style={[styles.section, { color: theme.text }]}>Optional links (up to {MAX_LINKS})</Text>
      {links.map((link, index) => (
        <View key={`link-${index}`} style={[styles.linkCard, { borderColor: theme.border }]}>
          <UiTextField
            label={`Link ${index + 1} URL`}
            value={link.submitted_url}
            onChangeText={(submitted_url) => updateLink(index, { submitted_url })}
            autoComplete="url"
            keyboardType="url"
            placeholder="https://"
            testID={`link-url-${index}`}
          />
          <Text style={[styles.body, { color: theme.text }]}>Declared type</Text>
          <View style={styles.trackRow}>
            {DECLARED_LINK_TYPES.map((type) => (
              <Pressable
                key={type}
                accessibilityRole="radio"
                accessibilityState={{ selected: link.declared_type === type }}
                accessibilityLabel={LINK_TYPE_LABELS[type]}
                disabled={busy}
                onPress={() => updateLink(index, { declared_type: type })}
                style={[
                  styles.typeChip,
                  {
                    borderColor: link.declared_type === type ? theme.accent : theme.border,
                  },
                ]}
              >
                <Text style={[styles.chipLabel, { color: theme.text }]}>{LINK_TYPE_LABELS[type]}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ))}
      {links.length < MAX_LINKS ? (
        <UiButton
          label="Add link"
          variant="secondary"
          disabled={busy}
          testID="add-link"
          onPress={() =>
            setLinks((current) => [...current, { submitted_url: '', declared_type: 'repository' }])
          }
        />
      ) : null}
      {error ? <StatusBanner tone="danger" title="Assessment could not continue" message={error} /> : null}
      {info && busy ? <StatusBanner title="Processing" message={info} testID="processing-state" /> : null}
      <UiButton
        label={busy ? 'Assessing…' : 'Submit assessment'}
        disabled={busy}
        testID="submit-assessment"
        onPress={() => void onSubmit()}
      />
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
  trackRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  trackChip: {
    borderWidth: 2,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  typeChip: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  chipLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  linkCard: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 12,
  },
});
