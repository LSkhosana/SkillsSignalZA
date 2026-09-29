import { LegalDocument } from '@/components/legal-document';
import { PRIVACY_COPY } from '@/lib/legal-copy';

export default function PrivacyScreen() {
  return <LegalDocument copy={PRIVACY_COPY} testID="privacy-screen" />;
}
