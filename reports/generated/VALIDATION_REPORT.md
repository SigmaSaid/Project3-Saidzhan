# Validation report

**Decision:** PASS WITH WARNINGS — prespecified automated contract thresholds passed; listed exceptions still require review.

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
- Reference SHA-256: `72dc5ce6109a95e7e7454d13dfcbed61d3e39ad4e3986dc875c145eebb6b12b5`
- Input rows: 965

## Executive result

- 964/965 rows were accepted as press releases.
- 1/965 rows were retained in quarantine; none were silently deleted.
- URL sets match one-to-one between the `html` and `default` configurations.
- The pipeline extracted 5,677 event candidates and 542 explicit name-and-age candidates.

## Why “populated” is not the same as “valid”

The companion `default` configuration has a non-empty `date_last_updated` value in all 965 rows, but only 962 values parse as dates.
The other 3 values appear to be article prose mistakenly stored in that field.

| Source URL                                                                                                              | Invalid populated value                                                                                                                                                               |
|:------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| https://www.ice.gov/news/releases/child-predator-arrests-human-trafficking-highlight-most-viewed-articles-2015          | ICE Enforcement and Removal Operations (ERO) enforces the nation’s immigration laws by identifying, arresting and removing aliens who present a danger to national security. In 2015… |
| https://www.ice.gov/news/releases/ice-releases-new-information-extensive-criminal-history-illegal-alien-ian-roberts-who | Roberts updated his address with USCIS.                                                                                                                                               |
| https://www.ice.gov/news/releases/meet-one-medias-non-criminals-ice-washington-arrests-another-illegal-alien-fugitive   | In February, the Security Alliance for Fugitive Enforcement Task Force in El Salvador provided updated information regarding Morales-Mejia’s possible presence in Northern Virginia.… |

## Automated gates

| Gate                                  | Status   | Observed                                       | Requirement                                                | Interpretation                                                                                                                                |
|:--------------------------------------|:---------|:-----------------------------------------------|:-----------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|
| source_schema                         | PASS     | 0 errors                                       | 0 errors                                                   | Raw rows require non-empty url/html; reference rows require all documented fields.                                                            |
| url_uniqueness                        | PASS     | raw=965/965, reference=965/965                 | 100% unique in each config                                 | Titles are not keys; the pipeline joins only on normalized source URL.                                                                        |
| one_to_one_join                       | PASS     | shared=965                                     | identical URL sets                                         | The HTML and structured configurations must describe the same source documents.                                                               |
| row_accounting                        | PASS     | input=965, accepted=964, quarantined=1         | input = accepted + quarantined                             | No row may disappear silently.                                                                                                                |
| release_signature                     | PASS     | 964/965 accepted                               | >= 99% accepted; all exceptions quarantined                | A page must have the release DOM, dates, canonical identity, and article body.                                                                |
| primary_body_selector                 | PASS     | 100.000%                                       | >= 99.0%                                                   | Fallback growth is treated as template drift, not silently accepted.                                                                          |
| title_reference_agreement             | PASS     | exact=965/965; paired agreement=100.000%       | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| topics_reference_agreement            | PASS     | exact=964/964; paired agreement=100.000%       | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| published_date_reference_agreement    | PASS     | exact=964/964; paired agreement=100.000%       | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| dateline_city_reference_agreement     | PASS     | exact=964/964; paired agreement=100.000%       | exact/reference-present >= 99.0%                           | Agreement is measured only where both the DOM extraction and silver reference have a value; the gate also penalizes missing extracted values. |
| body_similarity                       | PASS     | median=1.000, p05=1.000                        | median >= 0.99 and p05 >= 0.95                             | Token F1 tolerates documented block-level differences in the silver reference.                                                                |
| body_outlier_review                   | PASS     | 0/964 below 0.90 token F1                      | every outlier enters a human review queue                  | Low similarity can mean a DOM omission or useful content missing from the silver reference.                                                   |
| evidence_offsets                      | PASS     | 0 invalid offsets                              | 0 invalid offsets                                          | Every candidate must link back to an exact source-text span.                                                                                  |
| silver_reference_validity             | WARN     | 3 populated modified-date values are not dates | report completeness and validity separately                | The companion structured data is a comparison reference, not ground truth.                                                                    |
| candidate_layer_publication_readiness | WARN     | 5677 event and 542 person candidates           | independent row-level adjudication before journalistic use | Candidate rules preserve evidence, but automated invariants do not establish action, legal-stage, count, person-role, or relation accuracy.   |

