# 🟢 `[BUG-FERTILE-SANDWORM-588]` PCBWay.com -- Questions with BOM file of Order #T-E68W908185A

- **UUID**: `ff912e53-deec-43f8-b3ba-3c18ad6dcefc`
- **ID**: `BUG-FERTILE-SANDWORM-588`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-10-14 17:05:57 UTC`
- **Resolved**: `2026-10-14 17:21:57 UTC`

#### Description

Pls see attached, we should plan to consign all remaining components to them except for the one substitute-

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `reference` | [T-E68W908185A-2units-bom_templates(2026-10-14) questions.xlsx](attachments/BUG-FERTILE-SANDWORM-588/T-E68W908185A-2units-bom_templates(2026-10-14) questions.xlsx) | Uploaded reference questions spreadsheet from PCBWay |
| `reference` | [T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xlsx](attachments/BUG-FERTILE-SANDWORM-588/T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xlsx) | Replied quotation BOM with customer consignment notes for D1, J3, U5, Y1 and Molex confirmation for J16 |
| `reference` | [T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xls](attachments/BUG-FERTILE-SANDWORM-588/T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xls) | Legacy Excel 97-2004 format of replied quotation BOM |
| `reference` | [carrier_board_bom_rev2.xlsx](attachments/BUG-FERTILE-SANDWORM-588/carrier_board_bom_rev2.xlsx) | Clean EDA export BOM generated directly from updated carrier board model |
| `reference` | [carrier_board_bom_rev2.csv](attachments/BUG-FERTILE-SANDWORM-588/carrier_board_bom_rev2.csv) | CSV export of clean EDA BOM |
| `reference` | [carrier_board_bom_rev3.xlsx](attachments/BUG-FERTILE-SANDWORM-588/carrier_board_bom_rev3.xlsx) | Clean EDA export BOM Rev 3 with DigiKey substituted MPNs (CLV1A-FKB-CK1VW1DE1BB7C3C3, TYPE-C-16P-3MD, CPT-1207-5LTH-T, ECS-240-8-30B-CKM) |
| `reference` | [carrier_board_bom_rev3.csv](attachments/BUG-FERTILE-SANDWORM-588/carrier_board_bom_rev3.csv) | CSV export of clean EDA BOM Rev 3 |
| `reference` | [digikey_order_2026-10-14.xlsx](attachments/BUG-FERTILE-SANDWORM-588/digikey_order_2026-10-14.xlsx) | Customer DigiKey order confirmation for additional consigned parts (D1, J3, U5, Y1) and received MCUs (U1, U2) |

#### Resolution Notes

Consigned remaining out-of-stock components (D1, J3, U5, Y1) to PCBWay alongside U1 and U2, confirmed Molex brand for J16 (22-28-4023), generated replied quotation templates (.xlsx/.xls) and clean EDA BOM exports (Rev 2 & Rev 3 .xlsx/.csv), incorporated DigiKey order confirmation (order file `digikey_order_2026-10-14.xlsx` with total value $99.50 across 40 pcs), updated carrier board wiring and exporter manufacturer/through-hole inference, and updated consignment sourcing & shipping guide with exact MPNs, distributor part numbers, packaging requirements, and commercial invoice customs declarations.
