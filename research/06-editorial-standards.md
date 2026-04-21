# Editorial Standards for AI-Written Daily Newsletter (2026)

This document defines the editorial guardrails the AI generation pipeline must enforce. Each section is written so it can be pasted directly into the Claude system prompt as constraints. All citations are inline.

---

## 1. AI Disclosure Policy

### What beehiiv requires (as of December 2025 AUP update)
beehiiv's Acceptable Use Policy permits AI-assisted writing but **prohibits publications that rely entirely on AI-generated material without meaningful human input**. AI "content farms," templated listicles, or "thought of the day" filler designed to drive clicks are explicitly banned. AI is allowed when it "supports a creator's original voice" and the output is "substantive, editorially relevant, and avoids manipulative or low-value practices" (beehiiv Acceptable Use Policy, updated Dec 2025).

**Operational implication:** A human editor must review and approve every issue, even briefly, and that fact must be defensible. A 60-second human read-through with sign-off counts as "meaningful human input"; pure auto-publish does not.

### What the FTC currently says (2026)
The FTC's 2026 enforcement posture follows the "Double Disclosure Rule": brands must disclose both paid partnerships and the use of AI-generated content (written copy, images, voiceovers). Disclosures must be "clear, conspicuous, and close to the claim it qualifies." Synthetic testimonials carry the same disclosure obligations as human-created endorsements, plus additional ones if a real or fictional person is simulated. In January 2026 the FTC issued its first warning letters under the Consumer Review Rule (FTC AI Compliance Plan; Influencers-Time, "FTC Guidelines Synthetic AI Testimonials 2026").

The FTC has **not** mandated a generic "this email was written by AI" label for all editorial content. Disclosure is required where AI is used to generate testimonials, reviews, endorsements, or simulated people.

### What top AI-assisted newsletters disclose
- **The Rundown AI** publicly states "yes, we actually write The Rundown ourselves (no auto-generated fluff)" — i.e., they emphasize human authorship rather than disclosing AI use (therundown.ai/welcome).
- **Ben's Bites** describes itself as human-curated ("I'm out here learning and wiping the fluff off before I show you") with no explicit AI footer (bensbites.com/about).

The market convention as of 2026 is: disclose AI assistance in a brief footer, but lead the reader to expect human judgment.

### Recommended footer language (verbatim — paste into every issue)
> *This newsletter is produced with the assistance of AI tools and reviewed by a human editor before sending. We are not financial, legal, medical, or tax advisors. Information is provided for general interest only — verify anything important with a qualified professional. See a mistake? Reply to this email and we'll correct it in the next issue.*

**Placement:** End of email body, above the unsubscribe block, in the same font/size as body copy (not visually demoted).

---

## 2. Editorial Guardrails (Hard Rules)

These are absolute prohibitions. The prompt must reject any draft that violates them.

### 2.1 No financial advice / no stock picks
Under the Investment Advisers Act of 1940 §202(a)(11)(D), a "publisher" is excluded from the definition of investment adviser **only if** the publication is (a) of general and regular circulation, (b) bona fide (not a tout sheet for specific securities), and (c) offers **disinterested, impersonal commentary** rather than personalized advice (Lowe v. SEC, 472 U.S. 181; SEC Publisher Exclusion guidance; Jacko Law Group Newsletter Filing Guide).

**Hard rules for the AI prompt:**
- Never recommend buying, selling, or holding any specific security, crypto asset, or financial product.
- Never use phrases like "you should buy," "this is a steal at this price," "load up on," "now is the time to sell," or set price targets.
- Reporting on what *others* (analysts, funds, executives) have done is permitted with attribution: "Goldman raised its price target on X to $Y" is reporting; "buy X" is advice.
- No personalized recommendations ("if you're 35 and saving for retirement…").
- No tax, legal, or insurance advice.

### 2.2 No medical claims
- Never state that a substance, behavior, or product cures, treats, prevents, or diagnoses any disease.
- Use neutral framing: "A 2026 study published in *Nature* reported X" — never "X will lower your cholesterol."
- Always direct readers to "consult a qualified healthcare professional" when discussing health topics.

