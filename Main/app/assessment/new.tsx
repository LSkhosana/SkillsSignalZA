import * as DocumentPicker from 'expo-document-picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { PageShell } from '@/components/system/page-shell';
import { SectionHeader } from '@/components/system/section-header';
import { Button } from '@/components/system/button';
import { PageState, StatusPanel } from '@/components/system/feedback';
import { SelectField, UploadDropzone, UrlField } from '@/components/system/fields';
import { Badge, WorkspacePanel } from '@/components/system/surfaces';
import { WorkspaceShell } from '@/components/system/workspace-shell';
import {
  dispositionForOutcome,
  editingAllowed,
  paymentAllowedForDisposition,
  submissionAllowed,
  type WorkspacePhase,
} from '@/lib/assessment-workspace';
import {
  DECLARED_LINK_TYPES,
  LINK_TYPE_LABELS,
  MAX_LINKS,
  REPORT_PRICE_COPY,
  TRACK_OPTIONS,
  type DeclaredLinkType,
  type TrackId,
} from '@/lib/constants';
import { mediaTypeFromName, validatePickedCv } from '@/lib/cv';
import { validateEvidenceUrl } from '@/lib/evidence-url';
import { toHref } from '@/lib/href';
import { Routes } from '@/lib/routes';
import {
  customerMessageFromError,
  submitAssessment,
  toApiError,
  type CandidateLinkInput,
  type PickedCvDocument,
} from '@/services/api';
import { getAccessToken } from '@/services/auth';
import { continueAfterAuthentication, saveClaimToken, savePendingAssessment } from '@/services/flow';
import { FontFamily, Palette } from '@/theme/tokens';

type LinkDraft = {
  submitted_url: string;
  declared_type: DeclaredLinkType;
};

type Recovery = {
  phase: Extract<WorkspacePhase, 'review_required' | 'not_scorable' | 'service_failure'>;
  message: string;
};

function isTrackId(value: unknown): value is TrackId {
  return value === 'software_engineering' || value === 'data_analytics';
}

