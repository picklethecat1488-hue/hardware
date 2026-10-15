# 🟢 `[BUG-GLOWING-OLIGOCHAETE-544]` PCBWay.com -- Questions with BOM file of Order #T-E68W908185A

- **UUID**: `60a5da6f-9268-43dd-9cce-873124a43f70`
- **ID**: `BUG-GLOWING-OLIGOCHAETE-544`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-10-12 17:19:42 UTC`
- **Resolved**: `2026-10-12 17:26:06 UTC`

#### Description

The supplier is asking us to update our order with BOM revisions, see below:

Hi Leanne,

Please see the details below regarding the attached replies. I have ordered the U1 and U2 parts from DigiKey and plan to ship them to you once they arrive:

• U1 Microcontroller:
• MPN: MCXN947VDFT
• Digi-Key Part #: 568-MCXN947VDFT-ND (https://www.digikey.com/en/products/detail/nxp-usa-inc/MCXN947VDFT/22115161)
• Package: VFBGA-184 (11 × 11 mm, 0.8 mm pitch)
• Order Qty: 5 pcs (Cut Tape / Tray)

• U2 Capacitive Touch Controller:
• MPN: IQS7222C101QNR
• Digi-Key Part #: 1790-IQS7222C101QNRCT-ND (https://www.digikey.com/en/products/detail/azoteq-pty-ltd/IQS7222C101QNR/11494883)
• Package: QFN-20 (3 × 3 mm, 0.4 mm pitch)
• Order Qty: 5 to 10 pcs (Cut Tape)

Please note that the minimum buy-in on DigiKey for the IQS7222A is 8,000 units, so I am substituting the older IQS7222 in this order.

—————————

Greetings
Could you please send us rev bom in xls/xlsx format?

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `reference` | [T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xlsx](attachments/BUG-GLOWING-OLIGOCHAETE-544/T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xlsx) | Revised quotation BOM spreadsheet with U1/U2 consignment notes, IQS7222C101QNR substitution, and 3225-4P crystal |
| `reference` | [T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xls](attachments/BUG-GLOWING-OLIGOCHAETE-544/T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xls) | Legacy Excel 97-2004 format of revised quotation BOM |
| `reference` | [carrier_board_bom_rev1.xlsx](attachments/BUG-GLOWING-OLIGOCHAETE-544/carrier_board_bom_rev1.xlsx) | Clean EDA export BOM generated directly from updated carrier board model matching PCBWay schema |
| `reference` | [carrier_board_bom_rev1.csv](attachments/BUG-GLOWING-OLIGOCHAETE-544/carrier_board_bom_rev1.csv) | CSV export of clean EDA BOM |

#### Resolution Notes

Generated revised PCBWay quotation BOM spreadsheets (T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xlsx/.xls) and clean EDA engineering BOM exports (carrier_board_bom_rev1.xlsx/.csv) with IQS7222C101QNR substitution, U1/U2 customer consignment deductions, 3225-4P crystal update, and DNP J15; added regression test test_regression_bug_glowing_oligochaete_544_rev_bom_export.
