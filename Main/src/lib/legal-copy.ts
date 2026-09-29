export type LegalSection = {
  heading: string;
  paragraphs: string[];
};

export type LegalDocumentCopy = {
  title: string;
  subtitle: string;
  unpublished: string | null;
  sections: LegalSection[];
};

export const PRIVACY_COPY: LegalDocumentCopy = {
  title: 'Privacy',
  subtitle: 'What SkillSignalZA collects in this product, and what this page does not claim.',
  unpublished:
    'SkillSignalZA has not published a retention period, an automatic deletion schedule, or a customer process for accessing or deleting stored personal information. This page therefore does not state how long submitted files are kept or how deletion is requested.',
  sections: [
    {
      heading: 'What you submit',
      paragraphs: [
        'An assessment asks for a target track and one CV file. The CV must be a PDF or DOCX file of 10 MB or smaller. You may optionally add public evidence URLs such as repositories, projects, dashboards or a portfolio.',
        'Creating an account uses an email address and a password. SkillSignalZA uses that account to claim an assessment, confirm payment, and later reopen reports you own.',
      ],
    },
    {
      heading: 'Payment details',
      paragraphs: [
        'The full Readiness Report is a one-time R159 payment. Card details are collected in Paystack checkout, not in SkillSignalZA form fields. Returning from Paystack is not treated as proof that the report is unlocked.',
      ],
    },
    {
      heading: 'How submitted evidence is used',
      paragraphs: [
        'SkillSignalZA evaluates the submitted application bundle against the selected Software Engineering or Data Analytics track. It does not estimate hiring probability, guarantee interviews, or measure hidden capability.',
        'Protected or irrelevant personal attributes such as name, contact details, age, gender, race, disability, photograph or nationality must not affect scoring.',
        'Only candidate-submitted links are retrieved. Unsafe URL schemes, private-network targets, localhost targets, and credential-bearing URLs are blocked. Uploaded documents and retrieved page text are treated as untrusted data, not as instructions.',
      ],
    },
    {
      heading: 'Account, reports and identifiers',
      paragraphs: [
        'After you pay and SkillSignalZA confirms entitlement, the Readiness Report is available on the signed-in account. My Reports lists only safe metadata: assessment identity, track, score and band where available, access state, and dates.',
        'Claim tokens are not placed in URLs. A row in My Reports is not itself authorization; opening a report still requires a signed-in request that the backend accepts.',
      ],
    },
    {
      heading: 'What this page does not promise',
      paragraphs: [
        'This page does not claim employer partnerships, hiring outcomes, security certifications, customer counts, or testimonials. Those statements are not part of the current product.',
      ],
    },
  ],
};

export const TERMS_COPY: LegalDocumentCopy = {
  title: 'Terms',
  subtitle: 'How this SkillSignalZA release works, limited to behaviour the product actually supports.',
  unpublished: null,
  sections: [
    {
      heading: 'The product',
      paragraphs: [
        'SkillSignalZA is an application-evidence benchmark for entry-level Software Engineering and Data Analytics candidates in South Africa. A free preview follows a completed assessment. The full Readiness Report unlocks after a one-time R159 payment that SkillSignalZA has confirmed.',
        'The Career Map Pack is described on the public landing page. Purchase and download of the Career Map Pack are not available in this release.',
      ],
    },
    {
      heading: 'Your submissions',
      paragraphs: [
        'Submit only a CV and links you are allowed to provide. Public evidence links are optional and can improve what can be verified. They do not promise a higher score.',
        'If a CV cannot be read, or the assessment cannot be scored, SkillSignalZA explains that outcome and does not open checkout.',
      ],
    },
    {
      heading: 'Accounts, payment and reports',
      paragraphs: [
        'Sign-in, sign-up, email confirmation, password reset and session recovery are part of this product. If authentication started from preview, payment or a report, SkillSignalZA continues that same journey after a successful sign-in.',
        'Checkout does not start automatically. Duplicate payment initialization is blocked. Delayed confirmation tells you not to pay again. Paid report content is shown only after the protected report request succeeds.',
      ],
    },
    {
      heading: 'Limits',
      paragraphs: [
        'SkillSignalZA does not make hiring decisions, promise interviews, or guarantee employment. Backend scoring, ownership, payment and entitlement remain authoritative. This client does not rescore a report.',
      ],
    },
  ],
};

export const REFUNDS_COPY: LegalDocumentCopy = {
  title: 'Refund policy',
  subtitle: 'What this release can state about the R159 Readiness Report payment.',
  unpublished:
    'SkillSignalZA has not published refund eligibility, a refund window, or a refund method. This page therefore does not promise a refund, a cooling-off period, or an automatic reversal.',
  sections: [
    {
      heading: 'The charge this product supports',
      paragraphs: [
        'The full Readiness Report is a one-time R159 payment, not a subscription. Payment is processed through Paystack checkout. SkillSignalZA unlocks the report only after it confirms entitlement on the server.',
        'Closing checkout, returning from Paystack, or seeing a waiting screen is not proof of payment. If confirmation is delayed, do not make another payment. Check payment on the checkout screen.',
      ],
    },
    {
      heading: 'What stays unpublished',
      paragraphs: [
        'Until a refund rule is approved, SkillSignalZA will not invent a guarantee, a number of days, or a process that the current product does not implement.',
      ],
    },
  ],
};

export const SUPPORT_COPY: LegalDocumentCopy = {
  title: 'Support',
  subtitle: 'How to continue in the product while a public contact channel is unpublished.',
  unpublished:
    'A public support email, phone number, or ticket form is not published in this product yet. This page therefore does not give a contact address or a response-time promise.',
  sections: [
    {
      heading: 'Use the product first',
      paragraphs: [
        'If you already purchased a Readiness Report, sign in and open My Reports. Reports you own stay with the account, not with the original browser session.',
        'If a session ended, use the session-expired or sign-in recovery screens. SkillSignalZA continues the same assessment, payment or report journey when that context is still valid.',
        'If payment is waiting, stay on the checkout screen and check payment. Do not start another checkout and do not pay again.',
      ],
    },
    {
      heading: 'Do not send secrets',
      paragraphs: [
        'Do not send passwords, access tokens, or claim tokens. SkillSignalZA does not put claim tokens in URLs, and support copy in this app does not ask for them.',
      ],
    },
  ],
};
