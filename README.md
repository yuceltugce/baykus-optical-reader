# Baykuş Optik — optical answer sheet reader

Reads the Testofis "OPTİK-129" answer sheet from a phone scan: aligns it with the corner markers, fine-tunes the
alignment with the printed bubble rings, finds the marked option of every question and tells whether the result
can be trusted.

## Folders

| Folder | Contents |
|---|---|
| [`app/`](app/) | **The working application.** Web server the phone sends scans to, reading code, batch processing, tests. Start here: [`app/README.md`](app/README.md) |
| [`mobile/`](mobile/) | Prototype of the in-app scan feature (Expo / React Native, phone's own document scanner). See [`mobile/README.md`](mobile/README.md) |
| [`experiments/edge_alignment_v2/`](experiments/edge_alignment_v2/) | Alignment methods (E0–E3), the alignment code the app uses (`src/`) and the reference template (`reference/template.json`). Reports: [`EXPERIMENTS.md`](experiments/edge_alignment_v2/EXPERIMENTS.md) |
| [`docs/`](docs/) | System design diagram (`sistem_tasarimi.excalidraw`, open at excalidraw.com) |
| `dataset/` | 41 scanned sheets (flat/curved × front/angled), not in git. `flat_front/004.png` is the app's **reference** image. Images are stored at the size the code works with (2000 px high). |

## Quick start

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -B app/server.py                 # scan from the phone: open the https address it prints
.venv/bin/python -B app/batch_process.py <pdf/image folder> <output folder>   # batch reading + rapor.html
.venv/bin/python -B -m unittest discover -s app/tests
```

## Pipeline

### A. Building the template (done once)

1. The reference image is `dataset/flat_front/004.png`. All code works at a height of 2000 pixels. A bubble is about
   22 pixels wide, so the distance limits used below (10 px, 6 px, etc.) are chosen for this scale.
2. For each of the four subject blocks, the positions of four corner bubbles were entered by hand: options A and E of
   the first question, and options A and E of the last question. That gives 16 points in total.
3. The remaining bubbles are placed by linear interpolation between these corners. This gives an approximate position
   for all 830 bubbles, each with its subject, question and option (list A).
4. The hand-entered corners can be a few pixels off and the bubbles are not perfectly evenly spaced, so the positions
   are checked against the image. A threshold of 185 is applied to the grayscale image. Shapes 17–28 px in size, with
   an aspect ratio of 0.75–1.3 and a circularity above 0.65, are accepted as bubbles (list B).
5. For each bubble in list A, the nearest centre in list B is found. If it is closer than 10 pixels, the bubble's
   position is updated to that centre; otherwise the bubble is marked as unverified. 814 of the 830 bubbles were
   verified this way.
6. The 16 unverified bubbles are pencil-filled ones. With a single threshold the pencil mark merges with the pink
   ring into one large blob that exceeds the size limit, so it was rejected. A second method was used for these
   bubbles:
   - Four thresholds are tried: 140, 165, 185, 205. At the lower thresholds only the pencil mark is separated.
   - Only shapes inside the answer area are kept: 10,034 of 35,084.
   - Shapes whose size or aspect ratio does not fit a bubble are removed: 4,956 remain.
   - An ellipse is fitted to each remaining shape by least squares (`cv2.fitEllipse`). Shapes with unsuitable axes
     are dropped (4,945 remain), and so are shapes whose area differs from the ellipse area by more than 20%: 4,676
     remain.
   - Duplicates of the same bubble found at different thresholds are merged: of candidates closer than 6 px to each
     other, the one that fits its ellipse best is kept. This leaves 830 candidates.
   - With this method 15 of the 16 bubbles were corrected.
7. The result is stored in `experiments/edge_alignment_v2/reference/template.json`. The code that produced it is kept
   under the git tag `archive/temizlik-oncesi` (`scripts/edge_baseline.py`, `scripts/edge_refinement.py`).

### B. Server start-up

8. When the server starts, it reads `template.json`, scales the reference image to 2000 px and finds its corner
   markers. It also records which reference bubbles are themselves confirmed by a printed ring. All of this is kept
   in memory (`pipeline.reference()` → `run_experiment.prepare_reference()`).

### C. Aligning an incoming photo

9. If the input is a PDF, its first page is rendered to an image. The image is scaled to a height of 2000 px
   (`pipeline.decode()`, `pipeline.to_working()`).
10. Marker detection (`common.detect_markers()`):
    - The red channel is divided by the local paper brightness (`common.paper_flattened()`), which removes
      differences in exposure and shadow.
    - After a light Gaussian blur, a black-and-white mask is made with a threshold derived from the darkest pixels
      of the page.
11. A 5×5 morphological opening (erosion followed by dilation) is applied to the mask. Lines thinner than 5 px and
    small specks disappear; solid squares survive.
12. The remaining candidates must pass four checks in order: is the size right for a marker, is it close to a square,
    is it filled, does it have few corners. Duplicates of the same marker are removed, and so are shapes that have
    another candidate within 60 px. On the reference image this leaves 11 markers.
13. The markers in the photo are matched to the reference markers (`common.match_markers()`):
    - The two images can differ in width, so coordinates are divided by the image size to bring them into the 0–1
      range.
    - A cost table is built from the distances between every reference marker and every candidate.
    - The Hungarian algorithm finds the one-to-one assignment with the smallest total distance, so two candidates
      cannot be assigned to the same marker.
    - Matches with a distance above 0.06 are discarded.
    - If fewer than 6 matches remain, the photo cannot be aligned and the user is asked to scan the form again.
14. From the matched point pairs, a 3×3 perspective transform (homography, H) is computed that maps any reference
    point to its position in the photo (`homography.fit_checked()`, `cv2.findHomography`).
    - RANSAC builds transforms from random subsets of four markers and keeps the largest set of markers that agree
      within 3 px.
    - If that transform is numerically unstable, the transform built from all markers is used instead.
    - Both candidate transforms are then applied to the 830 bubbles, and the one that places more bubbles within
      10 px of a printed ring is chosen (`homography.fit_verified()`).
15. The chosen H is applied to the 830 template bubbles. This prediction is usually within 1–2 px, but local shifts
    appear when the paper is not flat.
16. The printed rings in the photo are found with the second method from the template step
    (`common.detect_bubble_contours()`), with these differences:
    - It uses the paper-flattened green channel.
    - Five thresholds are tried: 140, 165, 185, 205, 225.
    - The answer area is the reference answer area, padded by 30 px and carried into the photo by H
      (`common.answer_region()`).
17. The 830 predicted bubbles are matched to the detected rings (`common.associate()`). A match is accepted only when:
    - it is closer than 10 px,
    - the ring is that bubble's nearest candidate,
    - the second-nearest candidate is at least 3 px farther away.
18. A local correction is made for each subject (`src/local_contour.py`, `predict()`):
    - **Control points:** every fifth row (1, 6, 11, …) and the last row of each subject.
    - **Outlier removal:** at these points the difference between the observed and predicted position is measured.
      This is the shift the homography could not explain. Points that differ from the subject's median shift by more
      than 10 px are treated as wrong matches and dropped.
    - **TPS:** from the remaining points, a smoothed thin plate spline spreads the shift over the whole subject
      (`src/tps.py`, `residual_tps()`). The TPS is not forced to pass exactly through the points.
    - **Limits:** if fewer than 10 control points remain, the homography prediction is kept and a warning is shown.
      Corrections larger than 12 px are not applied.

### D. Alignment check

19. After alignment, the distance from each bubble to the nearest printed ring is measured. Within 5 px the bubble
    counts as in place; 5–14 px as shifted; farther away as unverified. The check is done per subject in regions of
    10 questions (`pipeline.final_position_check()`):
    - If more than 12% of the bubbles in any region are shifted, the result is not trusted.
    - If more than 50% are unverified, a warning is shown.
    - The 12% threshold lies between the worst region of the good pages (6.7%) and the best region of the bad pages
      (16%) in a test on 149 pages.
20. Questions with a bubble whose centre is closer than 13 px to the image border are marked as "not visible"
    (`pipeline.visible_bubbles()`).

### E. Reading ([`app/reading.py`](app/reading.py))

21. The red channel is used. The pink print of the form is almost white in this channel, while pencil stays dark.
22. The local paper brightness is estimated with a 61×61 morphological closing. Each pixel's darkness relative to the
    paper is computed as (paper − pixel) / paper, so shadows and exposure do not change the ratio.
23. The score of a bubble is the mean darkness of a disc of radius 8 px at its centre.
24. Each option is compared with the other options of the same question: the median of the question's five options
    is subtracted from its score. The five options sit close together, so a shadow or glare affects them all alike
    and cancels out in this difference.
25. The threshold is computed separately for each sheet (`sheet_threshold()`):
    - The differences of each question's darkest option are split into "answered" and "blank" with Otsu's method.
    - The median of the answered questions is taken as this sheet's typical mark.
    - The threshold is 30% of the typical mark.
    - Marks between the threshold and the typical mark are reported as "weak".
26. If one option passes the threshold, that option is read. If two options pass and the second is also dark enough,
    the question counts as multi-marked (`decide()`).
27. Accuracy was measured on 159 photos of the same four sheets, against each sheet's majority answer (checked with
    Gemini and by eye):
    - On the iPhone photos, the error rate was 1.17% with the old single-threshold method and is 0.25% with the
      in-question comparison.
    - On the Redmi photos, wrong answers went from 159 to 6.

### F. Result and service

28. The result is classified (`pipeline.process_image()`):
    - **Scan again (no result shown):** problems a new scan would fix — too few markers, a shifted region, questions
      outside the image, multiple marks that point to a shadow.
    - **Result with a warning:** problems a new scan would not fix — very light pencil, faint print.
    - **Confirmation list:** weak and multi-marked questions are put in a separate list to ask the user.
29. The server (`app/server.py`) has two endpoints:
    - `/api/process` processes the image, saves the input and results, and returns the marked photo and, for each
      question that needs confirmation, its row cropped from the photo.
    - `/api/confirm` saves the user's choices.
30. Clients:
    - the web page (`app/static/index.html`),
    - the mobile app prototype (`mobile/App.tsx`), which scans the form with the phone's own document scanner:
      VisionKit on iOS, ML Kit on Android.
31. Development tools:
    - batch processing and reports (`app/batch_process.py`),
    - comparison with vision models (`app/model_*.py`),
    - comparison of alignment methods (`experiments/edge_alignment_v2/run_experiment.py`).

Field tests, measurements and known limits (in Turkish): [`app/SAHA_DENEMELERI.md`](app/SAHA_DENEMELERI.md).

## Archive

Earlier work removed from the main branch is kept under git tags:

- `archive/temizlik-oncesi` — the full state right before the clean-up: source PDFs (`Flat_front.pdf` etc., the
  original source of the `dataset/` scans), the old notebook (`main.ipynb`), `scripts/`, `src/`, the first alignment
  experiments.
- `archive/faz1-2-kagit-tespiti` — the first approach: paper detection in a raw photo, perspective and
  0/90/180/270° orientation correction (`src/baykus_optik`).
- `archive/old-notebook-experiments` — the first alignment experiments (`experiments/edge_alignment/`).

To look at one: `git checkout <tag>` (go back with `git checkout main`).
