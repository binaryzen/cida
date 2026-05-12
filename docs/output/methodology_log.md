# CIDA Methodology Log

## 2026-05-10T22:26:09.583490 — Step 0: Setup
- db_created: true
- tables_created: 5

## 2026-05-10T22:26:33.033687 — Step 1: Acquire GovTrack
- legislators: 536
- house_votes: 0
- senate_votes: 0
- votes_skipped: 0
- status: failed

Skipped voters for 2023-06-13T17:48:00: 502 Server Error: Bad Gateway for url: https://www.govtrack.us/api/v2/vote_voter?created=2023-06-13T17%3A48%3A00&limit=700
Skipped voters for 2023-06-14T11:39:00: 502 Server Error: Bad Gateway for url: https://www.govtrack.us/api/v2/vote_voter?created=2023-06-14T11%3A39%3A00&limit=700
Skipped voters for 2024-04-16T16:47:00: 502 Server Error: Bad Gateway for url: https://www.govtrack.us/api/v2/vote_voter?created=2024-04-16T16%3A47%3A00&limit=700
## 2026-05-11T00:07:54.416820 — Step 1: Acquire GovTrack
- legislators: 536
- house_votes: 1241
- senate_votes: 691
- total_positions: 607881
- status: ok

## 2026-05-11T00:08:01.155318 — Step 2: Filter Votes
- house_total: 1241
- house_excluded: 444
- house_included: 797
- house_exclusion_pct: 35.78
- senate_total: 691
- senate_excluded: 93
- senate_included: 598
- senate_exclusion_pct: 13.46

## 2026-05-11T00:08:06.638644 — Step 3: Build Matrix
- house_n_legislators: 354
- house_n_votes: 797
- house_excluded_legislators: 82
- house_matrix_shape: 354x797
- senate_n_legislators: 85
- senate_n_votes: 598
- senate_excluded_legislators: 15
- senate_matrix_shape: 85x598

## 2026-05-11T00:10:52.606183 — Step 4: PCA (house)
- house_retained_components: 4
- house_pc1_party_r2: 0.9682
- house_eigenvalue_1: 563.5919
- house_retained_indices: [0, 1, 2, 3]

## 2026-05-11T00:11:22.472407 — Step 4: PCA (senate)
- senate_retained_components: 3
- senate_pc1_party_r2: 0.9298
- senate_eigenvalue_1: 406.465
- senate_retained_indices: [0, 1, 2]

## 2026-05-11T00:12:17.674610 — Step 6: SSA Geometry
- house_mds_dims: 2
- house_kruskal_stress: 0.0003
- house_stress_warning: no
- senate_mds_dims: 2
- senate_kruskal_stress: 0.0006
- senate_stress_warning: no

## 2026-05-11T00:33:25.496702 — Step 6: SSA Geometry
- house_mds_dims: 2
- house_kruskal_stress: 0.0003
- house_stress_warning: no
- senate_mds_dims: 2
- senate_kruskal_stress: 0.0006
- senate_stress_warning: no


**Step 09 [2026-05-11T00:33:27.966752]**: house: HDBSCAN(min_cluster_size=17), silhouette=0.765
**Step 09 [2026-05-11T00:33:58.463845]**: house: HDBSCAN(min_cluster_size=17), silhouette=0.765
**Step 09 [2026-05-11T00:33:58.857437]**: senate: HDBSCAN(min_cluster_size=5), silhouette=0.737
**Step 09 [2026-05-11T00:33:59.176377]**: No cluster has >= 10% minority-party membership## 2026-05-11T00:50:55.017712 — Step 6: SSA Geometry
- house_mds_dims: 2
- house_kruskal_stress: 0.0001
- house_stress_warning: no
- senate_mds_dims: 2
- senate_kruskal_stress: 0.0003
- senate_stress_warning: no

## 2026-05-11T01:01:05.085912 — Step 6: SSA Geometry
- house_mds_dims: 2
- house_kruskal_stress: 0.0001
- house_stress_warning: no
- senate_mds_dims: 2
- senate_kruskal_stress: 0.0001
- senate_stress_warning: no


## 2026-05-11T02:02:26.350586 — Step 10: Vote Annotation
- annotated_votes: 1395
- facets: 16
- facet_pca_correlations_above_0.10: 77


