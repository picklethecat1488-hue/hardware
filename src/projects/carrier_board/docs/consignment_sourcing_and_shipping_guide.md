# Carrier Board Consignment Parts Sourcing & PCBWay Shipping Guide

**Order Reference**: PCBWay Order `#T-E68W908185A`  
**Project**: `carrier_board`  
**Assembly Quantity**: 2 Production Units  
**Date**: October 14, 2026  

---

## 1. Overview & Sourcing Strategy

During BOM audit for Order `#T-E68W908185A`, PCBWay flagged stock availability and part inquiries on 7 components. To ensure factory-fresh production silicon, avoid out-of-stock component delays, and maintain design integrity, the customer is self-sourcing and consigning all out-of-stock components (**U1**, **U2**, **D1**, **J3**, **U5**, **Y1**) directly to PCBWay's assembly facility in Shenzhen, while confirming the single manufacturer clarification for **J16** (Molex 22-28-4023) to be procured by PCBWay.

---

## 2. Consigned Parts Order Form (Distributor Sourcing List)

When consigning parts to contract manufacturers, automated SMT feeders require tape/reel leader margin and setup attrition. For a 2-unit build, order the recommended quantities below to guarantee assembly coverage without downtime:

| Ref Des | Function | Manufacturer | Manufacturer Part # (MPN) | Distributor PN | Pkg / Footprint | Build Qty | Order Qty | Order Status & Unit Price |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`U1`** | NXP Dual-Core Cortex-M33 MCU | NXP Semiconductors | **`MCXN947VDFT`** | DigiKey: `568-MCXN947VDFT-ND` | VFBGA-184 (11x11mm, 0.8mm pitch) | 2 | **5 pcs** (Cut Tape / Tray) | **Received** ($16.41 / ea, $82.05 total) |
| **`U2`** | ProxFusion Capacitive Touch Controller | Azoteq | **`IQS7222C101QNR`** (sub for `IQS7222A001QNR`) | DigiKey: `1790-IQS7222C101QNRCT-ND` | QFN-20 (3x3mm, 0.4mm pitch) | 2 | **5 pcs** (Cut Tape) | **Received** ($0.84 / ea, $4.20 total) |
| **`D1`** | Common-Anode RGB LED | Cree LED | **`CLV1A-FKB-CK1VW1DE1BB7C3C3`** | DigiKey: `CLV1A-FKB-CK1VW1DE1BB7C3C3CT-ND` | 4-PLCC SMD (2.1x2.1mm) | 2 | **10 pcs** (Cut Tape) | **Ordered** ($0.255 / ea, $2.55 total) |
| **`J3`** | 16-Pin USB Type-C Receptacle | Korean Hroparts / Standard | **`TYPE-C-16P-3MD`** | DigiKey: `6652-TYPE-C-16P-3MDTR-ND` | USB-C-16P SMD | 2 | **10 pcs** (Tape & Reel) | **Ordered** ($0.19 / ea, $1.90 total) |
| **`U5`** | Piezoelectric Sounder | CUI Devices / Same Sky | **`CPT-1207-5LTH-T`** | DigiKey: `2223-CPT-1207-5LTH-T-ND` | 12.5mm TH (piezo_speaker_12mm, 5mm pitch) | 2 | **5 pcs** (Box/Tube) | **Ordered** ($0.78 / ea, $3.90 total) |
| **`Y1`** | 24.000 MHz Crystal Resonator | ECS Inc | **`ECS-240-8-30B-CKM`** | DigiKey: `XC1842CT-ND` | XTAL-3225-4P (3.2x2.5mm) | 2 | **5 pcs** (Cut Tape) | **Ordered** ($0.98 / ea, $4.90 total) |

---

## 3. Summary of PCBWay BOM Inquiry Responses (October 14, 2026)

The updated Excel file with responses in the `Customer Reply` column has been generated at:  
`attachments/BUG-FERTILE-SANDWORM-588/T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xlsx` (and legacy `.xls`)