export default function NewAssessmentScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ track?: string | string[] }>();
  const initialTrack = Array.isArray(params.track) ? params.track[0] : params.track;
  const [track, setTrack] = useState<TrackId>(isTrackId(initialTrack) ? initialTrack : 'software_engineering');
  const [cv, setCv] = useState<PickedCvDocument | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);
  const [links, setLinks] = useState<LinkDraft[]>([]);
  const [phase, setPhase] = useState<WorkspacePhase>('draft');
  const [recovery, setRecovery] = useState<Recovery | null>(null);
  const inFlight = useRef(false);

  const trackLabel = useMemo(
    () => TRACK_OPTIONS.find((option) => option.id === track)?.label ?? track,
    [track],
  );
  const linkErrors = links.map((link) => validateEvidenceUrl(link.submitted_url));
  const linksValid = linkErrors.every((error) => error === null) && links.length <= MAX_LINKS;
  const cvValid = Boolean(cv) && validatePickedCv(cv as PickedCvDocument) === null && cvError === null;
  const ready = cvValid && linksValid;
  const editable = editingAllowed(phase);
  const canSubmit = submissionAllowed(phase, phase === 'submitting', ready);
  const evidenceCount = links.filter((link) => link.submitted_url.trim().length > 0).length;

  async function pickCv() {
    if (!editable) {
      return;
    }
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
      setCvError(validationError);
      return;
    }
    setCvError(null);
    setCv(picked);
  }

  function updateLink(index: number, patch: Partial<LinkDraft>) {
    if (!editable) {
      return;
    }
    setLinks((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function returnToDraft() {
    if (inFlight.current) {
      return;
    }
    setRecovery(null);
    setPhase('draft');
  }

  async function onSubmit() {
    if (inFlight.current || !submissionAllowed(phase, inFlight.current, ready) || !cv) {
      return;
    }
    const validationError = validatePickedCv(cv);
    if (validationError || linkErrors.some((error) => error !== null)) {
      setCvError(validationError);
      return;
    }

    const preparedLinks: CandidateLinkInput[] = [];
    for (const link of links) {
      const submitted_url = link.submitted_url.trim();
      if (!submitted_url) {
        continue;
      }
      if (validateEvidenceUrl(submitted_url)) {
        return;
      }
      preparedLinks.push({ submitted_url, declared_type: link.declared_type });
    }

    inFlight.current = true;
    setRecovery(null);
    setPhase('submitting');
    try {
      const result = await submitAssessment({ track, cv, links: preparedLinks });
      if (!result.ok) {
        const code = result.error.code;
        if (code === 'REVIEW_REQUIRED' || code === 'NOT_SCORABLE') {
          const disposition = dispositionForOutcome({
            schema_version: 'anonymous.assessment.v1',
            state: code,
            assessment_id: '',
            run_id: '',
            access_state: null,
            claim_token: null,
            preview: null,
            error_code: code,
          });
          if (disposition.type === 'review_required' || disposition.type === 'not_scorable') {
            setRecovery({ phase: disposition.type, message: disposition.message });
            setPhase(disposition.type);
          }
        } else {
          setRecovery({
            phase: 'service_failure',
            message: customerMessageFromError(result.error, 'The assessment could not be submitted.'),
          });
          setPhase('service_failure');
        }
        return;
      }

      const disposition = dispositionForOutcome(result.data);
      if (
        disposition.type !== 'preview' ||
        !paymentAllowedForDisposition(disposition.type) ||
        !result.data.preview ||
        !result.data.claim_token
      ) {
        if (disposition.type === 'review_required' || disposition.type === 'not_scorable' || disposition.type === 'service_failure') {
          setRecovery({ phase: disposition.type, message: disposition.message });
          setPhase(disposition.type);
        }
        return;
      }

      const assessmentId = result.data.assessment_id;
      const preview = result.data.preview;
      const claimToken = result.data.claim_token;
      await savePendingAssessment({
        assessment_id: assessmentId,
        preview,
        claimed: false,
      });
      await saveClaimToken(assessmentId, claimToken);

      const accessToken = await getAccessToken();
      if (accessToken) {
        const claim = await continueAfterAuthentication(assessmentId, { accessToken });
        if (claim.status === 'blocked') {
          setRecovery({ phase: 'service_failure', message: claim.message });
          setPhase('service_failure');
          return;
        }
      }

      router.replace(toHref(`/assessment/${assessmentId}/preview`));
    } catch (caught) {
      setRecovery({
        phase: 'service_failure',
        message: customerMessageFromError(toApiError(caught), 'The assessment could not be submitted.'),
      });
      setPhase('service_failure');
    } finally {
      inFlight.current = false;
    }
  }

  const cvState = cvError ? 'Needs a PDF or DOCX under 10 MB' : cv ? cv.name : 'No CV selected yet.';

  return (
    <PageShell testID="assessment-form-screen">
      <SectionHeader
        eyebrow="Assessment"
        title="New assessment"
        subtitle={`Track: ${trackLabel}`}
      />
      <WorkspaceShell
        testID="assessment-workspace"
        rail={
          <WorkspacePanel testID="assessment-rail">
            <Text style={styles.eyebrow}>Context</Text>
            <Text style={styles.railLabel}>Selected track</Text>
            <Text style={styles.railValue}>{trackLabel}</Text>
            <Text style={styles.railLabel}>CV</Text>
            <Text style={styles.railValue} testID="cv-filename">
              {cvState}
            </Text>
            <Text style={styles.railLabel}>Evidence links</Text>
            <Text style={styles.railValue} testID="evidence-count">
              {evidenceCount} of {MAX_LINKS}
            </Text>
            <Text style={styles.railLabel}>Assessment scope</Text>
            <Text style={styles.railBody}>
              SkillSignalZA reads the CV and any public links against the selected track.
            </Text>
            <Text style={styles.railLabel}>Free preview</Text>
            <Text style={styles.railBody}>
              The next result is a free preview of score, band and track. The full report is {REPORT_PRICE_COPY} and
              stays locked until payment.
            </Text>
          </WorkspacePanel>
        }
      >
        {phase === 'submitting' ? (
          <StatusPanel
            title="Reading the submission"
            message="The assessment is in progress. The workspace stays in place, and nothing can be edited or submitted again until this finishes. Nothing has been charged."
            testID="processing-state"
          />
        ) : null}

        <WorkspacePanel testID="step-track">
          <Text accessibilityRole="header" style={styles.stepTitle}>
            01 Target track
          </Text>
          <Text style={styles.stepBody}>Choose the role family this assessment should read.</Text>
          <SelectField
            label="Target track"
            value={track}
            disabled={!editable}
            options={TRACK_OPTIONS.map((option) => ({
              value: option.id,
              label: option.label,
              description: option.description,
            }))}
            onChange={setTrack}
            testID="form-track"
          />
        </WorkspacePanel>

        <WorkspacePanel testID="step-cv">
          <Text accessibilityRole="header" style={styles.stepTitle}>
            02 CV upload
          </Text>
          <Text style={styles.stepBody}>A PDF or DOCX CV is required. The file must be 10 MB or smaller.</Text>
          <UploadDropzone
            label={cv ? 'Replace CV' : 'Choose CV (PDF or DOCX)'}
            hint="PDF or DOCX, 10 MB or smaller."
            fileName={cv?.name}
            disabled={!editable}
            error={cvError ?? undefined}
            onPress={() => void pickCv()}
            testID="pick-cv"
          />
          <Button label="Privacy notice" variant="ghost" href={Routes.privacy} />
        </WorkspacePanel>

        <WorkspacePanel testID="step-evidence">
          <Text accessibilityRole="header" style={styles.stepTitle}>
            03 Supporting evidence
          </Text>
          <Text style={styles.stepBody}>
            Optional. Public links can strengthen verifiability. They do not promise a higher score.
          </Text>
          <Badge label="Optional" />
          {links.map((link, index) => (
            <View key={`link-${index}`} style={styles.linkRow}>
              <UrlField
                label={`Link ${index + 1} URL`}
                value={link.submitted_url}
                editable={editable}
                error={linkErrors[index] ?? undefined}
                onChangeText={(submitted_url) => updateLink(index, { submitted_url })}
                placeholder="https://"
                testID={`link-url-${index}`}
              />
              <SelectField
                label="Declared type"
                value={link.declared_type}
                disabled={!editable}
                options={DECLARED_LINK_TYPES.map((type) => ({ value: type, label: LINK_TYPE_LABELS[type] }))}
                onChange={(declared_type) => updateLink(index, { declared_type })}
                testID={`link-type-${index}`}
              />
              <Button
                label="Remove link"
                variant="ghost"
                disabled={!editable}
                testID={`remove-link-${index}`}
                onPress={() => setLinks((current) => current.filter((_, itemIndex) => itemIndex !== index))}
              />
            </View>
          ))}
          {links.length < MAX_LINKS ? (
            <Button
              label="Add link"
              variant="secondary"
              disabled={!editable}
              testID="add-link"
              onPress={() =>
                setLinks((current) => [...current, { submitted_url: '', declared_type: 'repository' }])
              }
            />
          ) : null}
        </WorkspacePanel>

        <WorkspacePanel testID="step-ready">
          <Text accessibilityRole="header" style={styles.stepTitle}>
            04 Ready to assess
          </Text>
          <Text style={styles.stepBody}>
            {trackLabel}. {cv ? cv.name : 'No CV selected yet.'} {evidenceCount} public{' '}
            {evidenceCount === 1 ? 'link' : 'links'}.
          </Text>
          {recovery?.phase === 'review_required' ? (
            <PageState
              tone="warning"
              happened={recovery.message}
              meaning="This submission is paused for review. A full report cannot be unlocked from this result."
              consequence="Nothing was charged. The preview was not opened."
              testID="outcome-review-required"
              action={<Button label="Prepare another submission" onPress={returnToDraft} testID="reset-assessment" />}
            />
          ) : null}
          {recovery?.phase === 'not_scorable' ? (
            <PageState
              tone="warning"
              happened={recovery.message}
              meaning="This CV did not produce a score. Replace it with a clearer PDF or DOCX before trying again."
              consequence="Nothing was charged and no report was unlocked."
              testID="outcome-not-scorable"
              action={<Button label="Revise submission" onPress={returnToDraft} testID="reset-assessment" />}
            />
          ) : null}
          {recovery?.phase === 'service_failure' ? (
            <PageState
              tone="danger"
              happened={recovery.message}
              meaning="The assessment did not finish. Retry only after this attempt has stopped."
              consequence="Nothing was charged and no preview was opened."
              testID="outcome-service-failure"
              action={
                <Button
                  label="Retry assessment"
                  disabled={!canSubmit}
                  onPress={() => void onSubmit()}
                  testID="retry-assessment"
                />
              }
            />
          ) : null}
          {phase === 'draft' || phase === 'submitting' ? (
            <Button
              label="Submit assessment"
              disabled={!canSubmit}
              busy={phase === 'submitting'}
              testID="submit-assessment"
              onPress={() => void onSubmit()}
            />
          ) : null}
        </WorkspacePanel>
      </WorkspaceShell>
    </PageShell>
  );
}

const styles = StyleSheet.create({
  eyebrow: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  stepTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  stepBody: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  linkRow: {
    gap: 12,
    minWidth: 0,
  },
  railLabel: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  railValue: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
    lineHeight: 26,
  },
  railBody: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 14,
    lineHeight: 20,
  },
});
