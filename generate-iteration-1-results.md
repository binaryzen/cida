# Generate Iteration 1 Results Site

Instructions for building the GitHub Pages site presenting CIDA iteration 1 findings.
Do not produce prose content until these instructions are complete and approved.

---

## Site Overview

**Repository structure:**
```
/docs                  ← GitHub Pages root
  index.html           ← Home / overview
  theory.html          ← Schwartz theory connection
  methodology.html     ← Pipeline and anti-circularity design
  results-structure.html  ← PCA eigenvalues + component geometry
  results-overlay.html    ← FEC and facet interest overlays
  results-comparison.html ← Alignment and divergence with prior work
  data.html            ← Downloads, methodology log, caveats
  assets/
    plots/             ← copied from output/*.html (embedded as iframes or inlined)
    css/
    js/
```

**Tech stack:** Static HTML/CSS with no build step required (GitHub Pages default).
Interactive plots are existing Plotly HTML files embedded as `<iframe>` elements.
All data tables rendered via a minimal JS table component (e.g. Tabulator or plain HTML).
No server-side code. No frameworks with build steps.

**Navigation:** Persistent top nav across all pages in order:
Overview → Theory → Methodology → Structure → Overlays → Comparison → Data

**Iteration labeling:** Every page header includes "Iteration 1 — 118th Congress (2023–2025)"
and a disclaimer banner:

> This is an exploratory, first-pass analysis. Labels assigned to latent dimensions
> are descriptive attempts to characterise an observed mathematical vector, not
> measurements of the named concept. All correlation magnitudes should be interpreted
> in the context of the caveats on the Methodology page.

---

## Page 1 — Overview (`index.html`)

### Purpose
Orient a reader who knows nothing about the project. Establish the core question,
the approach at a high level, and the three headline findings.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  CIDA  Congressional Interest Dimension Analysis     │
│  Iteration 1 · 118th Congress (2023–2025)           │
├─────────────────────────────────────────────────────┤
│  [nav: Overview | Theory | Methodology | ...]        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  H1: What drives Congressional voting               │
│      beyond party lines?                            │
│                                                     │
│  2–3 paragraph intro (see content spec below)       │
│                                                     │
├──────────┬──────────┬──────────────────────────────┤
│ Callout  │ Callout  │  Callout                     │
│ 70%      │ PC3 is   │  Establishment money         │
│ party    │ invisible│  funds both sides of         │
│ variance │ to NOMINATE│ foreign policy             │
├──────────┴──────────┴──────────────────────────────┤
│  [→ Start: Theory]   [→ Jump to Results]           │
└─────────────────────────────────────────────────────┘
```

### Content specification
- **H1**: Must be a question, not a conclusion.
- **Intro paragraphs**: Must mention (a) the 118th Congress, (b) that the method is
  unsupervised (no pre-defined dimensions), (c) that labels were assigned after the
  fact and carry caveats. Must NOT assert causal claims about financial influence.
- **Callout 1 — party variance**: State that party alignment accounts for ~70% of
  voting variance in both chambers (House: 70.5%, Senate: 67.4%) and that this
  replicates existing literature.
- **Callout 2 — PC3 novelty**: State that one House component (descriptively labelled
  "executive-power-skeptics-vs-bipartisan-hawks") is statistically uncorrelated with
  either dimension of DW-NOMINATE (r=−0.057 with dim2), suggesting it captures
  structure not previously formalised.
- **Callout 3 — financial structure**: State that PAC contributions from corporate,
  labour, and trade-association committees correlate positively with the same pole of
  the internationalism component, forming a cross-partisan financial alignment. Use
  the word "correlate" not "fund" or "drive."
- **Validation criteria**: All three callout statistics must cite their source file
  (`nominate_comparison.csv`, `eigenvalue_spectrum_*.html`, `interest_correlation_table.csv`).

---

## Page 2 — Theory (`theory.html`)

### Purpose
Ground the empirical findings in Schwartz's Theory of Basic Human Values (1992),
providing a theoretical framework that predicts orthogonal value dimensions should
exist and that explains why the found components are interpretable as values rather
than noise.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  H1: Values, not just votes                         │
├─────────────────────────────────────────────────────┤
│  Section 1: Schwartz circumplex (700–900 words)     │
│  [Figure: Schwartz circumplex diagram — SVG or PNG] │
│  [Caption with citation]                            │
├─────────────────────────────────────────────────────┤
│  Section 2: Mapping our components                  │
│  [2-column table: Component label | Schwartz region]│
├─────────────────────────────────────────────────────┤
│  Section 3: What the theory predicts and what       │
│             we observed (400–500 words)             │
├─────────────────────────────────────────────────────┤
│  Section 4: Limits of the mapping (200–300 words)   │
│             [prominent caveat box]                  │
└─────────────────────────────────────────────────────┘
```

