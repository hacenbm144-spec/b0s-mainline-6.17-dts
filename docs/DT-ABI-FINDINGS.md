# DT-ABI findings — what Samsung's S-Boot requires from a mainline device tree

Everything below was established by building device trees, booting them through S-Boot, and
watching where the boot stopped. Each row is a **cause → observed failure → fix** triple, and each
was reproduced more than once.

This is the part of the work that is reusable by anyone else booting mainline on a Samsung
Exynos device. None of it is documented publicly anywhere I could find.

---

## 1. The 2+1 cell trap — S-Boot writes `memory@` nodes as 2+1

**Symptom:** the kernel starts, then panics in `paging_init` with
`Failed to allocate page table page`.

**Cause:** mainline's `exynos2200.dtsi` declares at the root:

```dts
#address-cells = <2>;
#size-cells = <2>;
```

but S-Boot's own EDTBO overlays write `memory@…` nodes using **2 address cells and 1 size cell**.
The overlay therefore does not match the root's cell layout, the memory nodes are interpreted with
the wrong stride, and the kernel builds a bogus RAM map.

**Fix:** a `-k` (kexec/bootloader-compatible) variant of the device tree whose root is
`#address-cells = <2>; #size-cells = <1>;` when booting through S-Boot. The native tree keeps 2+2.

**Why it matters:** this is invisible in the source. It only appears when S-Boot's overlays are
applied on top, so a DT that is perfectly valid for `dtc` can still produce a broken RAM map.

> Two separate trees are therefore maintained: `exynos2200-b0s.dts` (2+2, mainline-native) and
> `exynos2200-b0s-kx.dts` (2+1, S-Boot-compatible).

---

## 2. `-@` is mandatory — without `__symbols__` S-Boot cannot apply its overlays

**Symptom:** S-Boot prints `DT overlay fail` and drops to **Download mode**. The device does not
boot at all.

**Cause:** S-Boot applies **6 EDTBO overlays** to whatever DT it is handed. To resolve a fragment's
`target-path`, the *base* blob must contain a `__symbols__` node. A DTB built without `-@` has no
`__symbols__`, so every overlay fails to resolve.

**Fix:** build the DTB with overlay support:

```sh
make DTC_FLAGS=-@ exynos2200-b0s-kx.dtb
```

**This single flag is the difference between "boots" and "hard-bricks into Download mode".** It is
not discoverable from any error message that names the flag.

---

## 3. The 13 EDTBO stub labels must exist

**Symptom:** same `DT overlay fail` → Download mode, even with `-@`.

**Cause:** the overlays S-Boot applies do not only *target* nodes — some **add properties to
labels that must already exist**. If a label is missing, the overlay's `__overlay__` write fails
and S-Boot rejects the whole set.

**Fix:** declare **13 stub labels** in the board DTS (empty nodes with the exact names S-Boot's
overlays reference). With them present the same overlays resolve and the boot proceeds.

**Necessary companion:** ship **6 empty `recovery_dtbo` overlays** carrying only the stock
selection properties, so that no *vendor* overlay lands on the mainline tree while the selection
logic still succeeds.

---

## 4. `param+0x700200` — where S-Boot records the boot decision

**Location:** block device `/dev/block/sda5` (Samsung `param` partition), byte offset
**`+0x700200`**, 32-bit little-endian.

| value | meaning |
|---|---|
| `0x00000000` | normal Android boot |
| `0x00000004` | boot the **recovery** partition |

**Behaviour measured:**

- S-Boot **sets** this field when it decides to enter recovery (`= 4`).
- Android **clears it back to 0** on the way up — so in a running Android system the field reads 0
  regardless of how the phone got there.
- It is therefore an **output** of S-Boot's decision, not a persistent flag you can read to learn
  history. Comparing it across boots is only meaningful while a non-Android system is running.

**Use:** this is how a mainline kernel can return to Android deterministically — write `0` to
`param+0x700200` before rebooting, and the next boot is Android with no key combo:

```sh
printf '\x00\x00\x00\x00' | dd of=/dev/block/sda5 bs=1 seek=$((0x700200)) conv=notrunc,fsync
```

**Caveat:** the surrounding counters in `param` are not stable and must not be used as
identifiers. Only the field at `+0x700200` has a defined meaning.

---

## 5. `dtb-hw_rev` — board revision selection

S-Boot's overlay set is chosen by a **hardware-revision property** in the DT
(`dtb-hw_rev`). Overlay entries cover board-rev ranges (observed: `0x13`–`0x20`). The selected
overlay is visible at runtime in S-Boot's own log. Getting this property absent or out of range
leaves S-Boot with no overlay to apply, which surfaces as the same overlay failure in §2/§3.

---

## 6. What this means for the submission

The device tree is not "a config file". A working tree for this device requires:

| requirement | why |
|---|---|
| root cells matching **S-Boot's overlay layout** (2+1 for the boot path) | otherwise the RAM map is wrong and `paging_init` panics |
| built with **`-@`** | otherwise `__symbols__` is absent and overlays cannot resolve |
| **13 labeled stubs** present | otherwise overlay property-writes fail |
| **6 empty `recovery_dtbo`** overlays | keeps vendor overlays off the mainline tree while selection succeeds |
| `dtb-hw_rev` in range | selects which overlay set S-Boot applies |

All five were found the hard way, each by a boot that stopped at a different point. Any one of them
missing produces a failure whose message does not name the cause.

---

## Verification

The trees in this repository compile cleanly against vanilla **linux-6.17**:

```
exynos2200-b0s.dts      dtc -@ → 59,541 B dtb, 331 nodes   (2+2, mainline-native)
exynos2200-b0s-kx.dts   dtc -@ → 62,063 B dtb, 358 nodes   (2+1, S-Boot-compatible)
```

and `arch/arm64/boot/dts/exynos/Makefile` lists:

```
exynos2200-b0s.dtb
exynos2200-b0s-kx.dtb
exynos2200-b0s-native.dtb
```

Every device-specific value in the trees (model string, six memory banks, debug UART address and
its `samsung,dbg-uart-*` properties, FIFO size `0x100`, baud `0x1c200`, word length 8, panel
`1440x3088`) was read from the **live device's `/proc/device-tree`**, not copied from a sibling
board and not guessed.
