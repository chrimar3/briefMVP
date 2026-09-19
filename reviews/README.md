# reviews/ — the shareable shelf

Every **completed** pipeline run automatically drops its two self-contained pages here,
named so a non-technical reader can recognise them at a glance:

```
meltemi-beverages-northlight-01-2026-07-24-<revision>-brief.html   ← the brief review page (account-lead surface)
meltemi-beverages-northlight-01-2026-07-24-<revision>-run.html     ← the pipeline walkthrough (how it was built)
meltemi-beverages-northlight-01-2026-07-24-<revision>-el.html      ← the Greek brief document, typeset for reading
meltemi-beverages-northlight-01-2026-07-24-<revision>-en.html      ← the English brief document, typeset for reading
meltemi-beverages-northlight-01-2026-07-24-<revision>-el.md        ← the same Greek document as raw markdown
meltemi-beverages-northlight-01-2026-07-24-<revision>-en.md        ← the same English document as raw markdown
```

The walkthrough's bottom buttons are rewritten on copy so they link the shelf names —
everything cross-links correctly inside this folder.

## How account leads get them (pilot distribution — no server, by design)

1. **Email / Slack the file.** Each page is one file with zero dependencies — attach it,
   the lead double-clicks, it opens in any browser, offline, phone included. Print → PDF
   works from the page itself.
2. **Share this folder.** Point Dropbox / OneDrive / Drive desktop sync at `reviews/` and
   every lead sees new briefs the moment a run finishes.
   ⚠ Google Drive's *web preview* does not run the page's toggle/copy scripts — leads
   should open the synced local file, not the browser preview (Dropbox/OneDrive desktop
   sync have no such issue).

## Rules

- Only completed runs publish. Refusals and partial runs stay in `runs/` for the operator.
- Filenames include client, project, date and a content revision. Different campaigns
  and revisions keep distinct paths; republishing identical content is idempotent.
  Existing links remain on their original version. Share the new paths printed by the publisher.
- Agency-managed signed pages require current approval and match the canonical brief/renders.
- The pages are deterministic views of the run's artifacts and carry **no cost or model
  information** (mission decision §6.1).
- **Internal only** (mission decision §6.2): briefs contain client-sensitive material —
  share within the account team, never publicly.

Manual publish of any run: `python3 pipeline/publish.py runs/<id>`
