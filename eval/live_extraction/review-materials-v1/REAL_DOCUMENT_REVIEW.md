# Real-document candidate review

**PROPOSED / UNREVIEWED. No inference or human approval.**

20 candidates; zero admitted schema-expressible positives. Most are unsupported/negative controls.
Version minima concern tools or same-device image metadata; no ECU mappings are invented.
Conflicting campaign requirements and broad positive coverage remain missing.

## real-candidate-01: MCUboot / flash-layout

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/imgtool.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
The `--slot-size` argument is required and used to check that the firmware
does not overflow into the swap status area (metadata). If swap upgrades are
not being used, `--overwrite-only` can be passed to avoid adding the swap
status area size when calculating overflow.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-01",
      "start_char": 0,
      "end_char": 74
    },
    "text": "The `--slot-size` argument is required and used to check that the firmware"
  },
  {
    "evidence": {
      "document_id": "real-candidate-01",
      "start_char": 75,
      "end_char": 130
    },
    "text": "does not overflow into the swap status area (metadata)."
  },
  {
    "evidence": {
      "document_id": "real-candidate-01",
      "start_char": 131,
      "end_char": 151
    },
    "text": "If swap upgrades are"
  },
  {
    "evidence": {
      "document_id": "real-candidate-01",
      "start_char": 152,
      "end_char": 225
    },
    "text": "not being used, `--overwrite-only` can be passed to avoid adding the swap"
  },
  {
    "evidence": {
      "document_id": "real-candidate-01",
      "start_char": 226,
      "end_char": 269
    },
    "text": "status area size when calculating overflow."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-02: MCUboot / image-minimum-version

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/imgtool.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
A dependency can be specified in the following way:
`-d "(image_id, image_version)"`. The `image_id` is the number of the image
which the current image depends on. The `image_version` is the minimum version
of that image to satisfy compliance. For example `-d "(1, 1.2.3+0)"` means this
image depends on Image 1 which version has to be at least 1.2.3+0.
```

Proposed formal constraints: **none**. Image dependency metadata has no approved independently updatable ECU mapping; do not split one device into invented ECUs.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 0,
      "end_char": 51
    },
    "text": "A dependency can be specified in the following way:"
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 52,
      "end_char": 85
    },
    "text": "`-d \"(image_id, image_version)\"`."
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 86,
      "end_char": 127
    },
    "text": "The `image_id` is the number of the image"
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 128,
      "end_char": 163
    },
    "text": "which the current image depends on."
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 164,
      "end_char": 206
    },
    "text": "The `image_version` is the minimum version"
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 207,
      "end_char": 243
    },
    "text": "of that image to satisfy compliance."
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 244,
      "end_char": 286
    },
    "text": "For example `-d \"(1, 1.2.3+0)\"` means this"
  },
  {
    "evidence": {
      "document_id": "real-candidate-02",
      "start_char": 287,
      "end_char": 353
    },
    "text": "image depends on Image 1 which version has to be at least 1.2.3+0."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-03: MCUboot / flash-layout

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/readme-zephyr.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
Currently, the two image slots must be contiguous. If you are running
MCUboot as your stage 1 bootloader, `boot_partition` must be configured
so your SoC runs it out of reset. If there are multiple updateable images
then the corresponding primary and secondary partitions must be defined for
the rest of the images too (for example, `slot2_partition` and
`slot3_partition` for Image 1).
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 0,
      "end_char": 50
    },
    "text": "Currently, the two image slots must be contiguous."
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 51,
      "end_char": 69
    },
    "text": "If you are running"
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 70,
      "end_char": 141
    },
    "text": "MCUboot as your stage 1 bootloader, `boot_partition` must be configured"
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 142,
      "end_char": 175
    },
    "text": "so your SoC runs it out of reset."
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 176,
      "end_char": 215
    },
    "text": "If there are multiple updateable images"
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 216,
      "end_char": 291
    },
    "text": "then the corresponding primary and secondary partitions must be defined for"
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 292,
      "end_char": 354
    },
    "text": "the rest of the images too (for example, `slot2_partition` and"
  },
  {
    "evidence": {
      "document_id": "real-candidate-03",
      "start_char": 355,
      "end_char": 386
    },
    "text": "`slot3_partition` for Image 1)."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-04: MCUboot / confirmation-order

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/readme-zephyr.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
The application itself can flashed with regular flash tools, but will
need to be programmed at the offset of the primary slot for this particular
target. Depending on the platform and flash tool you might need to manually
specify a flash offset corresponding to the primary slot starting address. This
is usually not relevant for flash tools that use Intel Hex images (.hex) instead
of raw binary images (.bin) since the former include destination address
information. Additionally you will need to make sure that the flash tool does
not perform a mass erase (erasing the whole of the flash) or else you would be
deleting MCUboot.
These images can also be marked for upgrade, and loaded into the secondary slot,
at which point the bootloader should perform an upgrade.  It is up to
the image to mark the primary slot as "image ok" before the next reboot,
otherwise the bootloader will revert the application.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 0,
      "end_char": 69
    },
    "text": "The application itself can flashed with regular flash tools, but will"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 70,
      "end_char": 145
    },
    "text": "need to be programmed at the offset of the primary slot for this particular"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 146,
      "end_char": 153
    },
    "text": "target."
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 154,
      "end_char": 221
    },
    "text": "Depending on the platform and flash tool you might need to manually"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 222,
      "end_char": 296
    },
    "text": "specify a flash offset corresponding to the primary slot starting address."
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 297,
      "end_char": 301
    },
    "text": "This"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 302,
      "end_char": 382
    },
    "text": "is usually not relevant for flash tools that use Intel Hex images (.hex) instead"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 383,
      "end_char": 455
    },
    "text": "of raw binary images (.bin) since the former include destination address"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 456,
      "end_char": 468
    },
    "text": "information."
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 469,
      "end_char": 533
    },
    "text": "Additionally you will need to make sure that the flash tool does"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 534,
      "end_char": 612
    },
    "text": "not perform a mass erase (erasing the whole of the flash) or else you would be"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 613,
      "end_char": 630
    },
    "text": "deleting MCUboot."
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 631,
      "end_char": 711
    },
    "text": "These images can also be marked for upgrade, and loaded into the secondary slot,"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 712,
      "end_char": 768
    },
    "text": "at which point the bootloader should perform an upgrade."
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 770,
      "end_char": 781
    },
    "text": "It is up to"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 782,
      "end_char": 854
    },
    "text": "the image to mark the primary slot as \"image ok\" before the next reboot,"
  },
  {
    "evidence": {
      "document_id": "real-candidate-04",
      "start_char": 855,
      "end_char": 908
    },
    "text": "otherwise the bootloader will revert the application."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-05: MCUboot / ambiguous-future-guidance

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
Please note that the swap-using-scratch algorithm may be removed in the coming
future.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-05",
      "start_char": 0,
      "end_char": 78
    },
    "text": "Please note that the swap-using-scratch algorithm may be removed in the coming"
  },
  {
    "evidence": {
      "document_id": "real-candidate-05",
      "start_char": 79,
      "end_char": 86
    },
    "text": "future."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-06: MCUboot / scratch-capacity

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
When swap-using-scratch algorithm is used, in addition to the slots of
image areas, the bootloader requires a scratch area to allow for reliable
image swapping. The scratch area must have a size
that is enough to store at least the largest sector that is going to be swapped.
Many devices have small equally sized flash sectors, eg 4K, while others have
variable sized sectors where the largest sectors might be 128K or 256K, so the
scratch must be big enough to store that. The scratch is only ever used when
swapping firmware, which means only when doing an upgrade. Given that, the main
reason for using a larger size for the scratch is that flash wear will be more
evenly distributed, because a single sector would be written twice the number of
times than using two sectors, for example. To evaluate the ideal size of the
scratch for your use case the following parameters are relevant:
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 0,
      "end_char": 70
    },
    "text": "When swap-using-scratch algorithm is used, in addition to the slots of"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 71,
      "end_char": 144
    },
    "text": "image areas, the bootloader requires a scratch area to allow for reliable"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 145,
      "end_char": 160
    },
    "text": "image swapping."
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 161,
      "end_char": 194
    },
    "text": "The scratch area must have a size"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 195,
      "end_char": 275
    },
    "text": "that is enough to store at least the largest sector that is going to be swapped."
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 276,
      "end_char": 353
    },
    "text": "Many devices have small equally sized flash sectors, eg 4K, while others have"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 354,
      "end_char": 432
    },
    "text": "variable sized sectors where the largest sectors might be 128K or 256K, so the"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 433,
      "end_char": 474
    },
    "text": "scratch must be big enough to store that."
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 475,
      "end_char": 509
    },
    "text": "The scratch is only ever used when"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 510,
      "end_char": 568
    },
    "text": "swapping firmware, which means only when doing an upgrade."
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 569,
      "end_char": 589
    },
    "text": "Given that, the main"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 590,
      "end_char": 668
    },
    "text": "reason for using a larger size for the scratch is that flash wear will be more"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 669,
      "end_char": 749
    },
    "text": "evenly distributed, because a single sector would be written twice the number of"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 750,
      "end_char": 792
    },
    "text": "times than using two sectors, for example."
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 793,
      "end_char": 826
    },
    "text": "To evaluate the ideal size of the"
  },
  {
    "evidence": {
      "document_id": "real-candidate-06",
      "start_char": 827,
      "end_char": 891
    },
    "text": "scratch for your use case the following parameters are relevant:"
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-07: MCUboot / bootloader-state-machine

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
For new swaps, MCUboot must inspect a collection of fields to determine which
swap operation to perform.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-07",
      "start_char": 0,
      "end_char": 77
    },
    "text": "For new swaps, MCUboot must inspect a collection of fields to determine which"
  },
  {
    "evidence": {
      "document_id": "real-candidate-07",
      "start_char": 78,
      "end_char": 104
    },
    "text": "swap operation to perform."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-08: MCUboot / image-integrity

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
  * 32-bit magic number must be correct (`IMAGE_MAGIC`).
  * Image must contain an `image_tlv_info` struct, identified by its magic
    (`IMAGE_TLV_PROT_INFO_MAGIC` or `IMAGE_TLV_INFO_MAGIC`) exactly following
    the firmware (`hdr_size` + `img_size`). If `IMAGE_TLV_PROT_INFO_MAGIC` is
    found then after `ih_protect_tlv_size` bytes, another `image_tlv_info`
    with magic equal to `IMAGE_TLV_INFO_MAGIC` must be present.
  * Image must contain a SHA256 TLV.
  * Calculated SHA256 must match SHA256 TLV contents.
  * Image *may* contain a signature TLV.  If it does, it must also have a
    KEYHASH TLV with the hash of the key that was used to sign. The list of
    keys will then be iterated over looking for the matching key, which then
    will then be used to verify the image contents.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 2,
      "end_char": 56
    },
    "text": "* 32-bit magic number must be correct (`IMAGE_MAGIC`)."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 59,
      "end_char": 131
    },
    "text": "* Image must contain an `image_tlv_info` struct, identified by its magic"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 136,
      "end_char": 209
    },
    "text": "(`IMAGE_TLV_PROT_INFO_MAGIC` or `IMAGE_TLV_INFO_MAGIC`) exactly following"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 214,
      "end_char": 253
    },
    "text": "the firmware (`hdr_size` + `img_size`)."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 254,
      "end_char": 287
    },
    "text": "If `IMAGE_TLV_PROT_INFO_MAGIC` is"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 292,
      "end_char": 362
    },
    "text": "found then after `ih_protect_tlv_size` bytes, another `image_tlv_info`"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 367,
      "end_char": 426
    },
    "text": "with magic equal to `IMAGE_TLV_INFO_MAGIC` must be present."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 429,
      "end_char": 463
    },
    "text": "* Image must contain a SHA256 TLV."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 466,
      "end_char": 517
    },
    "text": "* Calculated SHA256 must match SHA256 TLV contents."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 520,
      "end_char": 558
    },
    "text": "* Image *may* contain a signature TLV."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 560,
      "end_char": 591
    },
    "text": "If it does, it must also have a"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 596,
      "end_char": 655
    },
    "text": "KEYHASH TLV with the hash of the key that was used to sign."
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 656,
      "end_char": 667
    },
    "text": "The list of"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 672,
      "end_char": 744
    },
    "text": "keys will then be iterated over looking for the matching key, which then"
  },
  {
    "evidence": {
      "document_id": "real-candidate-08",
      "start_char": 749,
      "end_char": 796
    },
    "text": "will then be used to verify the image contents."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-09: MCUboot / security-policy

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
Downgrade prevention is a feature which enforces that the new image must have a
higher version/security counter number than the image it is replacing, thus
preventing the malicious downgrading of the device to an older and possibly
vulnerable version of its firmware.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-09",
      "start_char": 0,
      "end_char": 79
    },
    "text": "Downgrade prevention is a feature which enforces that the new image must have a"
  },
  {
    "evidence": {
      "document_id": "real-candidate-09",
      "start_char": 80,
      "end_char": 155
    },
    "text": "higher version/security counter number than the image it is replacing, thus"
  },
  {
    "evidence": {
      "document_id": "real-candidate-09",
      "start_char": 156,
      "end_char": 231
    },
    "text": "preventing the malicious downgrading of the device to an older and possibly"
  },
  {
    "evidence": {
      "document_id": "real-candidate-09",
      "start_char": 232,
      "end_char": 267
    },
    "text": "vulnerable version of its firmware."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-10: MCUboot / conditional-build-feature

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
During the software based downgrade prevention the image version numbers are
compared. This feature is enabled with the `MCUBOOT_DOWNGRADE_PREVENTION`
option. In this case downgrade prevention is only available when the
overwrite-based image update strategy is used (i.e. `MCUBOOT_OVERWRITE_ONLY`
is set).
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 0,
      "end_char": 76
    },
    "text": "During the software based downgrade prevention the image version numbers are"
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 77,
      "end_char": 86
    },
    "text": "compared."
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 87,
      "end_char": 150
    },
    "text": "This feature is enabled with the `MCUBOOT_DOWNGRADE_PREVENTION`"
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 151,
      "end_char": 158
    },
    "text": "option."
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 159,
      "end_char": 219
    },
    "text": "In this case downgrade prevention is only available when the"
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 220,
      "end_char": 271
    },
    "text": "overwrite-based image update strategy is used (i.e."
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 272,
      "end_char": 296
    },
    "text": "`MCUBOOT_OVERWRITE_ONLY`"
  },
  {
    "evidence": {
      "document_id": "real-candidate-10",
      "start_char": 297,
      "end_char": 305
    },
    "text": "is set)."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-11: MCUboot / security-counter

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
Each signed image can contain a security counter in its protected TLV area, which
can be added to the image using the `-s` option of the [imgtool](imgtool.md) script.
During the hardware based downgrade prevention (alias rollback protection) the
new image's security counter will be compared with the currently active security
counter value which must be stored in a non-volatile and trusted component of
the device. It is beneficial to handle this counter independently from image
version number:
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 0,
      "end_char": 81
    },
    "text": "Each signed image can contain a security counter in its protected TLV area, which"
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 82,
      "end_char": 166
    },
    "text": "can be added to the image using the `-s` option of the [imgtool](imgtool.md) script."
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 167,
      "end_char": 245
    },
    "text": "During the hardware based downgrade prevention (alias rollback protection) the"
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 246,
      "end_char": 326
    },
    "text": "new image's security counter will be compared with the currently active security"
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 327,
      "end_char": 404
    },
    "text": "counter value which must be stored in a non-volatile and trusted component of"
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 405,
      "end_char": 416
    },
    "text": "the device."
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 417,
      "end_char": 481
    },
    "text": "It is beneficial to handle this counter independently from image"
  },
  {
    "evidence": {
      "document_id": "real-candidate-11",
      "start_char": 482,
      "end_char": 497
    },
    "text": "version number:"
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-12: MCUboot / multi-image-dependency

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/design.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
The dependencies between images can be described with additional TLV entries in
the protected TLV area after the end of an image. There can be more than one
dependency entry, but in practice if the platform only supports two individual
images then there can be maximum one entry which reflects to the other image.
```

Proposed formal constraints: **none**. Image dependency metadata has no approved independently updatable ECU mapping; do not split one device into invented ECUs.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-12",
      "start_char": 0,
      "end_char": 79
    },
    "text": "The dependencies between images can be described with additional TLV entries in"
  },
  {
    "evidence": {
      "document_id": "real-candidate-12",
      "start_char": 80,
      "end_char": 129
    },
    "text": "the protected TLV area after the end of an image."
  },
  {
    "evidence": {
      "document_id": "real-candidate-12",
      "start_char": 130,
      "end_char": 156
    },
    "text": "There can be more than one"
  },
  {
    "evidence": {
      "document_id": "real-candidate-12",
      "start_char": 157,
      "end_char": 235
    },
    "text": "dependency entry, but in practice if the platform only supports two individual"
  },
  {
    "evidence": {
      "document_id": "real-candidate-12",
      "start_char": 236,
      "end_char": 313
    },
    "text": "images then there can be maximum one entry which reflects to the other image."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-13: MCUboot / build-prerequisite

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/PORTING.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
* `MCUboot` requires a configuration file, which can be included as
   mcuboot_config/mcuboot_config.h, which configures various options
   (that begin with MCUBOOT_).
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-13",
      "start_char": 0,
      "end_char": 67
    },
    "text": "* `MCUboot` requires a configuration file, which can be included as"
  },
  {
    "evidence": {
      "document_id": "real-candidate-13",
      "start_char": 71,
      "end_char": 136
    },
    "text": "mcuboot_config/mcuboot_config.h, which configures various options"
  },
  {
    "evidence": {
      "document_id": "real-candidate-13",
      "start_char": 140,
      "end_char": 167
    },
    "text": "(that begin with MCUBOOT_)."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-14: MCUboot / hardware-api-prerequisite

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/PORTING.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
* `MCUboot` requires that the target provides a `flash` API with ability to
  get the flash's minimum write size, and read/write/erase individual sectors.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-14",
      "start_char": 0,
      "end_char": 75
    },
    "text": "* `MCUboot` requires that the target provides a `flash` API with ability to"
  },
  {
    "evidence": {
      "document_id": "real-candidate-14",
      "start_char": 78,
      "end_char": 154
    },
    "text": "get the flash's minimum write size, and read/write/erase individual sectors."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-15: MCUboot / crypto-build-dependency

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/PORTING.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
* `MCUboot` doesn't bundle a cryptographic library, which means the target
  OS must already have it bundled. The supported libraries at the moment are
  either `Mbed TLS` or the set `tinycrypt` + `Mbed TLS` (where `Mbed TLS` is
  used to provide functionality not existing in `tinycrypt`).
```

Proposed formal constraints: **none**. Image dependency metadata has no approved independently updatable ECU mapping; do not split one device into invented ECUs.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-15",
      "start_char": 0,
      "end_char": 74
    },
    "text": "* `MCUboot` doesn't bundle a cryptographic library, which means the target"
  },
  {
    "evidence": {
      "document_id": "real-candidate-15",
      "start_char": 77,
      "end_char": 109
    },
    "text": "OS must already have it bundled."
  },
  {
    "evidence": {
      "document_id": "real-candidate-15",
      "start_char": 110,
      "end_char": 151
    },
    "text": "The supported libraries at the moment are"
  },
  {
    "evidence": {
      "document_id": "real-candidate-15",
      "start_char": 154,
      "end_char": 228
    },
    "text": "either `Mbed TLS` or the set `tinycrypt` + `Mbed TLS` (where `Mbed TLS` is"
  },
  {
    "evidence": {
      "document_id": "real-candidate-15",
      "start_char": 231,
      "end_char": 290
    },
    "text": "used to provide functionality not existing in `tinycrypt`)."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-16: MCUboot / toolchain-version

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/readme-espressif.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
*Current compatible ESP-IDF version for HAL sources is `v5.1.6`*
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-16",
      "start_char": 0,
      "end_char": 64
    },
    "text": "*Current compatible ESP-IDF version for HAL sources is `v5.1.6`*"
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-17: MCUboot / no-supported-requirement

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/serial_recovery.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
MCUboot implements a Simple Management Protocol (SMP) server.
SMP is a basic transfer encoding for use with the MCUmgr management protocol. 
See the Zephyr [Device Management](https://docs.zephyrproject.org/latest/services/device_mgmt/index.html#device-mgmt) documentation for more information about MCUmgr and SMP.
```

Proposed formal constraints: **none**. Descriptive implementation statement does not establish any supported campaign requirement.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-17",
      "start_char": 0,
      "end_char": 61
    },
    "text": "MCUboot implements a Simple Management Protocol (SMP) server."
  },
  {
    "evidence": {
      "document_id": "real-candidate-17",
      "start_char": 62,
      "end_char": 139
    },
    "text": "SMP is a basic transfer encoding for use with the MCUmgr management protocol."
  },
  {
    "evidence": {
      "document_id": "real-candidate-17",
      "start_char": 141,
      "end_char": 315
    },
    "text": "See the Zephyr [Device Management](https://docs.zephyrproject.org/latest/services/device_mgmt/index.html#device-mgmt) documentation for more information about MCUmgr and SMP."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-18: MCUboot / threat-model-limitation

[Source](https://github.com/mcu-tools/mcuboot/blob/6d3b3d2c38ab20c242e5b9abb04d050086383eb2/docs/encrypted_images.md)
Revision: 6d3b3d2c38ab20c242e5b9abb04d050086383eb2; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
It does not protect against the possibility of attaching a JTAG and
reading the internal flash memory, or using some attack vector that
enables dumping the internal flash in any way.
```

Proposed formal constraints: **none**. Build, image-format, flash, security or application-health semantics are outside requires/mutex/order/ignition-and-battery constraints.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-18",
      "start_char": 0,
      "end_char": 67
    },
    "text": "It does not protect against the possibility of attaching a JTAG and"
  },
  {
    "evidence": {
      "document_id": "real-candidate-18",
      "start_char": 68,
      "end_char": 135
    },
    "text": "reading the internal flash memory, or using some attack vector that"
  },
  {
    "evidence": {
      "document_id": "real-candidate-18",
      "start_char": 136,
      "end_char": 182
    },
    "text": "enables dumping the internal flash in any way."
  }
]
```

Admission blockers: Independent human semantic review missing; No approved source-component/ECU inventory mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-19: Zephyr / build-prerequisite

[Source](https://docs.zephyrproject.org/latest/services/device_mgmt/dfu.html)
Revision: UNPINNED; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
You need to build and flash MCUboot itself on your device
```

