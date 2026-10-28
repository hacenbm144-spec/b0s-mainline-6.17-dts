# b0s-mainline-dts

Device tree and kernel patch series for running **mainline Linux 6.17** on the
**Samsung Galaxy S22 Ultra** (Exynos 2200, board `b0s`, SM-S908B).

Samsung's S-Boot applies six EDTBO overlays to whatever device tree it is handed, and it only
accepts one that matches expectations documented nowhere. Getting any of them wrong either sends
the phone to **Download mode** or panics the kernel in `paging_init` with a message that does not
name the cause. This repository contains the device tree that passes, the S-Boot device-tree ABI
findings reverse-engineered to get there, and the kernel patch series that makes the rest of the
platform work.

---

## What is here

```
patches/
  SERIES                        apply order + target tree
  0002-phy-samsung-ufs-add-Exynos-2200-UFS-PHY.patch
  0003-scsi-ufs-exynos-add-Exynos-2200-variant.patch
  0004-phy-exynos5-usbdrd-make-Exynos-2200-USB-3-work.patch
  0005-soc-samsung-b0s-kexec-boot-PMIC-rail-restore-via-ACP.patch
  0006-phy-samsung-exynos2200-usbdp-clean-USBDP-combo-PHY.patch
  0007-arm64-dts-exynos2200-add-b0s-S22-Ultra-and-its-kexec.patch
  0008-b0s-take-USBDP-eUSB2-reset-ACPM-and-DPU-addresses.patch
dtb/
  exynos2200-b0s.dts            2+2 cells, mainline-native,   331 nodes
  exynos2200-b0s-kx.dts         2+1 cells, S-Boot-compatible, 358 nodes
docs/
  DT-ABI-FINDINGS.md            the S-Boot device-tree requirements
```

## The patch series

| patch | what it does |
|---|---|
| **0002** | Exynos 2200 UFS PHY driver support |
| **0003** | Exynos 2200 variant in the UFS host driver |
| **0004** | make Exynos 2200 USB 3 work on the `exynos5-usbdrd` PHY |
| **0005** | restore PMIC rails across a kexec boot (ACP-M) |
| **0006** | clean up the Exynos 2200 USBDP combo PHY |
| **0007** | **device tree for the S22 Ultra** — the headline artifact |
| **0008** | USBDP/eUSB2 reset, ACPM and DPU addresses from the live device |

Each is shaped for submission to the relevant subsystem list. `SERIES` records the apply order and
the target tree.

## The device tree — why it is shaped the way it is

Documented in full in [`docs/DT-ABI-FINDINGS.md`](docs/DT-ABI-FINDINGS.md). The five requirements:

1. **S-Boot writes `memory@` nodes as 2+1 cells**, not 2+2. A mismatch gives a wrong RAM map and a
   `paging_init` panic with no useful message.
2. **The DTB must be built with `-@`.** Without `__symbols__`, none of S-Boot's six EDTBO overlays
   resolve and the device drops to Download mode.
3. **13 stub labels must already exist**, because some overlays write properties onto them.
4. **6 empty `recovery_dtbo` overlays** keep vendor overlays off the mainline tree while still
   letting S-Boot's selection logic succeed.
5. **`param+0x700200`** is where S-Boot records its boot decision (`0` = Android, `4` = recovery) —
   and writing `0` there before reboot is how a non-Android system returns to Android
   deterministically.

Every device-specific value in the trees — model string, the six memory banks, the debug UART at
`0x11C40000` and its `samsung,dbg-uart-*` properties (baud `0x1c200`, FIFO `0x100`, word length 8),
panel geometry `1440x3088` — was read from the **live device's `/proc/device-tree`**, not copied
from a sibling board and not guessed.

## Verify it

Both trees compile against vanilla `linux-6.17`:

```sh
TREE=/path/to/linux-6.17
DTS=$TREE/arch/arm64/boot/dts/exynos

cpp -nostdinc -undef -x assembler-with-cpp \
    -I "$DTS" -I "$TREE/include" -I "$TREE/arch/arm64/boot/dts" \
    -D__DTS__ dtb/exynos2200-b0s.dts -o /tmp/b0s.pp

dtc -I dts -O dtb -@ -o /tmp/b0s.dtb /tmp/b0s.pp
```

`-@` on the `dtc` line is not optional for a bootable image — see `docs/DT-ABI-FINDINGS.md` §2.

Apply the series:

```sh
git clone --depth 1 -b v6.17 https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
cd linux
for p in ../patches/000*.patch; do git am "$p" || break; done
```

## Scope

This is the **device tree and supporting platform patches**. It is not the whole port: the boot
route onto this hardware (kexec from the stock kernel) and the remaining platform bring-up live
outside this repository.

Nothing here is a Samsung binary. No vendor modules, no firmware, no images — source only.

## License

GPL-2.0-only. See [LICENSE](LICENSE). The device trees and the patches are derivative works of the
Linux kernel and carry the same terms.