**Step 09 [2026-05-11T02:12:11.047010]**: house: HDBSCAN(min_cluster_size=17), silhouette=0.765
**Step 09 [2026-05-11T02:12:14.245050]**: senate: HDBSCAN(min_cluster_size=5), silhouette=0.737
**Step 09 [2026-05-11T02:12:14.477753]**: No cluster has >= 10% minority-party membership
## 2026-05-11T02:13:20.946415 — LLM Cost Accounting

### Step 10b: Haiku annotation swarm (28 parallel agents x claude-haiku-4-5-20251001)
- batches_total: 28
- votes_annotated: 1395
- facets_per_vote: 16
- token_data_source: task_notifications (batches 19-27 measured; batches 0-18 estimated from average)
- tokens_measured_9_batches: 305403
- avg_tokens_per_batch: 33934
- total_tokens_estimated: 950143
- assumed_split: 85% input / 15% output
- cost_model: input=0.80/M, output=4.00/M
- haiku_swarm_cost_usd_estimated: 1.22

### Step 5: HITL interactive labeling (claude-sonnet-4-6)
- method: conversational HITL via Claude Code
- components_labeled: 4 house + 3 senate = 7
- token_data_source: unavailable (session compacted before cost extraction)
- cost_model: input=3.00/M, output=15.00/M
- hitl_cost_usd: not_measured
- note: labeling embedded in broader analytical session; tokens not separable

### Iteration total
- haiku_swarm_usd: 1.22
- hitl_usd: unmeasured (Sonnet-tier; rough order-of-magnitude: 0.50-3.00)
- total_estimated_range_usd: 1.72 - 4.22


## 2026-05-11T02:54:28.482346 — Step 7: FEC acquisition blocked by rate limit

- status: deferred_rate_limited
- fec_api_limit: 1000_requests_per_hour
- calls_needed: ~2140 (535 legislators x 2 cycles x 4 calls each)
- issue: three prior failed/killed runs consumed the hourly quota before successful run could complete
- records_acquired: 0
- recommendation: run step_07 in a fresh hour window; add exponential backoff + per-run request budget cap
- note: facet_pca_correlations.csv (step 10c) provides a complete interest overlay via vote annotation and is sufficient for iteration-1 interpretation

**2026-05-11T02:54:32.871864** — Step 8: No correlations computed — insufficient data
**2026-05-11T02:54:32.872720** — Step 8: OK
**Step 09 [2026-05-11T02:54:34.814226]**: house: HDBSCAN(min_cluster_size=17), silhouette=0.765
**Step 09 [2026-05-11T02:54:35.173590]**: senate: HDBSCAN(min_cluster_size=5), silhouette=0.737
**Step 09 [2026-05-11T02:54:35.350636]**: No cluster has >= 10% minority-party membership
## 2026-05-11T03:00:38.999504 — Step 7: Acquire FEC (bulk download)
- source: fec.gov bulk files pas2{yy}.zip + cm{yy}.zip
- cycles: [2022, 2024]
- industry_field: ORG_TP (fallback: CMTE_TP)
- legislators_matched: 522
- receipt_records: 10,140
- match_rate: 99.32%


