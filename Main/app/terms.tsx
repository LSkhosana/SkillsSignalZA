import { LegalDocument } from '@/components/legal-document';
import { TERMS_COPY } from '@/lib/legal-copy';

export default function TermsScreen() {
  return <LegalDocument copy={TERMS_COPY} testID="terms-screen" />;
}
