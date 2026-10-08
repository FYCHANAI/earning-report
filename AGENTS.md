# NTAM research website maintenance

The owner requires strict preservation of the existing website skeleton. Maintain this repository and its existing hosting; do not migrate frameworks or hosting during report updates.

## Preserve the template

- Read the ticker's three files: `<ticker>.html`, `<ticker>-sc.html`, `<ticker>-en.html`.
- Preserve HTML structure, classes, IDs, CSS, fixed JavaScript, tab order, language selector, charts, PI notice, disclaimer and AI interfaces.
- Respect `🔒` fixed and `✏️` replacement comments. Update only company/period text, financial values, chart data/labels and company-specific AI context within the replacement scope.
- Do not reformat files or replace older pages with a universal template. NVDA, NIO and MCD have seven tabs including `sandbox`; most other pages have six. Preserve these differences.
- For a new ticker, use the existing AVGO three-language template and its documented ticker/chart-key replacements, including corresponding `switchTab` resize keys.
- Fixed-component repairs need a separately defined scope. A content update does not authorize a redesign.
- Do not alter `CNAME`, `disclaimer.html`, PI legal wording, API route or secret configuration as part of a report update.

## Research and translation

- Use corporate disclosures, filings, company IR materials and original institutional research. Obtain the owner's permission before using mass-market finance platforms when authoritative evidence is insufficient. Do not use editable sites.
- Bloomberg ANR/EEO require dated original evidence or user-provided screenshots. Existing website labels are historical claims, not current evidence.
- Distinguish actuals, guidance, consensus and NTAM calculations/opinions. Do not attribute NTAM inference to a bank without its original report.
- Owner display convention (8 October 2026): Wall Street rating labels use exactly `Overweight`, `Buy`, `Neutral`, `Sell`, or `Underweight`, as corrected by the owner. Current MU cards use Buy / Overweight / Overweight. Preserve raw source ratings in research notes; do not invent mappings for unused categories.
- Wall Street rating badge colors are fixed by rating, never by broker: `Overweight` = dark blue (`bg-blue-100 text-blue-800`); `Buy` = green (`bg-emerald-100 text-emerald-800`); `Neutral` = gray (`bg-slate-100 text-slate-600`); `Sell` = pink (`bg-pink-100 text-pink-700`); `Underweight` = bright red (`bg-red-100 text-red-600`). Preserve the existing pale background badge style, sizing and layout. These explicitly requested color-class changes are allowed within the fixed skeleton.
- In “Our Views”, write “我們認為” / “我们认为” / “We believe” instead of naming NTAM as the speaker.
- Select Wall Street broker cards by availability in this priority: `UBS` > `Morgan Stanley` > `JP Morgan` > `Citi` > `HSBC`. Fill the existing card slots with the highest-priority available evidence; use other institutions only if the preferred list does not supply enough verified ratings. Preserve the original card count and skeleton.
- Public report prose omits calculator attribution such as “NTAM calculation” and repeated equivalent disclaimer wording. Keep the Wall Street source line to the Bloomberg ANR date and reference share-price date/value only. Preserve calculations and detailed provenance in research notes.
- Record reporting period, publication date, market-data as-of date, currency, unit and accounting basis. Never relabel old prices, targets or valuations with a new date.
- Preserve GAAP/non-GAAP, TIFRS, reported/adjusted, diluted/basic EPS, fiscal/calendar year, quarterly/YTD and pre-/post-elimination distinctions. Check ADR and split adjustments when relevant.
- Use one verified fact set for all three languages. Synchronize header, comments, KPI cards, tables, chart data/labels, valuation, broker views, risks and AI welcome/company context.
- Update the matching homepage card for a substantive report update. A wording correction to a historical snapshot must not imply refreshed data.
- Keep primary-source URLs and evidence in repository research notes. Missing inputs remain pending; never invent values, analyst views or dates.

## Verification and release

- Review the full diff against the current upstream revision. For text-only corrections, verify raw HTML tags/attributes, script/style bodies and dates are unchanged.
- For financial updates, reconcile totals, units, margins, growth, EPS basis, price/target formulas and three-language chart/table parity.
- Check tab order, language filenames, chart IDs/resize keys, internal links and changed inline JavaScript syntax. Review affected functions and desktop/mobile rendering when behavior or layout changes.
- Use a branch and reviewable commit. Distinguish local preparation, remote push, merge and verified production deployment. Do not claim checks or deployment that did not occur.
- Never commit credentials. The backend reads `GEMINI_API_KEY` from its deployment environment.

See `README.md` for the baseline and known issues. Later explicit owner instructions take precedence over these maintenance notes.