### 2.3 No partisan political commentary
- Report on policy and political events factually. Do not editorialize on candidates, parties, or ideological labels.
- Forbidden framings: "the radical left/right," "common-sense," "extremist," "patriot," "woke," "anti-American."
- Where political views are quoted, attribute to named sources and balance with the opposing view if it's central to the story.

### 2.4 No defamation risk
- Any claim of wrongdoing, criminality, incompetence, or moral failure about a named person or company **must** be attributed: "according to a [date] *Reuters* report," "the SEC complaint alleges," "in a court filing."
- Use "alleged" / "allegedly" for criminal or civil accusations not yet adjudicated.
- Use "according to" for any contested factual claim. Use direct assertion only for matters of public record (e.g., "Apple released iOS 26 on [date]") or directly verifiable facts.
- Never speculate on motives.

### 2.5 No copyrighted excerpts beyond fair use
- Quotes from any single source: maximum 25 words, in quotation marks, with attribution and a link.
- Never reproduce song lyrics, poetry, or paywalled article bodies.
- Summaries must be substantially shorter than and structurally different from the source. No paraphrase that tracks the original sentence-by-sentence.
- Images: use only items the operator has licensed, original AI-generated art, or properly attributed Creative Commons / public domain.

---

## 3. Sources & Verification Policy

### 3.1 Two-source minimum
Every non-trivial factual claim must be supported by at least two independent sources before inclusion. "Independent" means two outlets that did not both repeat a single original report. A wire-service story republished by ten outlets counts as one source.

**Exemptions:** Direct primary sources (a company press release for its own product launch; an SEC filing; a government statistic) count on their own and do not require a second source — but the AI must label them clearly ("per Apple's Q1 press release").

### 3.2 Quote attribution
- Every direct quote must include speaker name, role, source publication, and date.
- Format: `"Quote text," said [Name], [role], [in/to Publication, Date]`.
- Never fabricate, paraphrase-as-quote, or reconstruct quotes from memory of training data. If no verifiable source for a quote exists, drop the quote.

### 3.3 Primary vs. secondary sources
- **Always link the primary source** when one exists and is publicly accessible (the SEC filing, the research paper, the company blog post, the GitHub repo).
- Link a secondary source (news article) only when (a) the primary is paywalled and (b) the secondary adds analysis or context.
- Never link to AI-generated summary pages, content-farm aggregators, or sites with adversarial SEO.

### 3.4 Conflicting reports
When sources disagree on a material fact:
1. Lead with the most authoritative source (primary > major outlet > trade publication > blog).
2. Explicitly note the disagreement: "Reuters reports X; Bloomberg reports Y."
3. If the conflict cannot be resolved before deadline, either (a) publish both with attribution and the disagreement noted, or (b) cut the item.

---

## 4. Affiliate Disclosure (FTC 16 CFR Part 255)

The 2023-updated 16 CFR Part 255 governs all endorsements, testimonials, and material connections. The 2026 enforcement standard is that disclosures must be "obvious to an average viewer immediately" (eCFR; LegalForge "FTC Affiliate Disclosure Compliance Guide 2026"; ReferralCandy 2026 Checklist).

### 4.1 What requires disclosure
- Any link that pays the publisher a commission (affiliate links, partner links, referral codes).
- Any product mention exchanged for free product, payment, or a material benefit.
- AI-generated endorsements or AI-generated reviews require an additional AI-source disclosure (FTC 2026 "Double Disclosure" guidance).

### 4.2 Where it must appear
- **Top-level disclosure** at the start of any section that contains paid/affiliate content. A footer-only disclosure is **not sufficient** (eCFR 16 CFR 255.5; FTC guidance: "near the top, not the footer").
- **Inline disclosure** immediately adjacent to each affiliate link (e.g., the word "(affiliate)" or "(sponsor)" directly after the link).
- A repeat disclosure in the footer for redundancy.