| Item # | Ref Des | Quoted MPN | Footprint | PCBWay Inquiry | Customer Reply / Resolution | Action by PCBWay |
| :---: | :---: | :---: | :---: | :--- | :--- | :--- |
| **10** | `D1` | `CLV1A-FKB-CJ1M1F1BB7R3S3` | `LED_RGB_4P` | Out of stock. Please recommend substitutes or you can supply this part to us. | **Customer Consigned (客供)**. Customer will consign Cree `CLV1A-FKB-CK1VW1DE1BB7C3C3` directly. Please mark as Customer Consigned and deduct from quotation. | Customer Consigned Part |
| **19** | `J3` | `TYPE-C-16P` | `USB-C-16P` | Out of stock. Please recommend substitutes or you can supply this part to us. | **Customer Consigned (客供)**. Customer will consign Korean Hroparts `TYPE-C-16P-3MD` directly. Please mark as Customer Consigned and deduct from quotation. | Customer Consigned Part |
| **28** | `J15` | `DNP` | `pin_header_2x5_1.27mm` | `[DNS/DNP/Do Not Stuff] components[DNP不要贴];` | **Confirmed**. J15 is Do Not Stuff (DNP). Please do not purchase or populate. | Mark DNP (Do Not Solder) |
| **29** | `J16` | `22-28-4023` | `pin_header_1x2` | `brand:MOLEX.Please confirm.` | **Confirmed brand: MOLEX** (MPN: `22-28-4023`). Please purchase and assemble. | PCBWay Procured |
| **40** | `U1` | `MCXN947VDF` | `VFBGA-184` | `[Supplied by customer客供];` | **Confirmed Customer Consigned (客供)**. Customer will supply fresh production NXP MCXN947VDFT directly. | Customer Consigned Part |
| **41** | `U2` | `IQS7222C101QNR` | `QFN-20` | `[Supplied by customer客供];` | **Confirmed Customer Consigned (客供)**. Customer will supply Azoteq IQS7222C101QNR directly. | Customer Consigned Part |
| **44** | `U5` | `PKM13EPYH4000-B0` | `piezo_speaker_12mm` | Out of stock. Please recommend substitutes or you can supply this part to us. | **Customer Consigned (客供)**. Customer will consign CUI Devices `CPT-1207-5LTH-T` directly. Please mark as Customer Consigned and deduct from quotation. | Customer Consigned Part |
| **51** | `Y1` | `ECS-240-8-32B-CKM` | `XTAL-3225-4P` | Out of stock. Please recommend substitutes or you can supply this part to us. | **Customer Consigned (客供)**. Customer will consign ECS Inc `ECS-240-8-30B-CKM` directly. Please mark as Customer Consigned and deduct from quotation. | Customer Consigned Part |

---

## 4. Packing, Moisture & ESD Protection Guidelines

To prevent damage during transit and reflow:

1. **Moisture Sensitivity Level (MSL)**:
   - **`U1` (`MCXN947VDFT`, VFBGA-184)** is **MSL 3** (168-hour floor life).
   - Must be sealed in an airtight **Moisture Barrier Bag (MBB)** containing fresh desiccant pouches and a Humidity Indicator Card (HIC).
   - If cut tape is repacked, do not break factory seal until shipment, or bake per J-STD-033 prior to packing.
2. **Electrostatic Discharge (ESD)**:
   - All components must be in static-shielding bags or antistatic carrier tape. Do not use plain ziplock polyethylene bags.
3. **Outer Package Cushioning**:
   - Pack into a rigid corrugated cardboard box with bubble wrap or antistatic foam. Do not ship ICs in padded envelopes.

---

## 5. Labeling Requirements for Consigned Bags

