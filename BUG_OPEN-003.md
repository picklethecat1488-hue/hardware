# 🟢 `[BUG-OPEN-003]` EQ of order W908185ASE67_gerbers

- **UUID**: `448546c4-60eb-457e-b3e7-fc7b4b6d4527`
- **ID**: `BUG-OPEN-003`
- **Status**: `RESOLVED`
- **Severity**: `HIGH`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-07 15:43:22 UTC`
- **Resolved**: `2026-11-07 20:35:26 UTC`

#### Description

There are feedbacks on our Gerber’s (see attached), can you please fill out the Customer Reply section with responses, and update the project as necessary:
1) I’m OK with making our PCB .zip files Gerber standard files only. They highlighted the files they wanted removed
6) We can provide whatever feedback or updates are necessary
7) Please correct our impedence info in the design files and I will send updated Gerbers back to them

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `document` | [W908185ASE67-EQ.csv](attachments/BUG-OPEN-003/W908185ASE67-EQ.csv) | Uploaded document W908185ASE67-EQ.csv |
| `screenshot` | [screenshot_paste_1794082523598_un4js.png](attachments/BUG-OPEN-003/screenshot_paste_1794082523598_un4js.png) | Pasted screenshot screenshot_paste_1794082523598_un4js.png |
| `screenshot` | [screenshot_paste_1794082544131_e1kse.png](attachments/BUG-OPEN-003/screenshot_paste_1794082544131_e1kse.png) | Pasted screenshot screenshot_paste_1794082544131_e1kse.png |
| `screenshot` | [screenshot_paste_1794082551994_w6s3q.png](attachments/BUG-OPEN-003/screenshot_paste_1794082551994_w6s3q.png) | Pasted screenshot screenshot_paste_1794082551994_w6s3q.png |
| `screenshot` | [screenshot_paste_1794082558274_doxkv.png](attachments/BUG-OPEN-003/screenshot_paste_1794082558274_doxkv.png) | Pasted screenshot screenshot_paste_1794082558274_doxkv.png |
| `screenshot` | [screenshot_paste_1794082565048_ucixy.png](attachments/BUG-OPEN-003/screenshot_paste_1794082565048_ucixy.png) | Pasted screenshot screenshot_paste_1794082565048_ucixy.png |
| `screenshot` | [screenshot_paste_1794082590749_zorq7.png](attachments/BUG-OPEN-003/screenshot_paste_1794082590749_zorq7.png) | Pasted screenshot screenshot_paste_1794082590749_zorq7.png |
| `screenshot` | [screenshot_paste_1794082597850_8j2oo.png](attachments/BUG-OPEN-003/screenshot_paste_1794082597850_8j2oo.png) | Pasted screenshot screenshot_paste_1794082597850_8j2oo.png |

#### Attached Commits

- `f647928d`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:3b8d1948 --> Verify generated supplier packages strictly contain standard Gerber files | `unzip -l build/board/carrier_board/carrier_board/gerbers.zip`
- [ ] <!-- task:9d48fade --> Verify controlled impedance specification and VIPPO notes | `cat build/board/carrier_board/carrier_board/impedance_control_info.txt`

#### Resolution Notes

Resolved fab engineering queries (EQ) for order W908185ASE67_gerbers: (1) Populated Customer Reply section for all 7 items in W908185ASE67-EQ.csv, .xls, and .xlsx. (2) Standardized PCB zip packaging in provider/pcb/supplier.py to strictly include Gerber standard files (.gbr, .drl, .gbrjob, reports), removing companion CAD files (.pcb, .pcbdoc, .cam, .brd, .kicad_pcb). (3) Synchronized laminate specification to TG150 across fab notes, project summary, and supplier orders. (4) Added GND copper plane fill across blank regions of In2.Cu to achieve copper balance and prevent board warpage/delamination. (5) Corrected impedance specifications in design files (Dwgs.User silkscreen, project_summary, impedance_control_info.txt) to match actual 0.120mm routed trace width and 0.120mm spacing for USB 2.0 90 Ohm differential microstrip and 50 Ohm single-ended microstrip referenced to L2 GND.
