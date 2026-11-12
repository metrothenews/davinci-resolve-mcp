# LUTs

Workflows use the copies in this folder, not the originals in Resolve's LUT directory. This folder is the source of truth.

| File | What it is | Source | SHA-256 |
|---|---|---|---|
| `LUT 1_33 Point Cube_1.C0047.cube` | Grade from clip C0047.MP4, exported from Resolve. 33-point 3D cube. Node 1 contained Primary Balance + Saturation, Hue & Lum Mix. | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/MTN Luts/` (backed up 2026-11-11) | `4c4a54c0d60a42d07eac02bd1ac7bb62e27fcedb2bc000093f6c5645d96d4ffe` |
| `NIGHT_1_33Pt.cube` | Grade from C0047.MP4 (identical to the file above) | `export_luts`, 2026-11-11 | `4c4a54c0d60a42d07eac02bd1ac7bb62e27fcedb2bc000093f6c5645d96d4ffe` |
| `NIGHT_2_33Pt.cube` | Grade from C0051.MP4 | `export_luts`, 2026-11-11 | `15606f6ea714834fc3d6e75cdaaaba51a11e2893650941c8aad883b87b7b0124` |
| `NIGHT_3_33Pt.cube` | Grade from C0052.MP4 | `export_luts`, 2026-11-11 | `2f8d696ffa77a6ce0a9311096130f00839d0a605a4696d86fe46c4c58808f731` |
| `NIGHT_4_33Pt.cube` | Grade from C0053.MP4 | `export_luts`, 2026-11-11 | `a9a0eee4d82e82658ad01f2b32f52704bfdcb1abc5a1af97e62c0319656bf7a8` |
| `NIGHT_5_33Pt.cube` | Grade from C0054.MP4 | `export_luts`, 2026-11-11 | `c2832ce049689c5e3ce8ee0bd8221772e45641c974faae8e58412ad1d538e2fa` |
| `NIGHT_6_33Pt.cube` | Grade from C0055.MP4 | `export_luts`, 2026-11-11 | `7ad37d208e84002123f1a7196caaa00cc59384757e0e3e4e151a25a4a40b9418` |
| `NIGHT_7_33Pt.cube` | Grade from C0057.MP4 | `export_luts`, 2026-11-11 | `c86ada992b21b0be4061ea2e276de611b6ff762cfe52f1ad5714d327b0f8f2c3` |
| `NIGHT_8_33Pt.cube` | Grade from C0058.MP4 | `export_luts`, 2026-11-11 | `0d763cd040c7e2345f0332b482382f5967ef990c096dac1b8ae12422f35836c2` |
| `NIGHT_COLOR_1_33Pt.cube` | Color balance only, from the manual adjustments on C0047.MP4 | `color_only_luts`, 2026-11-11 | `2b0f34331f8c78336bb0c1d6b868bb8c4d738f916009604c7d31d3969cb73ab4` |
| `NIGHT_COLOR_2_33Pt.cube` | Color balance only, from the manual adjustments on C0054.MP4 | `color_only_luts`, 2026-11-11 | `9e7b8d40adcab9bdb0361b6519c74ccab26d3d55cdf3b424acb6d3a0fe54c9cd` |
| `NIGHT_COLOR_3_33Pt.cube` | Color balance only, from the manual adjustments on C0055.MP4 | `color_only_luts`, 2026-11-11 | `8bae81ae29f8d03ce7d390ca1349034b659ec6465350c5a71bf425377f7c2242` |
| `NIGHT_COLOR_4_33Pt.cube` | Color balance only, from the manual adjustments on C0057.MP4 | `color_only_luts`, 2026-11-11 | `7572bf50503752a279381f85716cac16bac71db4b7598556c923a9e4487c1b48` |
| `NIGHT_COLOR_5_33Pt.cube` | Color balance only, from the manual adjustments on C0058.MP4 | `color_only_luts`, 2026-11-11 | `30f0e8fe95c664ebe3277df3976d56b7dd20f3cdba3d5d2168e3e8df30a92f8e` |
| `NIGHT_COLOR_6_33Pt.cube` | Color balance only, from the manual adjustments on C0061.MP4 | `color_only_luts`, 2026-11-11 | `323e613e727ae3846211848b336378cbf230753ba1dee891c677142cc27ce6a3` |
| `NIGHT_COLOR_7_33Pt.cube` | Color balance only, from the manual adjustments on C0062.MP4 | `color_only_luts`, 2026-11-11 | `0c3e44b67d02372283251e8d183ae5fbca33a9224ff622f9d302d31499550452` |
| `NIGHT_COLOR_8_33Pt.cube` | Color balance only, from the manual adjustments on C0063.MP4 | `color_only_luts`, 2026-11-11 | `9f78401fb4e1c6c989c0d3f29d583cddf8fb2f6caac789494f700077e257df0f` |

The NIGHT and NIGHT_COLOR files also exist in Resolve's `MTN Luts` folder, but the copies here are the ones workflows use.

`NIGHT_n` are the first-pass look LUTs. `NIGHT_COLOR_n` are the second-pass color LUTs; they are applied *before* the look LUT. When a clip has both, the app layers them into one file in `combined/` (named `<look>__<color>.cube`, rebuilt on demand, safe to delete). See [docs/workflows/color_only_luts.md](../docs/workflows/color_only_luts.md).

## Adding a LUT

1. Copy the `.cube` file here with `cp -p`.
2. Add a row above, including its source and checksum (`shasum -a 256 <file>`).
