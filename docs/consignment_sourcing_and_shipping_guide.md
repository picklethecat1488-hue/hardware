# Carrier Board Consignment Parts Sourcing & PCBWay Shipping Guide

**Order Reference**: PCBWay Order `#T-E68W908185A`  
**Project**: `carrier_board`  
**Assembly Quantity**: 2 Production Units  
**Date**: October 11, 2026  

---

## 1. Overview & Sourcing Strategy

During BOM audit for Order `#T-E68W908185A`, PCBWay flagged stock availability and part inquiries on 7 components. To ensure factory-fresh production silicon and eliminate supply chain risks, the customer is self-sourcing and consigning the primary ICs (**U1** MCU and **U2** Capacitive Touch Controller) directly to PCBWay's assembly facility, while authorizing drop-in substitutes for general passive/connector parts.

---

## 2. Consigned Parts Order Form (Distributor Sourcing List)

When consigning parts to contract manufacturers, automated SMT feeders require tape/reel leader margin and setup attrition. For a 2-unit build, order **5 units** of each IC to guarantee assembly coverage without downtime.

| Ref Des | Function | Manufacturer | Manufacturer Part # (MPN) | Distributor PN | Pkg / Footprint | Build Qty | Recommended Order Qty (incl. SMT Attrition) | Distributor Order Link |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`U1`** | NXP Dual-Core Cortex-M33 MCU | NXP Semiconductors | **`MCXN947VDF`** | Digi-Key: `568-MCXN947VDF-ND`<br>Mouser: `771-MCXN947VDF` | VFBGA-184 (11x11mm, 0.8mm pitch) | 2 | **5 pcs** (Cut Tape / Tray) | [Digi-Key MCXN947VDF](https://www.digikey.com/en/products/result?keywords=MCXN947VDF) |
| **`U2`** | ProxFusion Capacitive Touch Controller | Azoteq | **`IQS7222A001QNR`** | Digi-Key: `IQS7222A-QNR-ND`<br>Mouser: `614-IQS7222A001QNR` | QFN-20 (3x3mm, 0.4mm pitch) | 2 | **5 to 10 pcs** (Cut Tape) | [Digi-Key IQS7222A-QNR](https://www.digikey.com/en/products/result?keywords=IQS7222A001QNR) |

### Contingency Consignment (Only if PCBWay Cannot Source Substitutes)

If PCBWay is unable to procure local drop-in equivalents for **D1** or **U5**, add these to the distributor order:

| Ref Des | Function | Manufacturer | MPN | Distributor PN | Pkg | Order Qty | Order Link |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`D1`** | Common-Anode RGB LED | Cree LED | `CLV1A-FKB-CJ1M1F1BB7R3S3` | Digi-Key: `CLV1A-FKB-ND` | 4-PLCC SMD (2.1x2.1mm) | 10 pcs | [Digi-Key CLV1A-FKB](https://www.digikey.com/en/products/result?keywords=CLV1A-FKB) |
| **`U5`** | Piezoelectric Sounder | Murata | `PKM13EPYH4000-B0` | Digi-Key: `490-4700-ND` | 12.6mm SMD | 5 pcs | [Digi-Key PKM13EPYH4000](https://www.digikey.com/en/products/result?keywords=PKM13EPYH4000-B0) |

---

## 3. Summary of PCBWay BOM Inquiry Responses

The updated Excel file with responses in the `Customer Reply` column has been generated at:  
`attachments/BUG-SEGMENTED-PALOLO-739/T-E68W908185A-2units-bom_templates(2026-10-11)_replied.xlsx`

| Item # | Ref Des | Quoted MPN | Footprint | PCBWay Inquiry | Customer Reply / Resolution | Action by PCBWay |
| :---: | :---: | :---: | :---: | :--- | :--- | :--- |
| **10** | `D1` | `CLV1A-FKB-CJ1M1F1BB7R3S3` | `LED_RGB_4P` | Out of stock. Please recommend substitutes or supply part. | **Approve local substitute**: Everlight `EAST2018RGBA0`, Kingbright `AA2810AZGS/CA`, or Lite-On `LTST-C19HE1WT` (Common Anode 4-PLCC RGB LED). If unavailable, customer will consign Cree part. | Source substitute locally |
| **19** | `J3` | `TYPE-C-16P` | `USB-C-16P` | Out of stock. Please recommend substitutes or supply part. | **Approve local substitute**: Standard in-stock 16-pin USB-C receptacle: Korean Hroparts `TYPE-C-31-M-12` (LCSC `C165948`), SHOU HAN `TYPE-C 16P` (`C2837372`), or XKB `U262-161N-4BQC11` (`C2765186`). | Source substitute locally |
| **28** | `J15` | `DNP` | `pin_header_2x5_1.27mm` | `[DNS/DNP/Do Not Stuff] components[DNP不要贴];` | **Confirmed**. J15 is Do Not Stuff (DNP). Do NOT purchase or populate. | Mark DNP (Do Not Solder) |
| **40** | `U1` | `MCXN947VDF` | `VFBGA-184` | The part we can get here was made in the year of 2022+ OK? | **Do NOT purchase 2022 stock**. Customer will consign/supply fresh production NXP MCXN947VDF to you directly. Please deduct component cost from quote. | Customer Consigned Part |
| **41** | `U2` | `IQS7222A001QNR` | `QFN-20` | Out of stock. Please recommend substitutes or supply part. | **Customer Consigned**. Customer will supply Azoteq IQS7222A001QNR directly. Please deduct component cost from quote. | Customer Consigned Part |
| **44** | `U5` | `PKM13EPYH4000-B0` | `piezo_speaker_12mm` | Out of stock. Please recommend substitutes or supply part. | **Approve local substitute**: Murata `PKM13EPYH4002-B0`, CUI Devices `CPT-1205C-300`, or PUI Audio `SMT-0927-S-6-R`. If unavailable, customer will consign Murata part. | Source substitute locally |
| **51** | `Y1` | `ECS-240-8-30B-CKM` | `XTAL-3225-4P` | Correct package for listed MPN is SMD5032-4P, not SMD3225-4P. Please confirm. | **Confirmed package is 3225**. Please update MPN to **`ECS-240-8-32B-CKM`** (or equivalent 24.000MHz 8pF 3225-4P crystal, e.g. Abracon `ABM8G-24.000MHZ-18-D2Y-T`). | Update MPN & source 3225 |

---

## 4. Packing, Moisture & ESD Protection Guidelines

To prevent damage during transit and reflow:

1. **Moisture Sensitivity Level (MSL)**:
   - **`U1` (`MCXN947VDF`, VFBGA-184)** is **MSL 3** (168-hour floor life).
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
MPN:              MCXN947VDF
Footprint:        VFBGA-184
Quantity:         5 PCS
Customer Name:    Daniel Parker
=====================================================
```

```text
=====================================================
PCBWAY CONSIGNED COMPONENT
Order Number:     T-E68W908185A
Subassembly:      carrier_board
Reference Des:    U2
Manufacturer:     Azoteq
MPN:              IQS7222A001QNR
Footprint:        QFN-20
Quantity:         5 PCS (or 10 PCS)
Customer Name:    Daniel Parker
=====================================================
```

---

## 6. Shipping & International Customs Clearance Instructions

When shipping parts to PCBWay in Shenzhen, China:

1. **Carrier**: Use **DHL Express**, **FedEx International Priority**, or **UPS Worldwide Express**. These provide seamless customs brokerage into Shenzhen.
2. **Incoterms / Duties**: Select **DDP (Delivery Duty Paid)** so all import duties, VAT, and customs fees are billed to your account. Deliveries requiring the recipient to pay customs fees locally may be rejected or delayed.
3. **Commercial Invoice Declaration**:
   - Provide 3 signed copies of the Commercial Invoice with the shipment.
   - **Description**: *"Consigned electronic integrated circuit samples for prototype PCB assembly under Order #T-E68W908185A. Temporary import for processing and re-export. Not for commercial resale."*
   - **HTS / HS Tariff Classification Codes**:
     - `U1` (MCXN947VDF Microcontroller): **`8542.31.0000`** (Processors & Controllers)
     - `U2` (IQS7222A001QNR Touch IC): **`8542.39.0000`** (Other Electronic Integrated Circuits)
   - **Declared Customs Value**: State the purchase value (e.g. ~$120 USD total) with note: *"Value for Customs Purposes Only - Consigned Prototype Assembly Parts"*.
4. **Delivery Address Format** (confirm exact address on your PCBWay Order Details page under "Consigned Material Delivery"):
   ```text
   Consignee:     PCBWay SMT Assembly Team
   Order #:       T-E68W908185A
   Address:       Building 2, No. 1, Baolong 6th Road, Baolong Community,
                  Baolong Subdistrict, Longgang District,
                  Shenzhen, Guangdong, China
   Postal Code:   518116
   Phone / Attn:  (See contact number in PCBWay Order Portal)
   ```
5. **Post-Shipping Action**:
   - Once shipped, log into your PCBWay account, go to **Order #T-E68W908185A**, click **"Consign Materials" / "Upload Tracking No."**, and submit the courier name and tracking number.
