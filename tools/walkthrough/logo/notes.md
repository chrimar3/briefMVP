# Meltemi Hand — refined lockup

## Changes and client evidence

| Change from dir1 | Reason and source citation |
|---|---|
| Replaced the variable-width closed brush silhouette with a single 112-unit stroke, two clean-cut terminals and seven path segments after the initial move. Removed the entry flare and hooked exit. | A deliberate, restrained gesture for premium everyday use: [source_id: background_brand_guidelines, location: Tone (guidance); Category no-gos]; adult premium-tea buyers: [source_id: transcript_kickoff, location: 00:03:41, DIMITRIS]; [source_id: creative_brief_opus, location: §3 Feel; §4 Tone of voice]. |
| Kept the two wind crests; made the central descent near vertical, the valley deep and the right outer leg nearly straight. The Μ echo is secondary to the wind silhouette. | Greek ownership of a modern category and premium summer: [source_id: transcript_kickoff, location: 00:06:02, DIMITRIS]; quietly proud and premium: [source_id: creative_brief_opus, location: §3 Feel]. No meander, column, sun or beach imagery: [source_id: background_brand_guidelines, location: Category no-gos]. |
| Moved the bubbles down and left from the original loose vertical pair, close to the final crest, with an outward/upward trajectory and decreasing radii 62 → 34. The largest bubble sits just above the crest's outgoing shoulder, separated by a small release gap. | Connect wind to carbonation so sparkling tea is communicated by one gesture: [source_id: transcript_kickoff, location: 00:02:05, DIMITRIS]; wind/summer character: [source_id: transcript_kickoff, location: 00:06:02, DIMITRIS]. This is the design interpretation requested in refinement point 2, not a new client claim. |
| Kept Citrus Yellow on Aegean Blue and white bubbles/name/caption; retained the source category line unchanged under the verbatim-text hard constraint. Added no decoration or claims. | [source_id: background_brand_guidelines, location: Color & visual; Claims — hard rules; Category no-gos]; [source_id: transcript_kickoff, location: 00:06:02, DIMITRIS]. See the colour conflict below. |
| Preserved the full Latin name and exact category/zero-sugar wording, with generous separation around the name. | [source_id: background_brand_guidelines, location: Brand name usage]; category unfamiliarity: [source_id: transcript_kickoff, location: 00:02:05, DIMITRIS]; zero sugar: [source_id: transcript_kickoff, location: 00:06:02, DIMITRIS]. |
| Supplied square and portrait wrappers of identical content, plus 128 px and 32 px raster checks; used an editable open path suitable for drawing on. | [source_id: rfp_meltemi, location: §4 Απαιτήσεις καμπάνιας]; [source_id: creative_brief_opus, location: §3 Do]. |

The supplied creative brief has no source_id metadata; `creative_brief_opus` above identifies the supplied file `runs/tier3/creative/creative_brief_opus.md`, not a newly asserted primary source. Transcript audience guidance takes precedence over the superseded RFP Gen Z audience.

## Animation — three sentences

The single yellow stroke draws on with the wind from its lower-left cut terminal, across the first crest and deep valley, over the second crest and down to its final cut terminal. As the wind passes the second crest, white bubbles release from its outgoing shoulder and rise along the illustrated trajectory, diminishing from the largest bubble to the smallest. The continuous open centreline and independent circle elements permit a stroke-dash reveal and positional bubble animation without any geometric obstruction; no animation is embedded in the SVG. [source_id: rfp_meltemi, location: §4 Απαιτήσεις καμπάνιας]

## Attempts and visual checks

Four render attempts; one geometry design. Attempt 1 passed the square and square small-size checks but Quick Look returned a blue portrait thumbnail with missing explicit dimensions. Attempts 2 and 3 used explicit portrait dimensions (1080×1920, then 576×1024); Quick Look scaled to the thumbnail width and clipped the lower part of the portrait. Attempt 4 used a responsive width/height on the portrait wrapper, preserving the required viewBox, and correctly fit the whole composition into Quick Look's square viewport.

