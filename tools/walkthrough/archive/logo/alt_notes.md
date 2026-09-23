# Meltemi Hand — fizz release alternative

One design attempt. Only the two circle centers changed; no stroke edits.

| Bubble | Before (cx, cy, r) | After (cx, cy, r) |
| --- | --- | --- |
| Largest | (1580, 430, 62) | (1588, 548, 62) |
| Smaller | (1635, 272, 34) | (1650, 430, 34) |

The large bubble now overlaps the outgoing shoulder of the second crest, so the white disc breaks out of the yellow gesture. The smaller bubble continues along the same up-right trajectory: delta (+62, -118), center distance 133.30 units and edge gap 37.30 units. Two bubbles retain the approved rhythm and avoid extra visual detail.

Viewed against the supplied original preview: the release is clear at 1024 px and remains attached at 128 px. At 32 px the largest bubble remains visible as a white spot (nominal diameter 2.07 px); the smaller bubble and intervening gap lose definition. No second attempt was needed.

## Validation output

```text
XML parse: PASS (alternative and square crop).
Byte preservation: PASS; removing only the two circle elements yields byte-identical original/alternative files. Frame, rect, path and all three text elements unchanged.
Palette: PASS #1B4F8A, #F5C518, #FFFFFF (exactly three SVG colours; PNG edge antialiasing adds blended pixels).
Prohibited features: PASS; no opacity, gradients, filters, styles or additional element types.
Text elements verbatim: PASS (3/3, byte comparison; literal UTF-8 middle dots).
Clear-space zone: PASS; all mark geometry is above y=1440. Only the unchanged wordmark foreground occupies x=825–1735, y=1440–1772; background rect excluded. Rendered wordmark bounds approximately (966.875, 1578.75, 1598.75, 1663.125).
Mark bounds: PASS; conservative control-hull/stroke envelope plus circles = (808, 396.0, 1684.0, 1256), inside x=740–1820, y=200–1440.
Crop bounds: PASS; viewBox="320 0 1920 1920"; inner content byte-identical to alternative. Rendered foreground bounds approximately (809.375, 116.25, 1748.75, 1841.25), fully inside crop. Background intentionally bleeds beyond crop.
Size: PASS; alternative 1135 bytes; square SVG 1164 bytes; both under 12 KB.
Renders: PASS; Quick Look outputs 1024×1024, 128×128 and 32×32 PNGs. All three inspected with view_image.
Shoulder overlap: PASS; nearest second-crest centerline distance 58.94 units at t=0.7077, less than stroke half-width + bubble radius (118 units).
```

## Render commands

```sh
qlmanage -t -s 1024 -o tools/walkthrough/logo tools/walkthrough/logo/dir1_final_alt_sq.svg
qlmanage -t -s 128 -o tools/walkthrough/logo/small/128 tools/walkthrough/logo/dir1_final_alt_sq.svg
qlmanage -t -s 32 -o tools/walkthrough/logo/small/32 tools/walkthrough/logo/dir1_final_alt_sq.svg
```

Quick Look initially failed sandbox initialization; rerunning with approved sandbox escalation succeeded. This was a render retry, not a design revision. Existing files were not edited; no git commands were used.
