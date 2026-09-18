Use the imagegen skill in its default built-in `image_gen` tool mode (no API key, no CLI fallback) to generate TWO packaging mock-ups of the same product on a CAN, one per built-in call, for the shadow-mode creative brief on sheet 09 of WALKTHROUGH.html. Synthetic demo brand (fixtures/northlight_01/); walkthrough illustration labelled as a mock-up, never a deliverable. Read fixtures/northlight_01/background_brand_guidelines.md first: its rules are hard constraints.

Two reference images are attached to this prompt:
- Image 1 (reference, "previous logo"): the walkthrough's original key-visual lockup — a flat Aegean Blue field, five horizontal white wind lines of varying weight running across it, a thick Citrus Yellow ring that reads as a zero with a single white tea leaf inside it, the wordmark "Meltemi Fizz" in white bold sans-serif beneath the ring, and the line "SPARKLING TEA · ZERO SUGAR" in Citrus Yellow beneath the wordmark. Also available as a file: tools/walkthrough/kv_previous_logo_ref.png.
- Image 2 (reference, "bottle label"): the label design from the earlier bottle mock-up — the same blue field, yellow ring with the white leaf, wordmark and line, but no wind lines. Also available as a file: tools/walkthrough/kv_packaging_mockup.png.

Shared specification for BOTH images (keep the scene identical so the two can be compared side by side):
Use case: product-mockup
Asset type: packaging mock-up plate for a presentation sheet, 1:1 square
Primary request: premium product photograph of a single standard 330 ml aluminium can of "Meltemi Fizz" sparkling tea, zero sugar, standing upright on a flat surface
Can format: a STANDARD 330 ml can (classic soft-drink proportions, about 66 mm wide by 115 mm tall), matte printed body, plain silver top and pull tab. NOT a slim can, NOT a sleek 250 ml or 355 ml tall can, NOT a stubby can: slim or tall cans read as hard seltzer or beer, which the brand forbids.
Scene/backdrop: plain, evenly lit, flat light-neutral studio backdrop (one flat tone, no gradient, no scenery), a single soft contact shadow
Style/medium: clean product photography, catalogue quality
Composition/framing: centered, slight three-quarter angle, generous padding, the can about 70% of the image height
Lighting/mood: soft studio softbox light, clean highlights, premium-everyday mood (modern Greek, confident, quiet)
Colour rules: the printed artwork uses exactly three flat colours, Aegean Blue #1B4F8A, Citrus Yellow #F5C518 and white; no gradients or gloss painted into the artwork itself (the can's metal may catch light naturally)
Text (verbatim, spell exactly, Latin script, never abbreviated, never transliterated): "Meltemi Fizz" (M-e-l-t-e-m-i space F-i-z-z) · "SPARKLING TEA · ZERO SUGAR" · and a small caption in the top-left corner of the image reading "MOCK-UP · NOT FOR DELIVERY"
Constraints: no alcohol association of any kind; no beach, party, bar, pool or spring-break cues; no people; no health or weight-loss claim; no competitor brand; no condensation droplets, ice, splash, fruit, straws or glassware; no watermark; no extra text or logos; clear space of at least one wordmark-height around the wordmark

Image A (call 1) — "previous logo": wrap the can body in the lockup of Image 1: blue field, the five white wind lines running horizontally around the can, the yellow ring with the white leaf, the wordmark, the line. Reproduce Image 1's proportions and element order faithfully; do not add or remove elements. Save as tools/walkthrough/kv_can_A_previous_logo.png.
Image B (call 2) — "bottle label": wrap the can body in the label design of Image 2: blue field, the yellow ring with the white leaf, the wordmark, the line, NO wind lines. Reproduce Image 2's label proportions faithfully. Save as tools/walkthrough/kv_can_B_bottle_label.png.

Workflow: generate A; look at it with view_image; check the verbatim text, the element order, that the can is a standard 330 ml format and nothing reads as alcohol, beach or party. If anything is wrong, regenerate with ONE targeted change, at most two attempts per image. Then the same for B. Copy the chosen results into the workspace under the two names above (do not leave them only under ~/.codex/generated_images). Do not edit WALKTHROUGH.html or any other file. Do not run git commands that change state. Finish with a short report: for each image the final prompt, which attempt was chosen and why, what is still imperfect, and the saved path.