### Content specification

**Section 1 — Schwartz circumplex:**
Must accurately describe the ten motivational value types and their circular
arrangement. Must cite: Schwartz, S.H. (1992). Universals in the content and
structure of values. *Advances in Experimental Social Psychology*, 25, 1–65.
Must explain the two bipolar axes:
  - Openness to Change ↔ Conservation
  - Self-Transcendence ↔ Self-Enhancement
Must mention that political behaviour research has applied the circumplex to
cross-national legislative data (cite at minimum: Piurko, Y., Schwartz, S.H., &
Davidov, E. (2011). Basic personal values and the meaning of left-right political
orientations in 20 countries. *Political Psychology*, 32(4), 537–561.)

**Section 2 — Component mapping table:**
| Component (descriptive label) | Schwartz axis | Relevant value types |
Must include all 5 components (4 House + 1 Senate-only). Descriptive labels must
appear in quotation marks with a footnote: "This label is an attempt to describe
an observed vector, not a measurement of the named concept."

Expected mapping (to be written into the page):
- party-alignment → Self-Enhancement (Power/Achievement) vs. Self-Transcendence
  (Universalism/Benevolence) on economic redistribution axis
- internationalism-vs-america-first → Universalism (world peace, equality across
  groups) vs. Security+Conformity (national security, in-group loyalty)
- security-hawks-vs-civil-libertarians → Security (order, protection) vs.
  Self-Direction+Stimulation (freedom, autonomy)
- executive-power-skeptics-vs-bipartisan-hawks → Conformity/Authority (institutional
  deference) vs. Self-Direction (resistance to concentrated authority); notable
  because this combines elements from opposite quadrants of the circumplex,
  which may explain why it is not captured by NOMINATE
- security-consensus-vs-institutional-skeptics (Senate) → Security vs. Self-Direction,
  with narrower population than House equivalent

**Section 3 — Predictions vs. observations:**
Must state that Schwartz's theory predicts these dimensions should be relatively
independent (orthogonal) — and that PCA by construction produces orthogonal components,
which is consistent with but does not confirm the theory.
Must state that the theory predicts the Security ↔ Self-Direction axis and the
Universalism ↔ In-group axis should be separable dimensions, which is what we observe
in PC1 vs. PC2.
Must NOT claim the data confirms Schwartz theory — only that the data is consistent
with it, and that the framework provides a useful interpretive lens.

**Section 4 — Limits of the mapping:**
Prominent caveat box must include:
- Schwartz theory describes individual psychological values; we are observing
  institutional voting behaviour. The mapping is analogical, not direct.
- Legislative voting conflates the legislator's personal values with constituent
  preferences, party pressure, and strategic considerations.
- The components are unlabelled mathematical vectors; any semantic label introduces
  interpretation. The Schwartz mapping is one possible interpretation.

**Validation criteria:**
- At least 2 academic citations with full bibliographic detail
- Schwartz circumplex diagram present with proper attribution
- All component labels in quotation marks on first use in each section
- Caveat box must appear before Section 2 closes or at top of Section 4
- No causal language ("drives," "causes," "reflects" should be "is consistent with,"
  "aligns with," "may correspond to")

---

## Page 3 — Methodology (`methodology.html`)