**2026-05-11T03:00:44.693555** — HOUSE PC0 (party-alignment) — Labor Organization: r=-0.638, p=0.0000
**2026-05-11T03:00:44.694205** — HOUSE PC0 (party-alignment) — Super PAC hybrid: r=-0.347, p=0.0000
**2026-05-11T03:00:44.694931** — HOUSE PC0 (party-alignment) — Super PAC (non-contrib): r=-0.222, p=0.0000
**2026-05-11T03:00:44.695382** — HOUSE PC0 (party-alignment) — Senate campaign: r=-0.204, p=0.0001
**2026-05-11T03:00:44.695973** — HOUSE PC0 (party-alignment) — Party - state (NQ): r=-0.184, p=0.0005
**2026-05-11T03:00:44.696804** — HOUSE PC0 (party-alignment) — Trade Association: r=0.208, p=0.0001
**2026-05-11T03:00:44.697195** — HOUSE PC0 (party-alignment) — PAC w/ non-contrib acct: r=0.243, p=0.0000
**2026-05-11T03:00:44.697631** — HOUSE PC0 (party-alignment) — House campaign: r=0.245, p=0.0000
**2026-05-11T03:00:44.698061** — HOUSE PC0 (party-alignment) — Non-connected PAC: r=0.265, p=0.0000
**2026-05-11T03:00:44.698487** — HOUSE PC0 (party-alignment) — Other: r=nan, p=nan
**2026-05-11T03:00:44.699843** — HOUSE PC1 (internationalism-vs-america-first) — Presidential campaign: r=0.028, p=0.6006
**2026-05-11T03:00:44.700279** — HOUSE PC1 (internationalism-vs-america-first) — Single-candidate IE: r=0.094, p=0.0777
**2026-05-11T03:00:44.700752** — HOUSE PC1 (internationalism-vs-america-first) — PAC w/ non-contrib acct: r=0.104, p=0.0501
**2026-05-11T03:00:44.701078** — HOUSE PC1 (internationalism-vs-america-first) — Party - national (NQ): r=0.119, p=0.0252
**2026-05-11T03:00:44.701414** — HOUSE PC1 (internationalism-vs-america-first) — Cooperative: r=0.131, p=0.0136
**2026-05-11T03:00:44.702041** — HOUSE PC1 (internationalism-vs-america-first) — Super PAC hybrid: r=0.311, p=0.0000
**2026-05-11T03:00:44.702421** — HOUSE PC1 (internationalism-vs-america-first) — Trade Association: r=0.319, p=0.0000
**2026-05-11T03:00:44.702900** — HOUSE PC1 (internationalism-vs-america-first) — Corporation: r=0.360, p=0.0000
**2026-05-11T03:00:44.703273** — HOUSE PC1 (internationalism-vs-america-first) — Membership Organization: r=0.445, p=0.0000
**2026-05-11T03:00:44.703696** — HOUSE PC1 (internationalism-vs-america-first) — Other: r=nan, p=nan
**2026-05-11T03:00:44.705325** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Party - national (NQ): r=0.027, p=0.6185
**2026-05-11T03:00:44.706037** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — PAC w/ non-contrib acct: r=0.039, p=0.4618
**2026-05-11T03:00:44.706531** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Super PAC: r=0.059, p=0.2688
**2026-05-11T03:00:44.706977** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Labor Organization: r=0.060, p=0.2614
**2026-05-11T03:00:44.707424** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Single-candidate IE: r=0.072, p=0.1801
**2026-05-11T03:00:44.708021** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Corporation: r=0.246, p=0.0000
**2026-05-11T03:00:44.708344** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Senate campaign: r=0.279, p=0.0000
**2026-05-11T03:00:44.708670** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Trade Association: r=0.319, p=0.0000
**2026-05-11T03:00:44.708975** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Membership Organization: r=0.367, p=0.0000
**2026-05-11T03:00:44.709279** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Other: r=nan, p=nan
**2026-05-11T03:00:44.710535** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Corporation: r=-0.221, p=0.0000
**2026-05-11T03:00:44.710901** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Cooperative: r=-0.159, p=0.0028
**2026-05-11T03:00:44.711217** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Corp w/o Capital Stock: r=-0.144, p=0.0068
**2026-05-11T03:00:44.711521** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Trade Association: r=-0.129, p=0.0152
**2026-05-11T03:00:44.711839** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Labor Organization: r=-0.128, p=0.0161
**2026-05-11T03:00:44.712396** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Non-connected PAC: r=0.257, p=0.0000
**2026-05-11T03:00:44.712748** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Super PAC (non-contrib): r=0.293, p=0.0000
**2026-05-11T03:00:44.713072** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Party - state (NQ): r=0.329, p=0.0000
**2026-05-11T03:00:44.713551** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Super PAC: r=0.341, p=0.0000
**2026-05-11T03:00:44.714032** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Other: r=nan, p=nan
**2026-05-11T03:00:44.819986** — SENATE PC0 (party-alignment) — PAC w/ non-contrib acct: r=-0.196, p=0.0757
**2026-05-11T03:00:44.820425** — SENATE PC0 (party-alignment) — Cooperative: r=-0.167, p=0.1307
**2026-05-11T03:00:44.821087** — SENATE PC0 (party-alignment) — Trade Association: r=-0.160, p=0.1495
**2026-05-11T03:00:44.821548** — SENATE PC0 (party-alignment) — Multi-candidate PAC: r=-0.140, p=0.2071
**2026-05-11T03:00:44.822042** — SENATE PC0 (party-alignment) — Corporation: r=-0.103, p=0.3554
**2026-05-11T03:00:44.822891** — SENATE PC0 (party-alignment) — Presidential campaign: r=0.159, p=0.1508
**2026-05-11T03:00:44.823321** — SENATE PC0 (party-alignment) — Super PAC (non-contrib): r=0.208, p=0.0592
**2026-05-11T03:00:44.823827** — SENATE PC0 (party-alignment) — House campaign: r=0.220, p=0.0454
**2026-05-11T03:00:44.824311** — SENATE PC0 (party-alignment) — Labor Organization: r=0.428, p=0.0001
**2026-05-11T03:00:44.825073** — SENATE PC0 (party-alignment) — Other: r=nan, p=nan
**2026-05-11T03:00:44.826904** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — House campaign: r=-0.313, p=0.0039
**2026-05-11T03:00:44.827512** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Party - national (NQ): r=-0.269, p=0.0138
**2026-05-11T03:00:44.828035** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Party - state (NQ): r=-0.225, p=0.0407
**2026-05-11T03:00:44.828372** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Senate campaign: r=-0.185, p=0.0938
**2026-05-11T03:00:44.828714** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Super PAC: r=-0.164, p=0.1395
**2026-05-11T03:00:44.829319** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Presidential campaign: r=-0.015, p=0.8921
**2026-05-11T03:00:44.829703** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Corporation: r=0.036, p=0.7491
**2026-05-11T03:00:44.830083** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Cooperative: r=0.126, p=0.2558
**2026-05-11T03:00:44.830482** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Corp w/o Capital Stock: r=0.188, p=0.0890
**2026-05-11T03:00:44.830824** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Other: r=nan, p=nan
**2026-05-11T03:00:44.832083** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — PAC w/ non-contrib acct: r=-0.128, p=0.2502
**2026-05-11T03:00:44.832565** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Membership Organization: r=-0.099, p=0.3752
**2026-05-11T03:00:44.832884** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Super PAC: r=-0.079, p=0.4788
**2026-05-11T03:00:44.833168** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Non-connected PAC: r=-0.067, p=0.5465
**2026-05-11T03:00:44.833458** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Multi-candidate PAC: r=-0.042, p=0.7048
**2026-05-11T03:00:44.834019** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Presidential campaign: r=0.051, p=0.6469
**2026-05-11T03:00:44.834401** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Cooperative: r=0.053, p=0.6355
**2026-05-11T03:00:44.834742** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Senate campaign: r=0.063, p=0.5699
**2026-05-11T03:00:44.835025** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Party - national (NQ): r=0.091, p=0.4133
**2026-05-11T03:00:44.835301** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Other: r=nan, p=nan
**2026-05-11T03:00:44.849353** — Step 8: OK
**Step 09 [2026-05-11T03:00:47.237034]**: house: HDBSCAN(min_cluster_size=17), silhouette=0.765
**Step 09 [2026-05-11T03:00:47.585759]**: senate: HDBSCAN(min_cluster_size=5), silhouette=0.737
**Step 09 [2026-05-11T03:00:47.796556]**: No cluster has >= 10% minority-party membership
**2026-05-11T03:02:28.163312** — HOUSE PC0 (party-alignment) — Labor Organization: r=-0.638, p=0.0000
**2026-05-11T03:02:28.163743** — HOUSE PC0 (party-alignment) — Super PAC hybrid: r=-0.347, p=0.0000
**2026-05-11T03:02:28.164126** — HOUSE PC0 (party-alignment) — Super PAC (non-contrib): r=-0.222, p=0.0000
**2026-05-11T03:02:28.164479** — HOUSE PC0 (party-alignment) — Senate campaign: r=-0.204, p=0.0001
**2026-05-11T03:02:28.165142** — HOUSE PC0 (party-alignment) — Party - state (NQ): r=-0.184, p=0.0005
**2026-05-11T03:02:28.165941** — HOUSE PC0 (party-alignment) — Multi-candidate PAC: r=0.157, p=0.0031
**2026-05-11T03:02:28.166333** — HOUSE PC0 (party-alignment) — Trade Association: r=0.208, p=0.0001
**2026-05-11T03:02:28.166696** — HOUSE PC0 (party-alignment) — PAC w/ non-contrib acct: r=0.243, p=0.0000
**2026-05-11T03:02:28.167051** — HOUSE PC0 (party-alignment) — House campaign: r=0.245, p=0.0000
**2026-05-11T03:02:28.167600** — HOUSE PC0 (party-alignment) — Non-connected PAC: r=0.265, p=0.0000
**2026-05-11T03:02:28.169034** — HOUSE PC1 (internationalism-vs-america-first) — Presidential campaign: r=0.028, p=0.6006
**2026-05-11T03:02:28.169405** — HOUSE PC1 (internationalism-vs-america-first) — Single-candidate IE: r=0.094, p=0.0777
**2026-05-11T03:02:28.169847** — HOUSE PC1 (internationalism-vs-america-first) — PAC w/ non-contrib acct: r=0.104, p=0.0501
**2026-05-11T03:02:28.170531** — HOUSE PC1 (internationalism-vs-america-first) — Party - national (NQ): r=0.119, p=0.0252
**2026-05-11T03:02:28.171358** — HOUSE PC1 (internationalism-vs-america-first) — Cooperative: r=0.131, p=0.0136
**2026-05-11T03:02:28.172142** — HOUSE PC1 (internationalism-vs-america-first) — Multi-candidate PAC: r=0.306, p=0.0000
**2026-05-11T03:02:28.172518** — HOUSE PC1 (internationalism-vs-america-first) — Super PAC hybrid: r=0.311, p=0.0000
**2026-05-11T03:02:28.172860** — HOUSE PC1 (internationalism-vs-america-first) — Trade Association: r=0.319, p=0.0000
**2026-05-11T03:02:28.173267** — HOUSE PC1 (internationalism-vs-america-first) — Corporation: r=0.360, p=0.0000
**2026-05-11T03:02:28.173646** — HOUSE PC1 (internationalism-vs-america-first) — Membership Organization: r=0.445, p=0.0000
**2026-05-11T03:02:28.175049** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Party - national (NQ): r=0.027, p=0.6185
**2026-05-11T03:02:28.175467** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — PAC w/ non-contrib acct: r=0.039, p=0.4618
**2026-05-11T03:02:28.175986** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Super PAC: r=0.059, p=0.2688
**2026-05-11T03:02:28.176565** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Labor Organization: r=0.060, p=0.2614
**2026-05-11T03:02:28.177089** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Single-candidate IE: r=0.072, p=0.1801
**2026-05-11T03:02:28.177757** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Multi-candidate PAC: r=0.231, p=0.0000
**2026-05-11T03:02:28.178237** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Corporation: r=0.246, p=0.0000
**2026-05-11T03:02:28.178551** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Senate campaign: r=0.279, p=0.0000
**2026-05-11T03:02:28.178822** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Trade Association: r=0.319, p=0.0000
**2026-05-11T03:02:28.179102** — HOUSE PC2 (security-hawks-vs-civil-libertarians) — Membership Organization: r=0.367, p=0.0000
**2026-05-11T03:02:28.180359** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Corporation: r=-0.221, p=0.0000
**2026-05-11T03:02:28.180693** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Cooperative: r=-0.159, p=0.0028
**2026-05-11T03:02:28.180979** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Corp w/o Capital Stock: r=-0.144, p=0.0068
**2026-05-11T03:02:28.181278** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Trade Association: r=-0.129, p=0.0152
**2026-05-11T03:02:28.181560** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Labor Organization: r=-0.128, p=0.0161
**2026-05-11T03:02:28.182056** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — PAC w/ non-contrib acct: r=0.249, p=0.0000
**2026-05-11T03:02:28.182358** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Non-connected PAC: r=0.257, p=0.0000
**2026-05-11T03:02:28.182650** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Super PAC (non-contrib): r=0.293, p=0.0000
**2026-05-11T03:02:28.182944** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Party - state (NQ): r=0.329, p=0.0000
**2026-05-11T03:02:28.183417** — HOUSE PC3 (executive-power-skeptics-vs-bipartisan-hawks) — Super PAC: r=0.341, p=0.0000
**2026-05-11T03:02:28.296288** — SENATE PC0 (party-alignment) — PAC w/ non-contrib acct: r=-0.196, p=0.0757
**2026-05-11T03:02:28.296717** — SENATE PC0 (party-alignment) — Cooperative: r=-0.167, p=0.1307
**2026-05-11T03:02:28.297139** — SENATE PC0 (party-alignment) — Trade Association: r=-0.160, p=0.1495
**2026-05-11T03:02:28.297592** — SENATE PC0 (party-alignment) — Multi-candidate PAC: r=-0.140, p=0.2071
**2026-05-11T03:02:28.297974** — SENATE PC0 (party-alignment) — Corporation: r=-0.103, p=0.3554
**2026-05-11T03:02:28.298591** — SENATE PC0 (party-alignment) — Party - state (NQ): r=0.111, p=0.3194
**2026-05-11T03:02:28.298922** — SENATE PC0 (party-alignment) — Presidential campaign: r=0.159, p=0.1508
**2026-05-11T03:02:28.299236** — SENATE PC0 (party-alignment) — Super PAC (non-contrib): r=0.208, p=0.0592
**2026-05-11T03:02:28.299763** — SENATE PC0 (party-alignment) — House campaign: r=0.220, p=0.0454
**2026-05-11T03:02:28.300296** — SENATE PC0 (party-alignment) — Labor Organization: r=0.428, p=0.0001
**2026-05-11T03:02:28.301573** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — House campaign: r=-0.313, p=0.0039
**2026-05-11T03:02:28.302082** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Party - national (NQ): r=-0.269, p=0.0138
**2026-05-11T03:02:28.302473** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Party - state (NQ): r=-0.225, p=0.0407
**2026-05-11T03:02:28.302876** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Senate campaign: r=-0.185, p=0.0938
**2026-05-11T03:02:28.303453** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Super PAC: r=-0.164, p=0.1395
**2026-05-11T03:02:28.304254** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Trade Association: r=-0.019, p=0.8675
**2026-05-11T03:02:28.304702** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Presidential campaign: r=-0.015, p=0.8921
**2026-05-11T03:02:28.305335** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Corporation: r=0.036, p=0.7491
**2026-05-11T03:02:28.305689** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Cooperative: r=0.126, p=0.2558
**2026-05-11T03:02:28.306093** — SENATE PC1 (internationalism-vs-civil-libertarian-skeptics) — Corp w/o Capital Stock: r=0.188, p=0.0890
**2026-05-11T03:02:28.307443** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — PAC w/ non-contrib acct: r=-0.128, p=0.2502
**2026-05-11T03:02:28.307810** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Membership Organization: r=-0.099, p=0.3752
**2026-05-11T03:02:28.308153** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Super PAC: r=-0.079, p=0.4788
**2026-05-11T03:02:28.308497** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Non-connected PAC: r=-0.067, p=0.5465
**2026-05-11T03:02:28.309004** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Multi-candidate PAC: r=-0.042, p=0.7048
**2026-05-11T03:02:28.309796** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Party - state (NQ): r=0.011, p=0.9228
**2026-05-11T03:02:28.310153** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Presidential campaign: r=0.051, p=0.6469
**2026-05-11T03:02:28.310561** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Cooperative: r=0.053, p=0.6355
**2026-05-11T03:02:28.310940** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Senate campaign: r=0.063, p=0.5699
**2026-05-11T03:02:28.311372** — SENATE PC2 (security-consensus-vs-institutional-skeptics) — Party - national (NQ): r=0.091, p=0.4133
**2026-05-11T03:02:28.314894** — Step 8: OK
**Step 09 [2026-05-11T03:02:30.549350]**: house: HDBSCAN(min_cluster_size=17), silhouette=0.765
**Step 09 [2026-05-11T03:02:30.939015]**: senate: HDBSCAN(min_cluster_size=5), silhouette=0.737
**Step 09 [2026-05-11T03:02:31.140356]**: No cluster has >= 10% minority-party membership
## 2026-05-11T03:39:26.601091 — Step 11: External Validation
- nominate_pc0_dim1_max_r: 0.982
- nominate_correlations_total: 14
- crs_correlations_above_0.10: 102
- threshold_audit: 50% threshold appropriate; 15 excluded all post-118th-Congress or near-zero coverage

