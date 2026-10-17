# 🟢 `[BUG-FAST-KATYDID-792]` Create supplier required assembly documents-

- **UUID**: `8693138a-3edf-46a0-9645-ba2dbe041841`
- **ID**: `BUG-FAST-KATYDID-792`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-10-16 21:00:50 UTC`
- **Resolved**: `2026-10-16 21:10:43 UTC`

#### Description

Please replace the dubious shipping guide with the documents requested below, I will attach photos myself to the rely as well as any additional requested documents, and affix labels to each component bag:

a. Invoice: Please list each component part number and include country of origin, qty,
unit price, total price, HS code information in the invoice. (See Commercial Invoice
Template).
Notice: When parts are from Taiwan area, please don't write Taiwan directly, you should
write 'Taiwan, China'.
b. Packing list: Please also provide us the packing list to include Carton No. , Description,
Quantity, Weight, Dimension/Volume, etc.
c. Copy of airway billing: To show the tracking number and logistics method of shipping,
and also your declared value as it must be same as declared in invoice.
d. Photos of parts: Please take photos of every parts and send to us as reference. You can
take one photo for each category of parts. For example, all ICs in one photo, all LEDs in
one photo.

Leave part quantities, package dimensions blank so I can write them in myselves.

#### Resolution Notes

Replaced interim shipping guide with supplier-required assembly documents: Document A (Commercial Invoice with Country of Origin including Taiwan, China, HS codes, unit prices), Document B (Packing List with Carton No, description, weights, dimensions), Document C (Airway Bill copy, tracking declaration, DDP terms), and Document D (Photos of parts guidelines and individual component bag labels). Left component quantities and carton dimensions blank for manual completion. Generated Excel workbook at attachments/BUG-FAST-KATYDID-792/commercial_invoice_and_packing_list.xlsx. Added regression test test_regression_bug_fast_katydid_792_supplier_assembly_documents.