### Purpose
Explain the pipeline at a level sufficient for an informed reader to understand what
was measured, what choices were made, and specifically what was done to reduce
circular reasoning and confounding.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  H1: How we measured it                             │
├─────────────────────────────────────────────────────┤
│  Pipeline diagram (horizontal flow, SVG)            │
│  GovTrack → Matrix → PCA → HITL → MDS → FEC+Facets │
├─────────────────────────────────────────────────────┤
│  Section: Data sources (table)                      │
├─────────────────────────────────────────────────────┤
│  Section: Vote encoding and exclusions              │
├─────────────────────────────────────────────────────┤
│  Section: What we did to reduce circular reasoning  │
│  [numbered list with one item per measure]          │
├─────────────────────────────────────────────────────┤
│  Section: Known limitations                         │
│  [numbered list]                                    │
└─────────────────────────────────────────────────────┘
```

### Content specification

**Data sources table** must include:
| Source | What it provides | Access | Step |
|---|---|---|---|
| GovTrack.us | 118th Congress roll-call votes | Public, CC0 | Step 1 |
| Congress.gov API | CRS policy area per bill | Public API | Step 10a |
| FEC Bulk Downloads | Committee-to-candidate contributions (Schedule A) | Public, bulk CSV | Step 7 |
| Voteview.com | DW-NOMINATE ideal point scores | Public, CC0 | Step 11 |

**Vote encoding section** must state:
- Yea=+1, Nay=−1, Not Voting/Present/Absent=0
- The 0 encoding for absences is a known limitation (conflates strategic abstention
  with absence)
- 15 Senate and [n] House legislators excluded for <50% participation; all 13
  zero-participation Senate exclusions are the class of 2024 who took office after
  the 118th Congress ended (cite `threshold_audit.json`)
- Procedural vote categories excluded: quorum, procedural, leadership, election
- [n_house] House and [n_senate] Senate discretionary votes retained

**Anti-circularity measures section** must enumerate each measure as a numbered item:

1. **Unsupervised decomposition first.** PCA was run with no prior hypothesis about
   what dimensions would emerge. Component labels were assigned only after inspecting
   top-loading votes.

2. **Human labeling kept minimal.** Labels were assigned in a single pass by one
   analyst reviewing the 10 highest-loading votes per component. No iterative
   refinement was done to improve label fit.

3. **External validation against DW-NOMINATE.** Component scores were correlated with
   Voteview DW-NOMINATE scores for the 118th Congress after labeling. NOMINATE is an
   independently-derived ideal-point model computed by a different method on the same
   votes. Correlation values are in `nominate_comparison.csv`.

4. **CRS policy area as independent category validation.** Congress.gov CRS policy
   areas are assigned by the Congressional Research Service, not by this project.
   Correlating PCA scores with CRS categories provides a label-validation step using
   categories that were not available to the analyst when labels were assigned.
   Results in `crs_validation.csv`.

5. **FEC data is financially independent.** The campaign contribution data (FEC bulk
   Schedule A) was acquired after all component labels were set. Financial correlations
   were not used to name or refine the components.

6. **Acknowledged circularity.** The facet annotations (Step 10b) were designed after
   seeing the component structure and are therefore not independent validation. High
   facet-PCA correlations should be interpreted as internal consistency, not
   confirmation. They are presented on the Overlays page with this caveat.

**Known limitations section** must enumerate:
1. Not-Voting encoded as 0
2. Single Congress only (118th); multi-Congress replication not yet done
3. Facet annotations are not independent of component labels
4. FEC industry classification coarse (entity_type_desc + ORG_TP); dark money and
   501(c)(4) spending excluded
5. District economic composition not controlled in FEC correlations
6. Senate sample size (n=85) limits statistical power on secondary components
7. Descriptive labels are analyst interpretations; alternative labels are possible

**Validation criteria:**
- Anti-circularity list must contain exactly 6 items as specified above (not more,
  not fewer); additional limitations go in the Known Limitations section
- Each data source in the table must link to the actual source URL
- All exclusion counts must match `step_03_status.json` and `threshold_audit.json`
- No prose claims of causal influence in this section

---

## Page 4 — Results: Component Structure (`results-structure.html`)

### Purpose
Present the PCA output: how many dimensions were found, how much variance each
explains, what the geometric structure looks like, and who the representative
legislators are at each pole.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  H1: Latent structure of Congressional voting       │
│  Iteration 1 · 118th Congress                      │
├─────────────────────────────────────────────────────┤
│  Section: Variance explained                        │
│  [2-column: House scree plot | Senate scree plot]   │
│  [files: eigenvalue_spectrum_house.html,            │
│          eigenvalue_spectrum_senate.html]           │
│  [short text: PC counts, % variance]                │
├─────────────────────────────────────────────────────┤
│  Section: 2D component space                        │
│  [2-column: pca_space_house.html | pca_space_senate]│
│  [caveat banner below each plot]                    │
├─────────────────────────────────────────────────────┤
│  Section: 3D geometry (House PC2–4 only)            │
│  [full-width: pca_3d_house.html]                   │
│  [note: Senate 3D omitted — insufficient variance   │
│          in PC2 for interpretable structure]        │
├─────────────────────────────────────────────────────┤
│  Section: SSA geometry                              │
│  [2-column: ssa_geometry_house | ssa_geometry_senate│
│  [explanation of cross-pattern finding]             │
├─────────────────────────────────────────────────────┤
│  Section: Representative legislators per pole       │
│  [tables: top 10 per component pole, both chambers] │
│  [data: loadings_house.csv, loadings_senate.csv,    │
│          scores_house.csv, scores_senate.csv]       │
└─────────────────────────────────────────────────────┘
```