All attempts were rendered with `qlmanage -t -s 1024 -o tools/walkthrough/logo <file>` and `-s 128` / `-s 32` into `small/128/` and `small/32/`, then inspected with `view_image`. Quick Look needed execution outside the filesystem sandbox because its sandbox initialization failed. The portrait renderer's final square carriers are retained verbatim as `dir1_final_916_ql.png` in each output folder; the central portrait rectangles were extracted losslessly, without scaling, to `dir1_final_916.svg.png` using Pillow (1024: x=224..800; 128: x=28..100; 32: x=7..25). These rectangles correspond exactly to the requested x=740..1820 viewBox, and the extracted portraits were also inspected with `view_image`.

At 1024 px, the complete name and category read at a glance in the portrait crop, and no foreground is clipped. At 128 px, the name remains identifiable; the category is very small and is not comfortably readable. At 32 px, both crests, the deep central valley and the largest white bubble remain distinguishable in the 32×32 square and the stricter 18×32 portrait; the smaller bubble is only a tiny antialiased point and the text is not readable. The mark passes the requested favicon geometry check, but the full lockup cannot communicate its category at favicon size.

## Constraint conflicts and remaining limitations

Refinement point 4 asks for a white category line, but the hard requirement to retain all three text elements exactly fixes that line's `fill="#F5C518"`. The hard constraint was prioritized: the category remains yellow, and the three literal elements below are unchanged. The hard constraint also retains `MOCK-UP · NOT FOR DELIVERY`; this is a refined design file with that mandated caption, not an unlabeled production release. Fonts remain the prescribed local fallback stack, so exact glyph bounds may vary by machine; the listed text bounds are measured from this machine's Quick Look render.

## Validation output

```text
XML parse: PASS, master and both crop wrappers.
Master viewBox: PASS, 0 0 2560 1920.
First child: PASS, full-frame 2560 x 1920 rect, #1B4F8A.
Palette: PASS, exactly #1B4F8A, #F5C518, #FFFFFF (SVG paint values; PNG antialiasing creates edge shades).
Prohibited features: PASS, no gradients, opacity, filters, masks, images, style, script, external font references, animation or non-XML entities.
Text: PASS, all three complete text elements match dir1.svg byte-for-byte, including attribute order and literal middle dots.
Geometry: PASS, one open constant-width 112-unit path (butt caps, round joins), two circles with radii 62 > 34; no additional elements.
Mark bounds: PASS, conservative control-hull plus half-stroke bounds x 808–1669, y 238–1256, within x 740–1820 / y 200–1440.
Clear-space zone: PASS, no foreground except the wordmark in x 825–1735 / y 1440–1772; background rect necessarily spans the zone.
Rendered wordmark bounds: approximately (966.875, 1578.75, 1598.75, 1661.25); visible height 82.50 units.
Clear space: PASS, using a conservative 112-unit wordmark-height allowance; mark bottom <=1256, name top 1578.75, name bottom 1661.25, category top 1805.62; left/right crop margins 226.88/221.25 units.
Square crop: PASS, viewBox 320 0 1920 1920; x 320–2240 / y 0–1920.
Portrait crop: PASS, viewBox 740 0 1080 1920; x 740–1820 / y 0–1920.
Crop content: PASS, exact same inner XML as master.
Rendered text bounds fit portrait: PASS; caption (815.0, 116.25, 1746.875, 151.875); category (863.75, 1805.625, 1696.25, 1841.25).
Master size: PASS, 1135 bytes < 12,000 bytes.
Square SVG size: 1164 bytes; portrait SVG size: 1164 bytes.
Final PNG sizes: square 1024x1024 / 128x128 / 32x32; portrait 576x1024 / 72x128 / 18x32.
Visual inspection: all six renders viewed after each render pass, plus all three extracted final portrait crops.
```

## Three verbatim text elements

```xml
<text x="1280" y="150" text-anchor="middle" font-family="'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif" font-weight="700" font-size="44" letter-spacing="10" fill="#FFFFFF">MOCK-UP · NOT FOR DELIVERY</text>
<text x="1280" y="1660" text-anchor="middle" font-family="'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif" font-weight="700" font-size="112" letter-spacing="-3" fill="#FFFFFF">Meltemi Fizz</text>
<text x="1280" y="1840" text-anchor="middle" font-family="'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif" font-weight="700" font-size="44" letter-spacing="6" fill="#F5C518">SPARKLING TEA · ZERO SUGAR</text>
```
