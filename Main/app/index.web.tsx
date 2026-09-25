import { useRouter } from 'expo-router';
import { useEffect, type CSSProperties } from 'react';

import '@/theme/landing.css';

const PRODUCT_FEATURES = {
  report: [
    'Readiness score and band',
    'Category-by-category breakdown',
    'Strengths and areas to strengthen',
    'Five priority actions',
    'Portfolio project recommendation',
  ],
  map: [
    'Career lanes and role patterns',
    'Repeated employer skill signals',
    'Portfolio blueprint guidance',
    'Market-informed progression map',
  ],
};

const HOW_STEPS = [
  ['01', 'Submit your application bundle', 'Choose a track, upload a PDF or DOCX CV, and optionally add public links to repositories, projects, dashboards or a portfolio.'],
  ['02', 'Review the free preview', 'See your readiness score, band and track before deciding whether the full report is worth unlocking.'],
  ['03', 'Decide what to do next', 'Unlock the detailed report once, or use the Career Map Pack to understand the wider market before planning your next move.'],
];

const MARQUEE = [
  'Built for South African entry-level tech candidates',
  'Software Engineering',
  'Data Analytics',
  'Evidence before assumptions',
  'Free readiness preview',
  'Full Readiness Report · R159 once',
];

export default function WebLandingScreen() {
  const router = useRouter();

  useEffect(() => {
    document.title = 'SkillSignalZA — Entry-level tech readiness, grounded in evidence';

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('.ss-reveal'));

    if (reduceMotion || !('IntersectionObserver' in window)) {
      nodes.forEach((node) => node.classList.add('ss-visible'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).classList.add('ss-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' },
    );

    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  const startAssessment = () => router.push('/assessment/new');

  return (
    <div className="ss-site">
      <div className="ss-top-rule" />

      <header className="ss-header">
        <div className="ss-container ss-header-main">
          <a className="ss-brand-small" href="#top" aria-label="SkillSignalZA home">
            <span className="ss-brand-mark" aria-hidden="true">
              <span /><span /><span />
            </span>
            <span>SkillSignalZA</span>
          </a>

          <div className="ss-wordmark">SKILLSIGNALZA</div>

          <div className="ss-header-actions">
            <a className="ss-link-button" href="#career-map-pack">Career Map Pack</a>
            <button className="ss-primary" type="button" onClick={startAssessment}>
              Start assessment <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>

        <nav className="ss-nav" aria-label="Main navigation">
          <div className="ss-container ss-nav-inner">
            <a href="#readiness-report">Readiness Report</a>
            <a href="#career-map-pack">Career Map Pack</a>
            <a href="#how-it-works">How it works</a>
            <a href="#sample-report">Sample report</a>
            <a href="#benchmark">About the benchmark</a>
          </div>
        </nav>
      </header>

      <div className="ss-marquee" aria-hidden="true">
        <div className="ss-marquee-track">
          {[...MARQUEE, ...MARQUEE].map((item, index) => (
            <span className="ss-marquee-item" key={`${item}-${index}`}>{item}</span>
          ))}
        </div>
      </div>

      <main id="top">
        <section className="ss-hero" id="readiness-report">
          <div className="ss-container ss-hero-grid">
            <div className="ss-reveal ss-visible">
              <p className="ss-eyebrow">Entry-level career readiness · South Africa</p>
              <h1>
                See what your application <em>evidence</em> actually communicates.
              </h1>
              <p className="ss-hero-deck">
                Submit your CV and optional project links. Get a free readiness preview against
                the SkillSignalZA benchmark, then unlock a detailed action plan if you want to go deeper.
              </p>
              <div className="ss-hero-actions">
                <button className="ss-primary" type="button" onClick={startAssessment}>
                  Assess my application <span aria-hidden="true">→</span>
                </button>
                <a className="ss-secondary" href="#career-map-pack">Explore Career Map Pack</a>
              </div>
              <p className="ss-hero-note">
                Free preview included · Full Readiness Report R159 once · No hiring-outcome promises
              </p>
            </div>

            <aside className="ss-hero-side ss-reveal" data-delay="1" aria-label="How SkillSignalZA works">
              <div className="ss-editorial-step">
                <span className="ss-step-index">01</span>
                <h3>Submit evidence</h3>
                <p>Your CV is required. Public project and portfolio links are optional and can strengthen what can be verified.</p>
              </div>
              <div className="ss-editorial-step">
                <span className="ss-step-index">02</span>
                <h3>Get a free preview</h3>
                <p>See your readiness score, band and selected track before paying anything.</p>
              </div>
              <div className="ss-editorial-step">
                <span className="ss-step-index">03</span>
                <h3>Unlock the report</h3>
                <p>Pay once for the detailed category breakdown, actions, criterion detail and project recommendation.</p>
              </div>
            </aside>
          </div>
          <div className="ss-orbit" aria-hidden="true" />
        </section>

        <section className="ss-section" id="career-map-pack">
          <div className="ss-container">
            <div className="ss-section-heading ss-reveal">
              <div>
                <p className="ss-eyebrow">Choose your product</p>
                <h2>Two ways to move forward.</h2>
              </div>
              <p className="ss-section-intro">
                The Readiness Report evaluates the application evidence you have now.
                The Career Map Pack helps you understand the market and decide what to build toward next.
              </p>
            </div>

            <div className="ss-products">
              <article className="ss-product ss-reveal" data-delay="1">
                <span className="ss-eyebrow">Readiness Report</span>
                <h3>Application evidence, scored and translated into next actions.</h3>
                <div className="ss-price">Free preview · Full report R159</div>
                <p className="ss-product-copy">
                  For candidates who already have a CV and want to understand how strongly their current
                  application communicates entry-level readiness.
                </p>
                <ul className="ss-feature-list">
                  {PRODUCT_FEATURES.report.map((item) => <li key={item}>{item}</li>)}
                </ul>
                <div className="ss-product-actions">
                  <button className="ss-primary" type="button" onClick={startAssessment}>
                    Start assessment <span aria-hidden="true">→</span>
                  </button>
                </div>
                <span className="ss-product-index" aria-hidden="true">01</span>
              </article>

              <article className="ss-product ss-reveal" data-delay="2">
                <span className="ss-eyebrow">
                  Career Map Pack
                  <span className="ss-coming-soon">Checkout coming later</span>
                </span>
                <h3>Understand the market before choosing what to build next.</h3>
                <div className="ss-price">Digital download</div>
                <p className="ss-product-copy">
                  A focused career map for entry-level Software Engineering or Data Analytics candidates,
                  built from SkillSignalZA market evidence.
                </p>
                <ul className="ss-feature-list">
                  {PRODUCT_FEATURES.map.map((item) => <li key={item}>{item}</li>)}
                </ul>
                <div className="ss-product-actions">
                  <a className="ss-secondary" href="#benchmark">Read about the Map Pack</a>
                </div>
                <span className="ss-product-index" aria-hidden="true">02</span>
              </article>
            </div>
          </div>
        </section>

        <section className="ss-section" id="how-it-works">
          <div className="ss-container">
            <div className="ss-section-heading ss-reveal">
              <div>
                <p className="ss-eyebrow">How it works</p>
                <h2>Evidence first. Then interpretation.</h2>
              </div>
              <p className="ss-section-intro">
                SkillSignalZA evaluates what the submitted application bundle communicates.
                It does not claim to measure hidden ability or predict hiring outcomes.
              </p>
            </div>

            <div className="ss-how">
              {HOW_STEPS.map(([number, title, copy], index) => (
                <article className="ss-how-item ss-reveal" data-delay={String(index + 1)} key={number}>
                  <div className="ss-how-number">{number}</div>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="ss-section" id="sample-report">
          <div className="ss-container">
            <div className="ss-section-heading ss-reveal">
              <div>
                <p className="ss-eyebrow">The paid experience</p>
                <h2>A report designed to be used, not merely read.</h2>
              </div>
              <p className="ss-section-intro">
                The full report moves from understanding the result, to diagnosing gaps,
                to taking specific action, then exposes criterion detail only when it is useful.
              </p>
            </div>

            <div className="ss-report-shell ss-reveal">
              <div className="ss-report-score">
                <div>
                  <small>Foundation visible</small>
                  <strong>51</strong>
                  <p>/ 100</p>
                </div>
                <div>
                  <small>Track</small>
                  <p>Software Engineering</p>
                </div>
              </div>

              <div className="ss-report-main">
                <p className="ss-eyebrow">Category performance</p>
                <h3>Your readiness at a glance.</h3>

                <div className="ss-bars">
                  {[
                    ['Core Technical Skills', '49%', '17 / 35'],
                    ['Tools & Platforms', '55%', '11 / 20'],
                    ['Applied Project Evidence', '53%', '8 / 15'],
                    ['Application Alignment', '55%', '11 / 20'],
                    ['Work Readiness', '40%', '4 / 10'],
                  ].map(([label, score, value]) => (
                    <div className="ss-bar" key={label}>
                      <span>{label}</span>
                      <div className="ss-bar-track">
                        <div className="ss-bar-fill" style={{ '--score': score } as CSSProperties} />
                      </div>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>

                <div className="ss-report-notes">
                  <div className="ss-report-note">
                    <p className="ss-eyebrow">Strongest area</p>
                    <h4>Tools & Platforms</h4>
                    <p>Positive evidence is surfaced clearly without turning the entire interface into a dashboard of green cards.</p>
                  </div>
                  <div className="ss-report-note">
                    <p className="ss-eyebrow">Priority area</p>
                    <h4>Proof & Accessibility</h4>
                    <p>Partial evidence can still leave room to strengthen a criterion. The customer-facing language explains that distinction.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="ss-statement" id="benchmark">
          <div className="ss-container">
            <p className="ss-reveal">
              Not another generic AI score. A deliberately narrow, <em>evidence-led</em> view of how an entry-level application presents itself.
            </p>
          </div>
          <div className="ss-statement-orbit" aria-hidden="true" />
        </section>

        <section className="ss-section">
          <div className="ss-container">
            <div className="ss-section-heading ss-reveal">
              <div>
                <p className="ss-eyebrow">Product behaviour</p>
                <h2>Loading and failure are part of the design.</h2>
              </div>
              <p className="ss-section-intro">
                The application keeps the same geometry through loading, success and failure.
                It blocks impossible actions and explains recovery rather than dumping raw errors.
              </p>
            </div>

            <div className="ss-trust-grid">
              <article className="ss-trust-card ss-reveal" data-delay="1">
                <p className="ss-eyebrow">Loading</p>
                <h3>Structured skeletons</h3>
                <p>Skeletons mirror the content that is coming instead of replacing an entire route with a generic spinner.</p>
                <div className="ss-skeleton" aria-hidden="true"><span /><span /><span /></div>
              </article>

              <article className="ss-trust-card ss-reveal" data-delay="2">
                <p className="ss-eyebrow" style={{ color: '#a92d2d' }}>Failure</p>
                <h3>Explain what happened</h3>
                <p>Critical failures tell the customer what happened, whether anything was charged or lost, and the safest next action.</p>
                <div className="ss-failure">Payment confirmation is taking longer than expected. Do not make another payment. Check again safely.</div>
              </article>

              <article className="ss-trust-card ss-reveal" data-delay="3">
                <p className="ss-eyebrow" style={{ color: '#8a5a08' }}>Blocked action</p>
                <h3>Prevent impossible transitions</h3>
                <p>Actions become unavailable when the current state does not permit them. The interface explains why before a bad request is possible.</p>
                <button className="ss-secondary ss-disabled-demo" type="button" disabled>Continue to payment</button>
              </article>
            </div>
          </div>
        </section>
      </main>

      <footer className="ss-footer">
        <div className="ss-container ss-footer-inner">
          <div>
            <div className="ss-brand-small">
              <span className="ss-brand-mark" aria-hidden="true"><span /><span /><span /></span>
              <span>SkillSignalZA</span>
            </div>
            <p>
              Application evidence benchmark for entry-level Software Engineering and Data Analytics candidates in South Africa.
            </p>
          </div>
          <div className="ss-footer-links">
            <a href="#benchmark">About the benchmark</a>
            <a href="#career-map-pack">Career Map Pack</a>
            <a href="#top">Privacy</a>
            <a href="#top">Terms</a>
            <a href="#top">Refunds</a>
            <a href="#top">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
