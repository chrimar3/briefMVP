# Meltemi Fizz — three wind directions

MOCK-UP · NOT FOR DELIVERY  
Synthetic Meltemi Beverages demo brand. Every asset is a walkthrough illustration.

Read first: fixtures/northlight_01/background_brand_guidelines.md. Reviewed both the rejected flat lockup and its can application. All three directions use an Aegean Blue #1B4F8A field, Citrus Yellow #F5C518 wind gesture and white #FFFFFF bubbles; all retain the full Latin-script name and prescribed text. Each main gesture is one closed, flat-filled path, without a surrounding badge. No health claims or alcohol imagery.

“Ownable” below describes a visual design rationale, not a trademark clearance finding.

## 1 — Meltemi Hand

[SVG](dir1.svg) · [1024 px preview](dir1.svg.png) · [128 px test](small/dir1.svg.png)

**Idea.** One continuous, wind-bent stroke climbs through two unequal crests, giving the gust the rhythm of the initial in Meltemi. Two detached white bubbles carry that upward movement into fizz.

**Why it is ownable.** The asymmetric double crest, deep central cut and flared terminals form a repeatable signature tied to the name. Its slant and upward bubble release connect that signature to moving air and carbonation, while the complete name remains underneath.

**What could go wrong on a can.** Curvature could compress the central opening and make the gesture read as ordinary italic lettering; the sharp entry and exit tips could soften in print. Keep the central valley on the front-facing panel and avoid wrapping a terminal out of sight. The wind association is suggestive rather than a literal weather pictogram.

**At 128 px.** Both crests, the central opening and both bubbles remain visible. The tips soften, but the silhouette survives without relying on them; no small-size redraw was needed.

## 2 — Zero, Unbuttoned

[SVG](dir2.svg) · [1024 px preview](dir2.svg.png) · [128 px test](small/dir2.svg.png)

**Idea.** A leaning zero is pulled open at its upper right by a single long gust. Its top edge stretches into a wind tail while two bubbles escape above the opening, bringing zero sugar and fizz into the same gesture.

**Why it is ownable.** The open shoulder, sharply cut lower terminal and extended top lip distinguish it from a closed wellness ring. The name supplies the wind story and the category line anchors the zero reading; nothing sits inside the counter.

**What could go wrong on a can.** If the opening wraps around the can, this could regress to a generic oval, or be read as a letter rather than zero. The tail needs to stay on the front panel. This has the greatest residual resemblance to the rejected ring territory, despite its different construction.

**At 128 px.** The open shoulder, tail and two bubbles remain separate and the counter stays clear. An initial white accent near the opening suggested a leaf; it was removed and both sizes re-rendered. The final simpler mark holds.

## 3 — Northbound

[SVG](dir3.svg) · [1024 px preview](dir3.svg.png) · [128 px test](small/dir3.svg.png)

**Idea.** A reinterpreted meteorological wind barb becomes one leaning staff with two swept-back arms. A loose column of three white bubbles rises beside it, turning the weather instrument into a sparkling-tea signal.

**Why it is ownable.** The pairing of a broad asymmetric weather glyph and buoyant bubbles gives Meltemi Fizz a specific wind-and-carbonation silhouette. The arms bow as if under pressure, introducing quiet humour without adding a face or a beach motif; this is an invented emblem, not a calibrated wind-speed or compass reading.

**What could go wrong on a can.** The tall staff can resemble an antenna or a botanical sprig if the arms disappear around the sides. The disconnected bubbles also need a clear front-facing area so they read with the staff. Keep the two open gaps broad and the complete emblem together.

**At 128 px.** The staff, both arms and all three bubbles remain distinct. This is the most robust geometric silhouette of the set; no simplification was needed.

## Validation

Each file was parsed using the requested Python xml.dom.minidom command. Additional assertions checked the exact SVG frame, first full-frame blue rectangle, size below 12 KB, exactly the three specified hex colours, all three text elements verbatim (including caption attribute order), and absence of opacity, gradients, filters, masks, images, styles, scripts and external references.

For these simple absolute-coordinate paths, bounding every Bézier control point gives a conservative enclosure of the entire filled mark. Circle bounds include their full radius. Those enclosures sit inside x 740–1820 and y 200–1440, so the marks survive both specified crops. Every mark ends above the clear-space zone; the caption and category line sit outside it. The full-frame background is the necessary field exception, and the wordmark is the only foreground element in the reserved zone.

Quick Look was run individually for every SVG with -s 1024 and -s 128, using the requested output directories. All six PNGs were inspected with view_image and have no error banner. Quick Look adds white padding above and below the landscape frame in its square thumbnails; the SVG itself has a full blue field. At 128 px, the mark is the test target: the prescribed caption and category line are too small to read. No physical print or can-wrap proof is implied.

Actual validation output:

```text
dir1.svg: PASS | 1342 bytes | XML parse | exact frame/background | exactly 3 palette colours | 3 verbatim text elements | prohibited features absent | clear space | both crop bounds
  Conservative mark bounds (x_min, y_min, x_max, y_max): (810, 240, 1734, 1238)
dir2.svg: PASS | 1178 bytes | XML parse | exact frame/background | exactly 3 palette colours | 3 verbatim text elements | prohibited features absent | clear space | both crop bounds
  Conservative mark bounds (x_min, y_min, x_max, y_max): (810, 236, 1736, 1350)
dir3.svg: PASS | 1172 bytes | XML parse | exact frame/background | exactly 3 palette colours | 3 verbatim text elements | prohibited features absent | clear space | both crop bounds
  Conservative mark bounds (x_min, y_min, x_max, y_max): (876, 216, 1656, 1300)
Quick Look: PASS | 3 thumbnails at 1024 px + 3 at 128 px; all six visually inspected, no XML error banners.
Small-size review: PASS | all three mark silhouettes remain distinct; required small caption/category text is not readable at 128 px.
```

## Design lead ranking

1. **Meltemi Hand** — first choice. Its distinctive double-crest gesture has the strongest direct connection to the name, with enough motion and bubble lift to support the wind story. It feels like a brand signature rather than a category badge.
2. **Northbound** — strongest alternative. The weather reference is more explicit and the silhouette is especially robust; its main tradeoff is possible antenna/sprig recognition.
3. **Zero, Unbuttoned** — clearest zero-sugar idea. The wind opening is useful, but its oval ancestry leaves it closest to the rejected territory and least specific to Meltemi.
