# SahiNaksha Demo Datasets

## Synthetic demo dataset

Location: `demo_data/`

| File | Purpose | Synthetic? |
|---|---|---|
| `sample_orthomosaic.ppm` | Tiny RGB raster fixture | Yes |
| `reference_parcels.geojson` | Four reference parcel polygons | Yes |
| `expected_final_output.geojson` | Expected reviewed-output structure | Yes |
| `provenance.json` | Dataset provenance and legal-status metadata | Yes |
| `README.md` | Dataset instructions | Yes |

### Provenance
The dataset was generated specifically for the SahiNaksha prototype. It contains no real cadastral records, land-owner information, addresses, or personal data.

The reference and expected-output geometry use the project's local `LOCAL_IMAGE_0_100` coordinate convention. These coordinates are intentionally not presented as EPSG:4326.

### Reproducibility
The fixture is deterministic and small enough to inspect manually. Convert the PPM raster to PNG for the current upload endpoint because the production upload contract accepts JPG/JPEG/PNG.

### Expected review scenario
The expected fixture demonstrates:
- 4 candidate parcels
- 2 accepted/human-verified parcels
- 1 field-verification request
- 1 rejected parcel
- 2 parcels with validation issues

These expected values are demonstration targets, not measured real-world survey results.

## External/real data
Real datasets should be added only with a recorded source, license/usage permission, CRS, acquisition date, preprocessing description and whether the geometry is authoritative. Do not mix synthetic and real records in a demo without labeling each source.