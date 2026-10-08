# NTAM investment research website

## NVDA research update — 8 October 2026

The three NVIDIA reports cover FY2027 Q2, ended 26 July 2026 and announced on 26 August. The update combines official results, CFO commentary and filings with owner-supplied Bloomberg ANR/EEO evidence. The consensus target is US$323.89 versus the 7 October reference share price of US$237.47. Broker cards contain only the verified UBS, Morgan Stanley and Citi ratings, dates, targets and implied price returns.

The report uses the latest recast Hyperscale/ACIE comparisons and the company non-GAAP basis that includes stock-based compensation. Working-capital demands, supply commitments and conditional guarantees are distinguished from growth catalysts. Peer valuation uses Bloomberg's Next 4 Qtrs Est Price/EPS, Adj+ field; the date visibility, fiscal-window and adjustment-basis limitations remain explicit.

The original seven tabs, three charts, four view items, three broker cards and four risk items are retained. One compact Wall Street source paragraph implements the owner's required attribution format. PI controls, legal text, CSS, API handling and fixed JavaScript remain unchanged. AI company context is dated and does not imply live prices.

The homepage is sorted by the actual earnings publication date of each report's covered quarter, not its editing date. Its leading cards are MU (30 September), AVGO (2 September) and NVDA (26 August); all other company cards retain their original content.

- [NVDA source and calculation ledger](research/nvda-fy2027-q2-2026-10-08.json)
- [NVDA validation record](research/nvda-fy2027-q2-validation.json)
- [Homepage earnings-date ledger](research/homepage-earnings-order-2026-10-08.json)

Original Bloomberg screenshots are not committed. Validation and deployment status are recorded separately; see the validation record, pull request and commit checks for actual results.

## MU research update — 8 October 2026

Micron reports in Traditional Chinese, Simplified Chinese and English now cover FY2026 Q4 and full year, published on 30 September for the period ended 3 September. The homepage MU card is updated and moved to the first position. Other company reports and homepage cards are unchanged.

The original six tabs, HTML classes, styles, chart layout, language selector, legal wording and AI interfaces are preserved. Company text, financial figures, four chart datasets and dated AI context are refreshed. A separate repair restores the missing English/Simplified PI controls from the Traditional Chinese implementation and the Simplified net-income label cell.

- [Maintenance rules](AGENTS.md)
- [Project Instructions（繁體中文，可貼入專案設定）](PROJECT_INSTRUCTIONS.md)
- [Source and calculation ledger](research/mu-fy2026-q4-2026-10-08.json)
- [Validation record](research/mu-fy2026-q4-validation.json)

The ledger combines Micron disclosures and owner-supplied Bloomberg ANR/EEO screenshots. Original screenshots are not committed. Broker cards contain verified ratings and targets; implied returns are NTAM calculations. EEO accounting bases and observation dates differ and are disclosed on the pages. Company adjusted FCF and the Bloomberg displayed FCF are distinguished, as are customer commitments, received deposits and RPO.

Validation covers financial arithmetic, three-language parity, exact template comparison and mocked JavaScript execution. Real browser rendering was not completed because the cloud browser could not reach the local HTTP preview. No live AI request was submitted.

GitHub access was confirmed on 8 October; publishing uses a reviewable branch and the existing Vercel integration. Commit checks, PR status and the live website determine actual deployment status. CNAME, disclaimer.html, API code and deployment configuration are unchanged. Earlier handover corrections to other companies are outside this MU release.