Attach a clearly printed label to **each individual component bag**:

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    U1
Manufacturer:     NXP Semiconductors
MPN:              MCXN947VDFT
Footprint:        VFBGA-184
Quantity:         5 PCS
Customer Name:    [Customer Name]
=====================================================
```

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    U2
Manufacturer:     Azoteq
MPN:              IQS7222C101QNR
Footprint:        QFN-20
Quantity:         5 PCS
Customer Name:    [Customer Name]
=====================================================
```

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    D1
Manufacturer:     Cree LED
MPN:              CLV1A-FKB-CK1VW1DE1BB7C3C3
Footprint:        LED_RGB_4P (PLCC-4)
Quantity:         10 PCS
Customer Name:    [Customer Name]
=====================================================
```

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    J3
Manufacturer:     Korean Hroparts / Standard
MPN:              TYPE-C-16P-3MD
Footprint:        USB-C-16P
Quantity:         10 PCS
Customer Name:    [Customer Name]
=====================================================
```

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    U5
Manufacturer:     CUI Devices / Same Sky
MPN:              CPT-1207-5LTH-T
Footprint:        piezo_speaker_12mm
Quantity:         5 PCS
Customer Name:    [Customer Name]
=====================================================
```

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    Y1
Manufacturer:     ECS Inc
MPN:              ECS-240-8-30B-CKM
Footprint:        XTAL-3225-4P
Quantity:         5 PCS
Customer Name:    [Customer Name]
=====================================================
```

---

## 6. Shipping & International Customs Clearance Instructions

When shipping parts to PCBWay in Shenzhen, China:

1. **Carrier**: Use **DHL Express**, **FedEx International Priority**, or **UPS Worldwide Express**. These provide seamless customs brokerage into Shenzhen.
2. **Incoterms / Duties**: Select **DDP (Delivery Duty Paid)** so all import duties, VAT, and customs fees are billed to your account. Deliveries requiring the recipient to pay customs fees locally may be rejected or delayed.
3. **Commercial Invoice Declaration**:
   - Provide 3 signed copies of the Commercial Invoice with the shipment.
   - **Description**: *"Consigned electronic components for prototype PCB assembly under Order #T-E68W908185A. Temporary import for processing and re-export. Not for commercial resale."*
   - **HTS / HS Tariff Classification Codes & Declared Breakdown**:
     - `U1` (MCXN947VDFT Microcontroller): **`8542.31.0000`** | 5 pcs @ $16.41 = **$82.05**
     - `U2` (IQS7222C101QNR Touch IC): **`8542.39.0000`** | 5 pcs @ $0.84 = **$4.20**
     - `D1` (CLV1A-FKB-CK1VW1DE1BB7C3C3 RGB LED): **`8541.41.0000`** | 10 pcs @ $0.255 = **$2.55**
     - `J3` (TYPE-C-16P-3MD USB Receptacle): **`8536.69.0000`** | 10 pcs @ $0.19 = **$1.90**
     - `U5` (CPT-1207-5LTH-T Piezo Sounder): **`8531.80.0000`** | 5 pcs @ $0.78 = **$3.90**
     - `Y1` (ECS-240-8-30B-CKM Crystal): **`8541.60.0000`** | 5 pcs @ $0.98 = **$4.90**
   - **Total Declared Customs Value**: **$99.50 USD** with invoice note: *"Value for Customs Purposes Only - Consigned Prototype Assembly Parts. Temporary import for processing and re-export. Not for commercial resale."*.
4. **Delivery Address Format** (confirm exact delivery address on your PCBWay Order Details page under "Consigned Material Delivery"):
   ```text
   Consignee:     PCBWay SMT Assembly Team
   Order #:       T-E68W908185A
   Address:       [Supplier Delivery Facility Address]
   Postal Code:   [Postal Code]
   Phone / Attn:  (See contact details in PCBWay Order Portal)
   ```
5. **Post-Shipping Action**:
   - Once shipped, log into your PCBWay account, go to **Order #T-E68W908185A**, click **"Consign Materials" / "Upload Tracking No."**, and submit the courier name and tracking number.
