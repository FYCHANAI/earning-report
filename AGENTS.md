# NTAM research website maintenance

The owner's latest instruction (8 October 2026) makes the latest MU three-language layout the single canonical template for all company reports. Maintain this repository and its existing hosting; do not migrate frameworks or hosting during report updates.

## Use the latest MU template

- Read the target ticker's three complete files and the current corresponding masters: `mu.html`, `mu-sc.html`, `mu-en.html`. Use each language's MU file as its own layout reference.
- All new reports and future updates to existing reports must follow the latest MU layout: six sections in this order — Our Views, Financials, Valuation, Wall Street Views, Risks, Disclaimer — with MU's white/blue presentation, header, cards, financial comparison table, chart containers, language selector, responsive layout, chat and explain-AI interfaces.
- Carry over the MU frontend behavior needed for that layout, including chart instance storage and the matching `switchTab` resize keys. Adapt ticker-specific IDs, instance keys, links, labels and company AI context consistently. Do not retain an older ticker's seventh `sandbox` tab or its former visual design.
- NVDA, ORCL, MCD and NIO now use this template in all three languages. Other older company pages migrate when they are next updated; do not bulk-convert unrelated pages without a request. The former rules preserving each ticker's old layout and using AVGO for new tickers are superseded.
- Preserve the target company's verified research, financial period, publication date and market-data dates. Never carry MU's company facts, targets, ratings, peers or AI context into another report. Adapt financial metrics, table rows and chart datasets to the company's business and available evidence within the MU presentation; do not invent values to fill a template.
- Respect `🔒` fixed and `✏️` replacement comments after applying the MU layout. The owner's layout instruction authorizes the necessary MU UI/frontend conversion, not unrelated refactoring or a redesign of MU itself. Unrelated fixed-component repairs still need a defined scope.
- Preserve PI legal wording and acceptance controls, the disclaimer and its loading behavior, API handling and shared infrastructure. Do not alter `CNAME`, `disclaimer.html`, the API route, model/secret configuration or hosting configuration as part of the layout conversion or report update.
- Risk-section formatting must match across Traditional Chinese, Simplified Chinese and English. Per the owner's 9 October 2026 correction, the first risk heading uses the same dark text as the remaining headings; never give it a red/rose emphasis. Keep this rule in the MU language masters and every report, including older layouts.

## Research and translation

- Company names on Traditional/Simplified Chinese pages must use the company's verified official name for that locale, including the page title, heading, company references, chart labels and company-specific AI text. Keep stock tickers unchanged. Use official corporate or regulatory evidence; do not infer an official name from a common media translation or mechanically convert regional names. Current examples: NVDA = 輝達 / 英伟达; AMD = 超微半導體 / 超威半导体; AVGO = 博通 / 博通. Retain English when no official Chinese name is verified (including the owner's Alphabet / Meta examples); preserve English product brands and source titles where appropriate. English pages retain English company names. A naming-only correction does not refresh financial dates or require unrelated layout changes.
- Use corporate disclosures, filings, company IR materials and original institutional research. Obtain the owner's permission before using mass-market finance platforms when authoritative evidence is insufficient. Do not use editable sites.
- Bloomberg ANR/EEO require dated original evidence or user-provided screenshots. Existing website labels are historical claims, not current evidence.
- Distinguish actuals, guidance, consensus and NTAM calculations/opinions. Do not attribute NTAM inference to a bank without its original report.
- Owner display convention (8 October 2026): Wall Street rating labels use exactly `Overweight`, `Buy`, `Neutral`, `Sell`, or `Underweight`, as corrected by the owner. Current MU cards use Buy / Overweight / Overweight. Preserve raw source ratings in research notes; do not invent mappings for unused categories.
- Wall Street rating badge colors are fixed by rating, never by broker: `Overweight` = dark blue (`bg-blue-100 text-blue-800`); `Buy` = green (`bg-emerald-100 text-emerald-800`); `Neutral` = gray (`bg-slate-100 text-slate-600`); `Sell` = pink (`bg-pink-100 text-pink-700`); `Underweight` = bright red (`bg-red-100 text-red-600`). Preserve the existing pale background badge style, sizing and layout. These explicitly requested color-class changes are allowed within the fixed skeleton.
- In “Our Views”, write “我們認為” / “我们认为” / “We believe” instead of naming NTAM as the speaker.
- Select Wall Street broker cards by availability in this priority: `UBS` > `Morgan Stanley` > `JP Morgan` > `Citi` > `HSBC`. Fill the MU template's card slots with the highest-priority available evidence; use other institutions only if the preferred list does not supply enough verified ratings. Preserve MU's card presentation; missing evidence remains pending rather than fabricated.
- Public report prose omits calculator attribution such as “NTAM calculation” and repeated equivalent disclaimer wording. Keep the Wall Street source line to the Bloomberg ANR date and reference share-price date/value only. Preserve calculations and detailed provenance in research notes.
- Public rating text and AI responses omit parenthetical site-classification explanations such as “本站統一分類”, “本站统一分类” and “site-standardized label”. Use the approved rating label alone; retain original source ratings and normalization evidence in research notes.
- Record reporting period, publication date, market-data as-of date, currency, unit and accounting basis. Never relabel old prices, targets or valuations with a new date.
- Preserve GAAP/non-GAAP, TIFRS, reported/adjusted, diluted/basic EPS, fiscal/calendar year, quarterly/YTD and pre-/post-elimination distinctions. Check ADR and split adjustments when relevant.
- Use one verified fact set for all three languages. Synchronize header, comments, KPI cards, tables, chart data/labels, valuation, broker views, risks and AI welcome/company context.
- Update the matching homepage card for a substantive report update. A wording correction to a historical snapshot must not imply refreshed data.
- Sort homepage report cards by the actual earnings publication date of the quarter covered by each report, newest first, not the report editing/update date. Verify the dates with primary sources and record them in `research/`; preserve existing order for tied dates. An older report keeps its covered quarter's publication date until its research content is updated.
- Keep primary-source URLs and evidence in repository research notes. Missing inputs remain pending; never invent values, analyst views or dates.

## Verification and release

- Review the full diff against the current upstream revision and the corresponding MU language master. For a layout conversion, verify the MU structure/styles/frontend behavior and preservation of the target's research facts and protected components. For text-only corrections after migration, verify raw HTML tags/attributes, script/style bodies and dates are unchanged.
- For financial updates, reconcile totals, units, margins, growth, EPS basis, price/target formulas and three-language chart/table parity.
- Check tab order, language filenames, chart IDs/resize keys, internal links and changed inline JavaScript syntax. Review affected functions and desktop/mobile rendering when behavior or layout changes.
- Use a branch and reviewable commit. Distinguish local preparation, remote push, merge and verified production deployment. Do not claim checks or deployment that did not occur.
- Never commit credentials. The backend reads `GEMINI_API_KEY` from its deployment environment.

See `PROJECT_INSTRUCTIONS.md` for the reusable Traditional Chinese project instructions and `README.md` for the baseline and known issues. Later explicit owner instructions take precedence over these maintenance notes.