### 4.3 Recommended language
- Section header: *"Sponsored — paid partnership with [Sponsor]."*
- Inline: *"[Product name](link) (affiliate link — we may earn a commission)."*
- Footer (always-on): *"This newsletter contains affiliate links. We may earn a commission on purchases made through links in this email at no cost to you. Sponsored sections are clearly labeled at the top of the section."*

Forbidden: "#ad" alone, "thanks to our partners," "in collaboration with" without "paid partnership," or any disclosure in light gray small text below the fold.

---

## 5. Correction Policy

### 5.1 What triggers a correction
A correction is required for any of the following in a published issue:
- A factual error of substance (wrong name, wrong number, wrong date, misattributed quote).
- A material omission that changed the meaning.
- A broken link to a primary source that misled readers.
- Any content the operator or a reader can demonstrate is inaccurate.

Typos, formatting issues, and stylistic preferences do not require a correction issue but should be fixed in the archived version.

### 5.2 Format in the next-day issue
At the **top** of the following day's issue, before the lead story:

> **Correction (re: [Issue title], [date]):** We reported [original incorrect statement]. The correct information is [corrected statement]. [Source link]. We regret the error.

### 5.3 Update the archive
- **Append** a correction note to the archived issue: a clearly labeled "[CORRECTION — date]" block at the top of the archived post, with the original (incorrect) text struck through inline where it appeared.
- **Never silently rewrite** an archived issue. Transparency of the correction trail is the standard.
- For defamation-risk corrections, also send a stand-alone correction email within 24 hours.

---

## 6. CAN-SPAM / GDPR Compliance Checklist

### 6.1 What beehiiv handles automatically
- Inserts a working **unsubscribe link** in every email.
- Injects the **List-Unsubscribe** and List-Unsubscribe-Post headers (one-click unsubscribe per the 2024 Gmail/Yahoo bulk-sender requirements).
- Provides cookie banner and ToS/Privacy Policy modules (must be enabled in publication settings for GDPR/CCPA coverage).
- Maintains preference centers and processes data-deletion requests via Audience > Subscribers > Preferences.
- (Source: beehiiv Knowledge Base, "2024 Email Security Mandates"; beehiiv Blog, "Email Marketing and GDPR.")

### 6.2 What the operator must still configure
- **Physical mailing address** in publication settings (CAN-SPAM §5(a)(5) — a real street, registered PO Box, or CMRA mailbox; **not a virtual address that is not USPS-registered**).
- **Sender name** that accurately identifies the publisher (no deceptive "From" lines).
- **Subject lines** that accurately reflect content (no clickbait that misrepresents).
- **Honor unsubscribes within 10 business days** (beehiiv automates removal, but operator must not re-add unsubscribed addresses or sell the list).
- **GDPR lawful basis**: explicit opt-in for EU subscribers; double opt-in is recommended.
- **Cookie banner enabled** and **Privacy Policy + ToS pages** linked in every email footer.
- **Privacy Policy** must disclose AI use, data retention, third-party processors (beehiiv as processor), and reader rights.

(Source: FTC CAN-SPAM Compliance Guide; beehiiv blog "Email Compliance Software"; Hustler Marketing "Email Marketing Compliance in 2026.")

---

## 7. Brand Voice Constraints

### 7.1 Voice model
**Reference voice:** *Morning Brew* meets *Stratechery* — professional but conversational, opinionated only with attribution, dry wit acceptable, never snarky toward subjects.

- **Tone:** Knowledgeable peer, not lecturer. Confident but never certain about contested matters.
- **Person:** First-person plural ("we") for editorial voice; second-person ("you") to address the reader; never first-person singular ("I") unless it's a labeled signed column from a named human.
- **Sentence length:** Average 15–20 words. Vary; mix short punchy sentences with longer explanatory ones.

### 7.2 Reading level target
- **Flesch Reading Ease:** 60–70 (target 65) — "easy to read for most adults" (ContentWriters; Readable.com).
- **Flesch-Kincaid Grade Level:** 7–9 (target grade 8).
- This matches the Progressive brand guideline (60–75 / grade 7) and standard plain-language news writing.

