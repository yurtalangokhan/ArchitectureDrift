# ArchitectureDrift Experiment Report

Suite: `architecture-drift-astronomy-real`

Suite fingerprint: `30fef305ce5ff59a50112cef5dd7b146aaf67256b96c2332bf44372601c7e2e0`

Implementation fingerprint: `6603539adafc3bb178435c6775afc3334f1d8773840769de2710200a4ade3a88`

Git commit: `baec0147a515654d883075a3d16727150075e805`

## Aggregated Results

| Scope | Cases | Evidence | Fully detected | Detection rate | Structural P | Structural R | Structural F1 | Contract P | Contract R | Contract F1 | Evaluability |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| astronomy-shop | 6 | NON_RUNTIME | 2 | 0.333 | 0.006 | 0.333 | 0.012 | 1.000 | 0.333 | 0.500 | 1.000 |
| astronomy-shop | 6 | RUNTIME | 4 | 0.667 | 0.167 | 0.667 | 0.267 | 0.667 | 0.667 | 0.667 | 0.611 |
| astronomy-shop | 6 | FUSED | 5 | 0.833 | 0.015 | 0.833 | 0.030 | 0.714 | 0.833 | 0.769 | 1.000 |
| overall | 6 | NON_RUNTIME | 2 | 0.333 | 0.006 | 0.333 | 0.012 | 1.000 | 0.333 | 0.500 | 1.000 |
| overall | 6 | RUNTIME | 4 | 0.667 | 0.167 | 0.667 | 0.267 | 0.667 | 0.667 | 0.667 | 0.611 |
| overall | 6 | FUSED | 5 | 0.833 | 0.015 | 0.833 | 0.030 | 0.714 | 0.833 | 0.769 | 1.000 |

## Per-Mutation Detection

| System | Mutation | Non-Runtime | Runtime | Fused |
|---|---|---:|---:|---:|
| astronomy-shop | AS-M01 | No | Yes | Yes |
| astronomy-shop | AS-M02 | Yes | No | Yes |
| astronomy-shop | AS-M03 | Yes | Yes | Yes |
| astronomy-shop | AS-M04 | No | No | No |
| astronomy-shop | AS-M05 | No | Yes | Yes |
| astronomy-shop | AS-M06 | No | Yes | Yes |

## Reproducibility

The suite manifest explicitly defines the case set. Each case includes SHA-256 digests of its baseline, contracts, mutation oracle, and evidence artifacts. The implementation fingerprint covers the ArchitectureDrift Python sources and pyproject.toml.