### Content specification

**Variance explained text** must state exact figures:
- House: 4 components retained; PC0=70.5%, PC1=6.2%, PC2=1.9%, PC3=1.4%
- Senate: 3 components retained; PC0=67.4%, PC1=5.4%, PC2=2.2%
- Parallel analysis used to determine number of retained components

**Component labels caveat banner** (must appear directly below each plot containing
labelled axes):
> Component labels (e.g. "internationalism-vs-america-first") are descriptive
> shorthand assigned by analyst inspection of top-loading votes. They describe
> the observed direction of the vector, not a measurement of the named concept.
> Axis magnitudes are arbitrary; only relative positions and directions are
> interpretable.

**2D plots text** — for each component pair displayed, must include:
- Which votes load most strongly on each pole (top 3–5 vote descriptions)
- Which legislators are near the extremes
- A statement about what is NOT being claimed (e.g. "this does not measure patriotism
  or loyalty; it describes a pattern in vote co-occurrence")

**3D House plot** — must include:
- Note that PC0 (party-alignment) is excluded from this visualisation; it is shown
  separately in the 2D plot
- Instructions on how to interact (rotate, hover for names)
- Statement that 3D visualisation is exploratory; the structure is clearer in the
  2D projections

**SSA cross-pattern finding** — text must describe:
- The cross pattern: Republican intra-party variance primarily aligned with the
  internationalism axis; Democrat intra-party variance primarily aligned with the
  security/civil-liberties axis
- That these axes are roughly orthogonal to each other
- The 5-senator Senate outlier cluster (Scott, Schmitt, Tuberville + 2 others)
  identified in SSA before clustering
- Kruskal stress values from `step_06_status.json`

**Representative legislators table** — generated from `scores_house.csv` and
`scores_senate.csv`. For each non-party component, show top 5 legislators at each
pole. Table columns: Name, Party, State, Score. Must include a note that scores
are standardised and that a legislator appearing at an extreme means their voting
pattern is most consistent with that pole — it does not indicate intent or ideology.

**Validation criteria:**
- All 6 interactive Plotly plots embedded (2 scree, 2 PCA 2D, 1 3D, 2 SSA)
- Caveat banner present below every labelled-axis plot
- Representative legislators tables sourced from CSV data, not hardcoded
- Kruskal stress values present and sourced from `step_06_status.json`
- Senate 3D omission explained

---

## Page 5 — Results: Interest Overlays (`results-overlay.html`)

### Purpose
Present the two interest-alignment layers — FEC campaign finance and vote facet
annotations — and be explicit about which is independent of the component labels
and which is not.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  H1: Whose interests align with each dimension?     │
├─────────────────────────────────────────────────────┤
│  [Prominent framing box: two kinds of evidence]     │
├─────────────────────────────────────────────────────┤
│  Section A: FEC campaign finance (independent)      │
│  [2-column heatmaps:                                │
│   interest_correlation_heatmap_house.html           │
│   interest_correlation_heatmap_senate.html]         │
│  [Key finding text]                                 │
│  [Table: top 10 FEC correlations, non-party comps]  │
├─────────────────────────────────────────────────────┤
│  Section B: Vote facet annotations (NOT independent)│
│  [prominent caveat box first]                       │
│  [Table: top facet-PCA correlations]                │
│  [Explanation of what they add vs. not]             │
├─────────────────────────────────────────────────────┤
│  Section C: CRS policy areas (independent)          │
│  [Table: top CRS correlations]                      │
└─────────────────────────────────────────────────────┘
```

### Content specification

**Framing box** must state:
> This page presents two categories of evidence with different epistemological status.
> FEC financial data and CRS policy areas were acquired from external sources after
> component labels were finalised — they are independent validation signals.
> Vote facet annotations were designed by the analyst after seeing the component
> structure and are therefore not independent. High facet-PCA correlations indicate
> internal consistency, not confirmation.

**Section A — FEC findings** must state:
- Source: FEC bulk Schedule A (pas2 files), cycles 2022 and 2024, 522 legislators
  matched (99.3% of matrix legislators), `fec_receipts` table
- Industry classification based on FEC `ORG_TP` (organisation type) and `CMTE_TP`
  (committee type). Known limitation: dark money and 501(c)(4) spending excluded;
  `entity_type_desc` used for unlabelled committees.
- Key finding: For House PC1 ("internationalism-vs-america-first"), contributions from
  Membership Organisations (r=0.445), Corporations (r=0.360), Trade Associations
  (r=0.319), and Labor Organisations (r=0.286) all correlate positively with the same
  pole. This cross-partisan financial alignment is the primary FEC finding.
- Key finding: House PC3 ("executive-power-skeptics") shows a different financial
  profile — Super PAC (r=0.341) and non-qualified party committees (r=0.330), not
  traditional PACs. Text must note this may reflect anti-establishment financial
  networks rather than industry influence.
- Must include statement: Correlation with financial contributions does not establish
  that contributions cause voting patterns. District economic composition was not
  controlled; legislators from industries concentrated in their districts will show
  both higher industry contributions and industry-aligned votes for constituency
  reasons.

**Section B — Facet annotation caveat box** must be styled differently (e.g. amber
background) and state:
> The 16 policy facets below were designed by the analyst after inspecting the PCA
> output. The high correlations (e.g. nato_alliance r=0.83 with House PC1) indicate
> that the facet coding was internally consistent with the component structure — not
> that the component independently measures NATO alignment. These results are presented
> for completeness and interpretive texture, not as validation.

**Section B — Facet table** sourced from `facet_pca_correlations.csv`. Show top 10
non-party correlations. Include columns: Chamber, Component, Facet, r.

**Section C — CRS validation** must note:
- CRS policy areas assigned by Congressional Research Service, not by this project
- Coverage: 290,115 vote-positions with CRS area across 25 policy areas
- Key finding for Senate PC1: top correlations are "Economics and Public Finance"
  (r=0.527), "Transportation and Public Works" (r=0.496), "Public Lands and Natural
  Resources" (r=0.452) — domestic spending categories not used in labeling, suggesting
  the Senate dimension has a broader institutionalist character beyond foreign policy
- Source: `crs_validation.csv`

**Validation criteria:**
- Both heatmap plots embedded
- Framing box present before Section A
- Facet caveat box styled distinctly from body text and appears before facet data
- All r values sourced from named CSV files
- No causal language ("causes," "drives," "buys") in financial sections
- District-composition confound acknowledged in Section A

---

## Page 6 — Results: Comparison with Prior Work (`results-comparison.html`)

### Purpose
Compare CIDA findings with DW-NOMINATE (Poole & Rosenthal tradition) and Ferguson's
investment theory. Be precise about where we align, where we extend, and where we
genuinely diverge — without overclaiming novelty.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  H1: Where CIDA agrees and disagrees with           │
│      established findings                           │
├─────────────────────────────────────────────────────┤
│  Section: The NOMINATE comparison                   │
│  [Table: our components vs NOMINATE dim1/dim2 r²]   │
│  [Scatter: our PC0 vs NOMINATE dim1, both chambers] │
├─────────────────────────────────────────────────────┤
│  Section: What NOMINATE sees the same way           │
├─────────────────────────────────────────────────────┤
│  Section: What NOMINATE sees differently            │
├─────────────────────────────────────────────────────┤
│  Section: The Ferguson investment theory connection  │
├─────────────────────────────────────────────────────┤
│  Section: Open questions                            │
└─────────────────────────────────────────────────────┘
```

### Content specification

**NOMINATE comparison table** sourced from `nominate_comparison.csv`. Must show r and
r² for each of our components against both NOMINATE dimensions. Must include n for
each chamber.

**"Agrees" section** must cover:
- One-dimensionality of modern Congress: Our PC0 r=0.982 with NOMINATE dim1 (House),
  r=−0.968 (Senate sign-flip due to encoding). Both approaches find party alignment
  accounts for ~70% of roll-call variance. Cite Poole & Rosenthal (1997).
- Weakness of secondary dimensions: NOMINATE dim2 has been noted in the literature as
  weak and unlabelled in the post-1980 Congress. Our secondary components explain only
  1.4–6.2% each, consistent with this characterisation.
- Senate Paul/Lee/Hawley-adjacent outlier cluster: Qualitatively consistent with
  observations in the post-2016 literature about Senate libertarian-nationalist votes.

**"Sees differently" section** must cover:
- House PC3 (executive-power-skeptics) r²=0.003 with NOMINATE dim1, r²=0.003 with
  NOMINATE dim2. This component is essentially orthogonal to both NOMINATE dimensions.
  Must state: "This could mean PC3 captures genuine novel structure, or that it
  captures structured noise in a part of the vote space NOMINATE discounts. Replication
  across additional Congresses would be required to distinguish these."
- CRS validation of Senate PC1: Top CRS correlates (Economics, Transportation, Public
  Lands) suggest the Senate "internationalism" dimension has a domestic-spending
  character that does not obviously correspond to any established label. The component
  may be better described as "institutionalist fiscal alignment" than pure foreign policy.
- NOMINATE's single second dimension vs. our 3: Our analysis finds that what NOMINATE
  compresses into one weak second dimension may contain at least two separable signals
  (internationalism r²=0.461, security-hawks r²=0.224 against NOMINATE dim2 in the
  House), though with the caveat that both could be partly the same underlying gradient
  seen from different angles.

**Ferguson investment theory section** must cover:
- Cite: Ferguson, T. (1995). *Golden Rule: The Investment Theory of Party Competition
  and the Logic of Money-Driven Political Systems.* University of Chicago Press.
- Cite at least one recent INET paper (Ferguson, Jorgensen, Chen).
- Connection: Ferguson argues that on international economic policy, a bipartisan
  investor coalition exists that transcends the domestic left-right divide. Our FEC
  finding — that corporate, labour, trade-association, and membership-organisation
  contributions all correlate with the same pole of the internationalism component —
  is consistent with this claim.
- Limitation: We cannot distinguish investor coordination from shared district-level
  interests. Ferguson's claim requires demonstrating influence, not merely correlation.

**Open questions section** must list at minimum:
1. Would PC3 replicate in the 115th, 116th, 117th Congress? If not, it may be
   specific to the 118th.
2. Is the Senate PC1 "institutionalist fiscal alignment" pattern a stable feature or
   an artefact of the small Senate sample and specific 118th Congress dynamics?
3. Does controlling for district economic composition eliminate the FEC financial
   correlations, or do they survive as an independent signal?

**Validation criteria:**
- NOMINATE comparison table present and sourced from `nominate_comparison.csv`
- All r² values in text match values in `nominate_comparison.csv` (pearson_r²)
- Ferguson citation complete with publisher and year
- At least 4 academic citations total with full bibliographic detail
- PC3 novelty claim explicitly hedged with replication caveat
- No section titled "What CIDA discovered" or equivalent triumphalist framing

---

## Page 7 — Data (`data.html`)

### Purpose
Provide downloads of all output files, the full methodology log, and a reference
table of every threshold and design choice made in the pipeline.

### Layout wireframe
```
┌─────────────────────────────────────────────────────┐
│  H1: Data and methodology                           │
├─────────────────────────────────────────────────────┤
│  Section: Downloads                                 │
│  [table of files with description and format]       │
├─────────────────────────────────────────────────────┤
│  Section: Design choices and thresholds             │
│  [table: choice | value | rationale | source]       │
├─────────────────────────────────────────────────────┤
│  Section: LLM cost accounting                       │
├─────────────────────────────────────────────────────┤
│  Section: Full methodology log                      │
│  [rendered markdown from methodology_log.md]        │
└─────────────────────────────────────────────────────┘
```

### Content specification

**Downloads table** must include all of the following files with description:

| File | Description | Format |
|---|---|---|
| `scores_house.csv` | Legislator PCA scores, House | CSV |
| `scores_senate.csv` | Legislator PCA scores, Senate | CSV |
| `loadings_house.csv` | Vote loadings per component, House | CSV |
| `loadings_senate.csv` | Vote loadings per component, Senate | CSV |
| `facet_pca_correlations.csv` | Facet-component correlations | CSV |
| `interest_correlation_table.csv` | FEC industry-component correlations | CSV |
| `nominate_comparison.csv` | CIDA vs DW-NOMINATE correlations | CSV |
| `crs_validation.csv` | CRS policy area correlations | CSV |
| `cluster_summary_table.csv` | Cluster membership and composition | CSV |
| `component_labels.json` | Human-assigned component labels | JSON |
| `threshold_audit.json` | Senate participation threshold audit | JSON |
| `methodology_log.md` | Full pipeline methodology log | Markdown |

**Design choices table** must include:

| Choice | Value | Rationale |
|---|---|---|
| Participation threshold | 50% | Excludes legislators absent >half of votes; all 118th exclusions are post-Congress class or near-zero-coverage mid-term replacements |
| Vote encoding | +1/−1/0 | Standard; 0 for absences is a known limitation |
| Components retained | 4 (House), 3 (Senate) | Parallel analysis |
| MDS distance metric | Euclidean on PC1+ | Correlation distance produces circle artefact on orthogonal components |
| MDS input dimensions | PC1+ only (PC0 excluded) | Including party dimension produces horseshoe artefact |
| FEC cycles | 2022, 2024 | Spans 118th Congress |
| FEC source | Bulk download (pas2+cm files) | No rate limiting; complete coverage |
| Industry classification | ORG_TP (fallback: CMTE_TP) | Inline in committee master; dark money excluded |

**LLM cost accounting section** must state:
- Haiku annotation swarm: ~950,000 tokens estimated (9 of 28 batches measured;
  remainder estimated from average), model claude-haiku-4-5-20251001,
  estimated cost ~$1.22
- HITL interactive labeling: conducted in claude-sonnet-4-6 conversational session;
  token count not separable from analytical discussion; Sonnet-tier pricing applies
  (~$0.50–$3.00 estimated)
- Total estimated LLM cost for iteration 1: $1.72–$4.22
- Source: `methodology_log.md` LLM cost accounting section

**Validation criteria:**
- All 12 files in downloads table present as actual downloadable links
- Design choices table complete with all 8 rows listed above
- LLM cost section present with model names and cost estimates
- Methodology log rendered (not just linked) so it is searchable on-page
- No design choice listed without a rationale

---

## Global validation checklist

Before the site is considered complete, verify:

- [ ] All 7 pages present and linked from nav
- [ ] All 6 interactive Plotly plots embedded (`eigenvalue_spectrum_*.html`,
      `pca_space_*.html`, `pca_3d_house.html`, `ssa_geometry_*.html`,
      `interest_correlation_heatmap_*.html`)
- [ ] Iteration banner ("Iteration 1 · 118th Congress (2023–2025)") on every page
- [ ] Disclaimer banner on every page (exact text specified in Site Overview)
- [ ] Component label caveat appears on every page that uses a label
- [ ] Facet annotation caveat styled distinctly on Overlays page
- [ ] All r values in prose traceable to a named source file
- [ ] All citations on Theory and Comparison pages have author, year, title, venue
- [ ] No causal language in any financial or influence claim
- [ ] Downloads table links resolve
- [ ] Site renders correctly without JavaScript disabled (plots degrade gracefully
      to static fallbacks if possible)
- [ ] No hardcoded statistics that are also in CSV files — all numbers either
      rendered from data at build time or explicitly annotated "as of iteration 1"
