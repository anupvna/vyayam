# Asset and data licenses

Every third-party asset in Vyayam is listed here with its license and how it is used.
Anything not listed was created for this project.

## Exercise data

| What | Source | License | How it's used |
|---|---|---|---|
| Exercise facts: names, primary/secondary muscles, equipment, level | [free-exercise-db](https://github.com/yuhonas/free-exercise-db) by yuhonas, based on [exercises.json](https://github.com/wrkout/exercises.json) by Ollie Jennings | [The Unlicense](https://unlicense.org) (public domain dedication) | Used as a cross-check when curating `backend/app/data/exercises.json`. Each exercise records the dataset id it was checked against in its `source` field. |
| Form cues, common mistakes, breathing and safety notes | Written for Vyayam | Project's own | Original text. |
| Movement patterns, joint-load (`loads`) tags, main/accessory classification | Curated for Vyayam | Project's own | Drives the alternatives ranking and injury exclusions. |

### Not used, and why

- **free-exercise-db photos.** The repository is public domain, but the origin of its
  exercise photos is not documented, and the maintainer has not confirmed their
  license (see the project's issue tracker). With the rule "only verified, openly
  licensed assets", they are excluded.
- **ExerciseDB and similar GIF datasets.** Their animations are copyrighted
  ("© Gym visual") or sold under commercial licenses.

## Images and illustrations

| What | Source | License |
|---|---|---|
| Equipment illustrations (`EquipmentArt.tsx`) | Drawn for Vyayam as SVG | Project's own |
| Muscle map (`MuscleMap.tsx`) | Drawn for Vyayam as SVG | Project's own |
| App icon | Drawn for Vyayam | Project's own |

## Fonts

| Font | Source | License |
|---|---|---|
| Marcellus | [Fontsource](https://fontsource.org/fonts/marcellus) (Google Fonts) | SIL Open Font License 1.1 |
| Instrument Sans | [Fontsource](https://fontsource.org/fonts/instrument-sans) (Google Fonts) | SIL Open Font License 1.1 |

Both fonts are bundled with the app rather than loaded from a CDN, so they work
offline.

## Code dependencies

Backend and frontend dependencies are standard open-source packages (MIT, BSD,
Apache-2.0 and similar), listed in `backend/pyproject.toml` and
`frontend/package.json`.
