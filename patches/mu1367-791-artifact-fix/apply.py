#!/usr/bin/env python3
"""Apply or revert the MU1367 / 791 AID 12.3 artifact fix on a CarPlay Maps VC payload.

The payload directory is the one that contains common/ and profiles/, for example:
  MU1367/791_AID12.3/payload                      (this repository)
  /Volumes/<SD>/Custom/carplay_maps_vc/payload    (MQB Toolbox SD card)
  /Volumes/<SD>/CarPlayMapsVC/payload             (M.I.B. MU1367_791 SD card)

Every file is checked against the known stock and patched SHA-256 before anything
is written. Unknown builds are refused and nothing is changed.
"""
import argparse
import hashlib
import pathlib
import sys

FILES = {
    "common/altscreen-most-bridge": {
        "stock": "c846e505da704f101815a4658f1b815930d0b6f779d435349b864ef96056c8f3",
        "patched": "fed7dce45f923384fec47861c448b753913f0561ed7e2a279860a5d13f8a44f4",
        # (file offset, stock bytes, patched bytes), ARM little-endian
        "edits": [
            # Queue flush only when no access unit is part-written (packet_pos == 0).
            (0x1B04, "0030a0e3", "1c6094e5"),  # mov r3,#0         -> ldr r6,[r4,#0x1c]
            (0x1B08, "1c3084e5", "000056e3"),  # str r3,[r4,#0x1c] -> cmp r6,#0
            (0x1B0C, "0c2084e5", "0c208405"),  # str r2,[r4,#0xc]  -> streq r2,[r4,#0xc]
            (0x1B10, "143084e5", "14608405"),  # str r3,[r4,#0x14] -> streq r6,[r4,#0x14]
            # Request a fresh IDR under congestion: drop the writer fast-streak > 7 condition.
            (0x4174, "07005383", "00005383"),  # cmphi r3,#7 -> cmphi r3,#0
        ],
    },
    "profiles/MU1367/791/core.so": {
        "stock": "00b48a8fe876e6ff405124b87ed9eace1bcb079220ff7f02b866f42676477a4a",
        "patched": "b76c18934d8f0c0b446e461f1d6f8c24790b377aae45517b329ca19693b0b959",
        "edits": [
            (0x2A70, "2820a0e3", "1e20a0e3"),  # maxFPS 40 -> 30
            (0x2B94, "1410a0e3", "3210a0e3"),  # safeArea top: mov r1,#20 -> mov r1,#50
            (0x2B9C, "6e3fa0e3", "903100e3"),  # safeArea height: mov r3,#440 -> movw r3,#400
            (0x4370, "1420a0e3", "0520a0e3"),  # forced IDR every 20 -> 5 frames
            (0x452C, "1420a0e3", "0520a0e3"),  # same period, logged value
            # Cluster URL without "/map", so iOS draws the turn card (finding by mathsls).
            (0x8130, "6d6170733a2f6361722f696e737472756d656e74636c75737465722f6d617000", "6d6170733a2f6361722f696e737472756d656e74636c75737465720000000000"),
        ],
        # Earlier releases of this patch: upgraded in place.
        "previous": {
            # safe area 160,20,480,430, map-only cluster URL
            "4e2777b2d06fec693235828ce31259230e33992a931bb6b0369545e8f9ee230f": [
                (0x2B94, "1410a0e3", "3210a0e3"),
                (0x2B9C, "ae3100e3", "903100e3"),
                (0x8130, "6d6170733a2f6361722f696e737472756d656e74636c75737465722f6d617000", "6d6170733a2f6361722f696e737472756d656e74636c75737465720000000000"),
            ],
            # safe area 160,50,480,400, map-only cluster URL
            "2f7439b0af69aa53a6e5a3d89bc3c6fd08d6840cc1a983f57995f1235570c9d6": [
                (0x8130, "6d6170733a2f6361722f696e737472756d656e74636c75737465722f6d617000", "6d6170733a2f6361722f696e737472756d656e74636c75737465720000000000"),
            ],
        },
    },
    # Stop the diagnostic logs filling the 20 MB /ramdisk, which froze the cluster
    # stream after about 20 minutes (omonob/MHI2-Carplay-Maps#48, fix by mathsls).
    "common/carplay-cluster-supervisor": {
        "stock": "cdc2f9c64eae15ecfc57eafcd497a9a19582d04c7068b0a48e0b84c5d6546b24",
        "patched": "8e6ac3a85f04c3faca4850c9f09021bdd628fa1653d718f9c3db3be9d8057569",
        "edits": [
            (0x47C0, "2f72616d6469736b2f616c7473637265656e2d6d6f73742d6272696467652e6c6f6700",
             "2f6465762f6e756c6c0000000000000000000000000000000000000000000000000000"),  # bridge log path -> /dev/null
        ],
    },
    "common/dio_manager.wrapper.sh": {
        "stock": "c7889641338663fc9575834307f6d170a363644a85e5e66bb5b59fa1cfd358fc",
        "patched": "4ab7c1f88f37c0aef20735d079225767c52029be28adc989238548bd3b3442cb",
        "edits": [
            (0x03D4, "434152504c41595f414c5453435245454e5f4c4f473d2f72616d6469736b2f636172706c61796d6170732d766964656f2e6c6f67",
             "434152504c41595f414c5453435245454e5f4c4f473d2f6465762f6e756c6c202020202020202020202020202020202020202020"),  # video log -> /dev/null (space padded)
            (0x05A1, "434152504c41595f53454355524954595f4252494447455f4c4f473d2f72616d6469736b2f636172706c61792d6d6170732d73657373696f6e2e6c6f67",
             "434152504c41595f53454355524954595f4252494447455f4c4f473d2f6465762f6e756c6c202020202020202020202020202020202020202020202020"),  # session log -> /dev/null (space padded)
        ],
    },
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("payload", type=pathlib.Path, help="payload directory containing common/ and profiles/")
    parser.add_argument("--revert", action="store_true", help="restore the stock bytes instead")
    args = parser.parse_args()

    source, target = ("patched", "stock") if args.revert else ("stock", "patched")
    pending = []
    for rel, spec in FILES.items():
        path = args.payload / rel
        if not path.is_file():
            sys.exit(f"missing: {path}")
        data = bytearray(path.read_bytes())
        digest = sha256(data)
        if digest == spec[target]:
            print(f"already {target}: {rel}")
            continue
        edits = spec["edits"]
        if not args.revert and digest in spec.get("previous", {}):
            edits = spec["previous"][digest]
        elif digest != spec[source]:
            sys.exit(f"unknown build, nothing changed: {rel} ({digest})")
        for offset, stock, patched in edits:
            old, new = bytes.fromhex(stock), bytes.fromhex(patched)
            if args.revert:
                old, new = new, old
            if data[offset:offset + len(old)] != old:
                sys.exit(f"unexpected bytes at {rel}+{offset:#x}, nothing changed")
            data[offset:offset + len(new)] = new
        if sha256(data) != spec[target]:
            sys.exit(f"result hash mismatch, nothing changed: {rel}")
        pending.append((path, rel, data))

    for path, rel, data in pending:
        path.write_bytes(data)
        print(f"{target}: {rel}")


if __name__ == "__main__":
    main()