Proposed formal constraints: **none**. No supported installed ECU-version requirement follows from this statement.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-19",
      "start_char": 0,
      "end_char": 57
    },
    "text": "You need to build and flash MCUboot itself on your device"
  }
]
```

Admission blockers: Independent human review missing; Immutable source/context/license capture incomplete; No approved ECU mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.

## real-candidate-20: PX4 / no-supported-requirement

[Source](https://docs.px4.io/v1.18/en/advanced_config/bootloader_update)
Revision: v1.18 documentation URL; immutable commit unresolved; publication date unknown; retrieved 2026-11-06T18:13:54.614946+00:00.

```text
The PX4 Bootloader is used to load firmware for Pixhawk boards (PX4FMU, PX4IO).
```

Proposed formal constraints: **none**. No supported installed ECU-version requirement follows from this statement.

Exact ingested evidence segments:
```json
[
  {
    "evidence": {
      "document_id": "real-candidate-20",
      "start_char": 0,
      "end_char": 79
    },
    "text": "The PX4 Bootloader is used to load firmware for Pixhawk boards (PX4FMU, PX4IO)."
  }
]
```

Admission blockers: Independent human review missing; Immutable source/context/license capture incomplete; No approved ECU mapping
- [ ] Source context, license and revision reviewed.
- [ ] Mapping and unsupported/negative label reviewed.
- [ ] Reviewer/date/adjudication recorded; approval remains pending.
