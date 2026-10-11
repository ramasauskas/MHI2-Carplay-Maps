# MU1367 / 791 AID 12.3: block-artifact fix

Binary patch for the stock CarPlay Maps VC `altscreen-most-bridge` and the MU1367/791 `core.so`. It removes the colored block artifacts on the 791 cluster map that appear on roundabouts, during fast scrolling, and in dense map areas, especially with Waze.

The analysis and patches are by **[diasdio](https://github.com/diasdio)**, described in [omonob/MHI2-Carplay-Maps#1 (comment)](https://github.com/omonob/MHI2-Carplay-Maps/issues/1#issuecomment-6108353282). The safe-area finding is **[patrickrpracht-create](https://github.com/patrickrpracht-create)**'s, from [#5](https://github.com/omonob/MHI2-Carplay-Maps/issues/5). The binaries and the low-latency recovery design are **[omonob](https://github.com/omonob)**'s. This directory only packages the patch so it can be applied and checked.

## What changes

| File | Offset | Change | Why |
| --- | --- | --- | --- |
| `altscreen-most-bridge` | `0x1b04`–`0x1b13` | Queue flush runs only when no access unit is part-written | A flush in the middle of an AU sent a truncated H.264 frame to the cluster. The corruption then held until the next IDR. |
| `altscreen-most-bridge` | `0x4174` | `cmphi r3,#7` → `cmphi r3,#0` | Under congestion the fresh-IDR request was never made, because any MOST write over 30 ms reset the "fast writes" streak it waited for. |
| `core.so` | `0x4370`, `0x452c` | Forced IDR every 20 → 5 frames | This matches VW's own GOP length (`nv_frames_per_gop = 5`). The MOST queue holds about one GOP. |
| `core.so` | `0x2a70` | `maxFPS` 40 → 30 | Less data per second over MOST. |
| `core.so` | `0x2b9c` | `safeArea` height 440 → 430 | Stops the position arrow being cut off when the cluster shows its bottom warning strip. |

Trade-off: the map is a little less fluid and lags slightly, similar to the factory map.

| File | Stock SHA-256 | Patched SHA-256 |
| --- | --- | --- |
| `common/altscreen-most-bridge` | `c846e505da704f101815a4658f1b815930d0b6f779d435349b864ef96056c8f3` | `fed7dce45f923384fec47861c448b753913f0561ed7e2a279860a5d13f8a44f4` |
| `profiles/MU1367/791/core.so` | `00b48a8fe876e6ff405124b87ed9eace1bcb079220ff7f02b866f42676477a4a` | `4e2777b2d06fec693235828ce31259230e33992a931bb6b0369545e8f9ee230f` |

The patched hashes are identical to the builds diasdio runs in their car.

## Tested on

- Golf Alltrack MK7: `MHI2_ER_VWG13_K4525_1`, MU1367, cluster 5G1920791B (diasdio).
- MU1367 on `MHI2_ER_VWG13_P4521`, head unit 5NA035020D H51, cluster 5G1920791A, SW 3195 / HW 408. MQB Toolbox route with NavActiveIgnore (ramasauskas).

Only **MU1367 with the 791 AID 12.3** has been tested. The bridge is byte-identical in every profile, but the patch has not been tried on MU1102, MU1440 or the 790 cluster.

## Install

`MU1367/791_AID12.3/payload` in this fork already contains the patched files. To patch an SD card prepared from the [upstream release](https://github.com/omonob/MHI2-Carplay-Maps/releases/latest), point the script at its payload directory:

```sh
# MQB Toolbox V4.2A card
python3 patches/mu1367-791-artifact-fix/apply.py "/Volumes/<SD>/Custom/carplay_maps_vc/payload"
# M.I.B. 3.6.0 MU1367_791 card
python3 patches/mu1367-791-artifact-fix/apply.py "/Volumes/<SD>/CarPlayMapsVC/payload"
```

The script refuses any file that is not the exact stock or patched build, and in that case writes nothing. On an MQB card the bridge is shared by every MU profile, so use a patched card only for MU1367 with a 791 cluster.

Then, with the card in SD1, run **Customization → CarPlay Maps VC → Install 791 AID 12.3 (AUTO MU)**. Wait for `CPMAP_INSTALL_OK` and do a full reboot. Running the installer again keeps the factory backups from the first install.

## Revert

- Remove the mod in the car with **Customization → CarPlay Maps VC → Restore factory files**, then do a full reboot.
- Or restore the stock bytes with `apply.py --revert <payload>` and run **Install 791 AID 12.3** again.
