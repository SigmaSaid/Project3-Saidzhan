# Validation report

**Decision:** NOT READY — at least one automated release-level contract gate failed.

This report evaluates the release-level document extractor on the pinned Big Local News snapshot.
It distinguishes source completeness, value validity, extractor agreement, and publication
readiness. The companion structured configuration is treated as a **silver reference**, not
infallible ground truth.

## Reproducibility

- Dataset: `stanforddams/biglocal`
- Revision: `4e9cd487de2b4781bc40b39a92295b0ee6827034`
- Split: `train`
- Raw fingerprint: `not available`
- Reference fingerprint: `not available`
- Reference SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Input rows: 50

## Executive result

- 0/50 rows were accepted as press releases.
- 50/50 rows were retained in quarantine; none were silently deleted.
- URL-set contract did not pass: shared=0.
- The pipeline extracted 0 event candidates and 0 explicit name-and-age candidates.

## Why “populated” is not the same as “valid”

The companion `default` configuration has a non-empty `date_last_updated` value in all 0 rows, but only 0 values parse as dates.
The other 0 values appear to be article prose mistakenly stored in that field.

No invalid modified dates found.

## Automated gates

| Gate                                  | Status   | Observed                                       | Requirement                                                | Interpretation                                                                                                                                |
|:--------------------------------------|:---------|:-----------------------------------------------|:-----------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|
| source_schema                         | FAIL     | 50 errors                                      | 0 errors                                                   | Raw rows require non-empty url/html; reference rows require all documented fields.                                                            |
| url_uniqueness                        | PASS     | raw=50/50, reference=0/0                       | 100% unique in each config                                 | Titles are not keys; the pipeline joins only on normalized source URL.                                                                        |
| one_to_one_join                       | FAIL     | shared=0                                       | identical URL sets                                         | The HTML and structured configurations must describe the same source documents.                                                               |
| row_accounting                        | PASS     | input=50, accepted=0, quarantined=50           | input = accepted + quarantined                             | No row may disappear silently.                                                                                                                |
| release_signature                     | FAIL     | 0/50 accepted                                  | >= 99% accepted; all exceptions quarantined                | A page must have the release DOM, dates, canonical identity, and article body.                                                                |
| primary_body_selector                 | FAIL     | 0.000%                                         | >= 99.0%                                                   | Fallback growth is treated as template drift, not silently accepted.                                                                          |
| title_reference_agreement             | WARN     | exact=0/0; paired agreement=100.000%           | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| topics_reference_agreement            | WARN     | exact=0/0; paired agreement=100.000%           | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| published_date_reference_agreement    | WARN     | exact=0/0; paired agreement=100.000%           | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| dateline_city_reference_agreement     | WARN     | exact=0/0; paired agreement=100.000%           | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| body_similarity                       | FAIL     | median=0.000, p05=0.000                        | median >= 0.99 and p05 >= 0.95                             | Token F1 tolerates documented block-level differences in the silver reference.                                                                |
| body_outlier_review                   | PASS     | 0/0 below 0.90 token F1                        | every outlier enters a human review queue                  | Low similarity can mean a DOM omission or useful content missing from the silver reference.                                                   |
| evidence_offsets                      | PASS     | 0 invalid offsets                              | 0 invalid offsets                                          | Every candidate must link back to an exact source-text span.                                                                                  |
| silver_reference_validity             | PASS     | 0 populated modified-date values are not dates | report completeness and validity separately                | The companion structured data is a comparison reference, not ground truth.                                                                    |
| candidate_layer_publication_readiness | PASS     | 0 event and 0 person candidates                | independent row-level adjudication before journalistic use | Candidate rules preserve evidence, but automated invariants do not establish action, legal-stage, count, person-role, or relation accuracy.   |

## Field-level silver-reference comparison

| Field           |   Reference present |   Extracted present |   Paired | Coverage   | Exact / paired   |   Extra DOM values |
|:----------------|--------------------:|--------------------:|---------:|:-----------|:-----------------|-------------------:|
| title           |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| subtitle        |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| topics          |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| published_date  |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| modified_date   |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| dateline_raw    |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| dateline_city   |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| dateline_region |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| body_text       |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |
| image_urls      |                   0 |                   0 |        0 | 100.00%    | not measurable   |                  0 |

### Body-text similarity

- Compared: 0
- Normalized exact matches: 0 (0.00%)
- Below 0.90 token F1: 0
- Below 0.95 token F1: 0
- Mean token F1: 0.0000
- Median token F1: 0.0000

### Review queue

No body-text mismatches found.

## Quarantine