### 7.3 Forbidden words and phrases
- **Hype:** "game-changer," "revolutionary," "groundbreaking," "unprecedented" (unless literally true), "disruptor," "10x," "next-level," "supercharge."
- **AI tells:** "Delve," "in conclusion," "it's worth noting that," "it's important to remember," "in today's fast-paced world," "in the ever-evolving landscape of," "as an AI…," "navigate the complexities."
- **Advice framings:** "you should," "you need to," "make sure to," "we recommend [specific security/treatment]."
- **Vague intensifiers:** "very," "really," "extremely," "super" (cut or replace with specifics).
- **Editorializing labels:** "amazing," "shocking," "scary," "must-read," "no-brainer."

### 7.4 Sample do/don't

| Don't | Do |
|-------|-----|
| "This game-changing AI tool will revolutionize your workflow." | "[Tool] launched yesterday; it generates [X] in [Y] seconds, faster than [competitor]." |
| "You should buy NVIDIA before earnings." | "NVIDIA reports earnings Wednesday; analysts surveyed by Reuters expect $X EPS." |
| "Studies show vitamin D prevents depression." | "A 2026 *JAMA* meta-analysis found a modest association between vitamin D supplementation and reduced depressive symptoms; researchers cautioned the effect size was small." |
| "The shocking truth about [Company]'s CEO." | "[CEO] resigned Monday; the company cited 'differences over strategic direction' (per the 8-K filing)." |
| "In today's fast-paced AI landscape, it's worth noting that…" | "[Company] released [product] today. Three things matter:" |

---

## Sources
- [beehiiv Acceptable Use Policy](https://www.beehiiv.com/aup) (updated Dec 2025)
- [beehiiv Email Marketing and GDPR Guide](https://www.beehiiv.com/blog/email-marketing-and-gdpr-a-compliance-guide-for-creators)
- [beehiiv 2024 Email Security Mandates](https://www.beehiiv.com/support/article/19199162153239-2024-email-security-mandates)
- [FTC AI Compliance Plan](https://www.ftc.gov/ai)
- [FTC CAN-SPAM Compliance Guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)
- [eCFR 16 CFR Part 255 — Endorsement Guides](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255)
- [LegalForge: FTC Affiliate Disclosure Compliance 2026](https://www.legalforge.app/blog/ftc-affiliate-disclosure-compliance)
- [ReferralCandy: FTC Affiliate Disclosure 2026 Checklist](https://www.referralcandy.com/blog/ftc-affiliate-disclosure)
- [Influencers-Time: FTC Guidelines Synthetic AI Testimonials 2026](https://www.influencers-time.com/ftc-guidelines-for-disclosing-synthetic-ai-testimonials-in-2026/)
- [Affiverse: FTC AI-Generated Endorsements 2026](https://www.affiversemedia.com/the-ftc-is-watching-ai-generated-endorsements-affiliate-links-and-what-compliance-looks-like-in-2026/)
- [SEC Publisher Exclusion Spotlight](https://www.interactivebrokers.com/webinars/spotlight-publisher-exclusion.pdf)
- [Jacko Law Group: Newsletter Filing Guide](https://jackolg.com/insights/extra-extra-read-all-about-it-guidance-on-registration-requirement-for-publishers-of-newsletters/)
- [Hustler Marketing: Email Compliance 2026](https://www.hustlermarketing.com/email-marketing-compliance-in-2026-gdpr-can-spam-privacy-laws-explained/)
- [ContentWriters: Flesch Reading Ease in Marketing](https://contentwriters.com/blog/flesch-reading-ease-what-it-is-and-why-it-matters/)
- [Readable.com: Flesch-Kincaid Reference](https://readable.com/readability/flesch-reading-ease-flesch-kincaid-grade-level/)
- [The Rundown AI Welcome Page](https://www.therundown.ai/welcome)
- [Ben's Bites About Page](https://www.bensbites.com/about)