## Field-level silver-reference comparison

| Field           |   Reference present |   Extracted present |   Paired | Coverage   | Exact / paired    |   Extra DOM values |
|:----------------|--------------------:|--------------------:|---------:|:-----------|:------------------|-------------------:|
| title           |                 965 |                 965 |      965 | 100.00%    | 965/965 (100.00%) |                  0 |
| subtitle        |                 176 |                 176 |      176 | 100.00%    | 176/176 (100.00%) |                  0 |
| topics          |                 964 |                 964 |      964 | 100.00%    | 964/964 (100.00%) |                  0 |
| published_date  |                 964 |                 965 |      964 | 100.00%    | 964/964 (100.00%) |                  1 |
| modified_date   |                 962 |                 965 |      962 | 100.00%    | 962/962 (100.00%) |                  3 |
| dateline_raw    |                 946 |                 952 |      945 | 99.89%     | 945/945 (100.00%) |                  7 |
| dateline_city   |                 964 |                 964 |      964 | 100.00%    | 964/964 (100.00%) |                  0 |
| dateline_region |                 964 |                 964 |      964 | 100.00%    | 964/964 (100.00%) |                  0 |
| body_text       |                 964 |                 965 |      964 | 100.00%    | 962/964 (99.79%)  |                  1 |
| image_urls      |                 525 |                 548 |      525 | 100.00%    | 515/525 (98.10%)  |                 23 |

### Body-text similarity

- Compared: 964
- Normalized exact matches: 962 (99.79%)
- Below 0.90 token F1: 0
- Below 0.95 token F1: 0
- Mean token F1: 0.9999
- Median token F1: 1.0000

### Review queue

| URL                                                                                                           |   Token F1 | Reference / DOM tokens   | First difference                                                                                                                                                                                                                                                                                                        |
|:--------------------------------------------------------------------------------------------------------------|-----------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| https://www.ice.gov/news/releases/social                                                                      |     0      | 2 / 239                  | replace at reference tokens 0:2, DOM tokens 0:239; reference context: 'not found'; DOM context: 'ICE actively participates in a number of social networks and the ICE Social Network Portal is a starting point from [… 219 changed tokens omitted …]'                                                                  |
| https://www.ice.gov/news/releases/ice-issues-over-1000-tentative-job-offers-shore-agencys-enforcement-efforts |     0.9531 | 191 / 208                | insert at reference tokens 191:191, DOM tokens 191:208; reference context: 'that’s a cause people really believe in.” For'; DOM context: 'that’s a cause people really believe in.” For media inquiries about ICE activities, operations or policies, contact ICE’s Office of Public Affairs at ICEMedia@ICE.dhs.gov .' |
| https://www.ice.gov/news/releases/ice-removes-liberian-rebel-commander-known-using-child-soldiers             |     0.9804 | 372 / 384                | insert at reference tokens 372:372, DOM tokens 372:384; reference context: 'can also email tips to HRV.ICE@ice.dhs.gov . For'; DOM context: 'can also email tips to HRV.ICE@ice.dhs.gov . For media inquiries, contact ICE Public Affairs Officer Lindsay Williams at Lindsay.Williams@ice.dhs.gov .'                   |

## Quarantine

| URL                                      | Drupal entity type   | Quality flags                                                                                              |
|:-----------------------------------------|:---------------------|:-----------------------------------------------------------------------------------------------------------|
| https://www.ice.gov/news/releases/social | basic_page           | body_fallback; canonical_url_mismatch; missing_topics; title_fallback; unexpected_entity_bundle:basic_page |

## Reference-data audit

- Unique source URLs: 965/965
- Valid publication dates: 964/965
- Valid modified dates: 962/965
- Duplicate-title groups: 1
- Non-US region labels in `state`: Peru
- Companion-config median metadata lag: 2 days
- DOM-extracted median metadata lag: 2.0 days

## Publication-readiness decision

The accepted document records passed the project's prespecified structural and silver-agreement thresholds. This is an automated contract result, not proof of ground-truth accuracy. 0 body outliers below 0.90 token F1 await human adjudication.