| URL                                                                                                                     | Drupal entity type   | Quality flags                                                                              |
|:------------------------------------------------------------------------------------------------------------------------|:---------------------|:-------------------------------------------------------------------------------------------|
| https://www.ice.gov/news/releases/10-suspects-charged-july-4-attack-texas-ice-detention-facility                        |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/100-days-record-breaking-immigration-enforcement-us-interior                          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/11-charged-florida-marriage-fraud-scheme-targeting-us-service-members                 |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/12-arrested-south-texas-worksite-enforcement-operation-ice-rio-grande-valley-federal  |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/12-men-sentenced-conspiring-distribute-fentanyl-methamphetamine-marijuana-tennessee   |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/15-suspected-gang-members-indicted-drug-trafficking-scheme                            |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/16-charged-sweeping-houston-based-multimillion-dollar-illegal-gambling-money          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/2-drug-dealers-sentenced-murder-following-ice-hsi-investigation-florida               |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/2-hondurans-indicted-transporting-minors-across-state-lines-sexual-activity           |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/2-mexican-nationals-defendants-ice-cases-secured-arizona                              |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/2-ms-13-members-sentenced-racketeering-following-ice-new-england-partner              |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/2-naturalized-us-citizens-disrespect-legal-immigration-process-harboring-illegal      |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/2-texas-women-indicted-kidnapping-abuse-and-forced-child-labor                        |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/21-illegal-aliens-arrested-bay-leon-county-targeted-operation                         |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/25-canadian-nationals-connected-nationwide-multi-million-dollar-grandparent-scam      |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/287g-partnership-between-ice-and-ma-department-corrections-keeps-criminal-alien       |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/3-ice-officers-are-heroes-after-rescuing-motorist-burning-car-illinois                |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/3-illegal-aliens-arrested-southeast-texas-following-execution-search-warrant          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/3-violent-ms-13-gang-members-custody-following-ice-new-york-city-operation            |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/395m-counterfeit-sports-merchandise-seized-ahead-super-bowl-lix                       |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/4-chinese-nationals-sentenced-roles-complex-fraud-scheme-following-multiagency        |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/4-illegal-aliens-charged-firearms-offenses-result-ice-las-cruces-and-atf              |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/4-sentenced-federal-prison-cocaine-conspiracy-involving-89-kilograms                  |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/4-time-removed-twice-convicted-criminal-alien-sentenced-1-year-illegal-reentry        |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/5-37-fugitives-expelled-mexico-were-targets-ice-el-paso-investigation-foreign         |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/53-members-criminal-organization-known-las-farc-charged-drug-trafficking-and-firearms |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/6-foreign-nationals-indicted-illegal-reentry                                          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/6-time-removed-twice-convicted-mexican-national-charged-illegal-reentry               |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/7-connecticut-gang-members-charged-murder-and-racketeering-offenses                   |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/8-venezuelan-illegal-aliens-ties-tren-da-aragua-are-charged-transnational-commercial  |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/acting-ice-director-todd-m-lyons-statement-benjamin-hanil-songs-arrest                |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/acting-ice-director-todd-m-lyons-statement-illegal-alien-shooting-cbp-officer         |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/aliens-involved-road-rage-incident-charged-firearms-offenses-following-multi-agency   |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/arizona-man-sentenced-85-years-attempt-engage-child-sex-following-ice-tucson          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/arrests-foreign-nationals-made-electronic-benefit-transfer-card-fraud-scheme          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/british-national-indicted-organized-multi-state-fraud-and-money-laundering-scheme     |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/california-and-colorado-women-found-guilty-stalking-ice-officer                       |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/california-man-accused-doxxing-ice-employee-now-custody                               |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/california-man-arrested-charged-making-fake-ids-doordash-drivers-following-ice        |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/cameroonian-citizen-believed-be-living-canada-wanted-elder-fraud-money-laundering     |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/canadian-citizen-charged-unlawful-aerial-photography-defense-installation             |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/canadian-national-ice-custody-passes-away                                             |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/career-criminal-illegal-alien-ice-custody-passes-away-local-hospital                  |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/caribbean-arms-trafficking-ringleader-charged-conspiracy-smuggle-firearms-us          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/caribbean-trafficking-leader-criminal-organization-sentenced-nearly-5-years-firearms  |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/caught-camera-ice-arrests-violent-protesters-who-threatened-federal-law-enforcement   |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/child-exploitation-task-force-seizes-10-million-images-videos-second-year-sends-stern |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/child-predator-arrests-human-trafficking-highlight-most-viewed-articles-2015          |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/colombian-national-dies-after-being-found-unresponsive-ice-custody-phelps-county-jail |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |
| https://www.ice.gov/news/releases/colorado-fentanyl-dealer-sentenced-texas-20-years-federal-prison-following-ice-el     |                      | duplicate_source_html; missing_body; missing_published_date; missing_title; missing_topics |

## Reference-data audit

- Unique source URLs: 0/0
- Valid publication dates: 0/0
- Valid modified dates: 0/0
- Duplicate-title groups: 0
- Non-US region labels in `state`: none
- Companion-config median metadata lag: 0.0 days
- DOM-extracted median metadata lag: 0.0 days

## Publication-readiness decision

The document layer is not ready for descriptive analysis because at least one automated contract gate failed. Resolve the failed gates before using its findings.
