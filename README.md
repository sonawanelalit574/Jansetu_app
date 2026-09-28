# JanSetu

Citizen infrastructure requests, read at the scale of a planning desk.

People file in the language they speak — by text, SMS, smartphone voice, a feature-phone missed call, or a messaging thread. JanSetu classifies the need and sets it beside who lives in the district, how thin the infrastructure is, and where this year’s scheme line already sits. A planning desk then sees hotspots, an under-heard shelf, and a cabinet note. The note is a decision aid. It does not sanction money.

This is a digital public good for the “AI for Digital Public Infrastructure & Governance” track: built for India’s languages and missions, with a method that can be inspected.

## Project structure

```
jansetu/                 <- repo root (push THIS folder's contents to GitHub)
├── app.py               <- entry point: exposes `app` (gunicorn app:app)
├── wsgi.py              <- alternate entry (gunicorn wsgi:app)
├── requirements.txt
├── render.yaml          <- Render Blueprint
├── Procfile
├── Dockerfile
├── .python-version
├── jansetu/             <- application package
│   ├── __init__.py      <- create_app() factory
│   ├── routes.py, db.py, nlp.py, scoring.py, seed.py, ...
├── templates/           <- Jinja templates
├── static/              <- css / js
├── data/                <- SQLite file is created here at boot
└── docs/                <- pitch deck + build script (not needed to run)
```

## Run it locally

From the folder that contains `app.py`:

```bash
python -m pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5050](http://127.0.0.1:5050).

## Host on Render

1. Push the **contents of this folder** to a GitHub repo, so `app.py` and `requirements.txt` are at the repo root (not inside another folder).
2. On Render: **New → Blueprint**, pick the repo. `render.yaml` does the rest.

Or create a **Web Service** by hand:

| Setting | Value |
| --- | --- |
| Root directory | empty |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120` |
| Python | 3.12.11 |

There is no external database. The SQLite ledger is created and seeded automatically on first boot. On Render's free plan the disk is ephemeral, so it re-seeds after each redeploy or restart. A free instance sleeps after about 15 minutes idle and wakes on the next visit.

| Path | What it is |
| --- | --- |
| `/` | The public argument |
| `/desk` | File by text, voice, missed call, or messaging |
| `/console` | Planning desk: atlas, notes, ledger |
| `/note/<district>/<sector>` | One cabinet note |
| `/method` | The four weights, in public |
| `/deck` | Slides. Print to PDF from the browser |
| `/api/open-data` | The demonstration ledger, without names or phone numbers |

## Submission blurb

JanSetu is a digital public good that turns citizen infrastructure requests into a planning ledger for India. People can file by text, smartphone voice, a feature-phone missed call, or a messaging thread, in twelve Indian languages. The engine detects the script and the need — water, roads, power, health, schools, sanitation, housing, or connectivity — and scores every district against four public questions: how loud is the demand, how large is the infrastructure gap, who lives there, and where the money already sits. A planning desk sees hotspots, an under-heard shelf for places with weak voice reach, and a cabinet note with an indicative project, a scheme fit, and the evidence. The method is published. The core engine does not send citizen text to an outside model. The ledger in this prototype is a demonstration set shaped from public scheme patterns, so the product can be judged on the decision, not on a locked database.

## How a request moves

1. Script detection chooses the language. A lexicon chooses the sector. A tie is refused, and the desk asks.
2. Severity rises when the text mentions an ambulance, a clinician, a teacher, children, or a run of days.
3. The record joins the district: population, rural share, deprivation, a coverage index, and the scheme allocation.
4. The cell is scored out of 100: demand 34, deficit 30, equity 20, allocation gap 16.
5. Hotspots are cells near the top with enough records to defend in a meeting. The under-heard shelf is separate: high deficit, very low voice reach, almost no records. Those complaints are not inflated.
6. Six cabinet notes form a portfolio — different needs, different states, plus one seat for a quiet district.

Scheme fit is drawn from programmes that already exist: Jal Jeevan Mission, PMGSY, RDSS, PM-ABHIM / NHM, Samagra Shiksha, Swachh Bharat Mission, BharatNet, and PMAY-Gramin. Indicative costs are planning assumptions, not official rates.

## Optional Gemini

Classification never calls out. If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set, a note page can ask Gemini to rewrite the paragraph. That call sends the published numbers only, not the citizen’s words.

```powershell
$env:GEMINI_API_KEY = "your-key"
python app.py
```

## Cloud Run

```bash
gcloud run deploy jansetu --source . --region asia-south1 --allow-unauthenticated
```

The container listens on `$PORT` and loads `app:app`. SQLite is enough for a demonstration; a shared deployment should move the ledger to Cloud SQL. The scoring code does not need to change for that. The desk in production would sit behind government SSO, and the intake behind a telecom and messaging gateway. Both speak the same JSON this prototype already accepts at `POST /api/requests`.

## Demo path

1. Home. The quote and the bars are the live ledger.
2. Citizen desk. File a Tamil or Hindi sample. Keep the reference.
3. Open the receipt, then the cabinet note.
4. Planning desk. Open the Rayagada road note, then the under-heard shelf.
5. Method page. The weights are the product.

Print `/deck` to PDF for the slide upload.

## Honesty

Populations, coverage, deprivation, and rupee lines are demonstration estimates shaped from the pattern of public Indian datasets. They are not Census figures, mission dashboards, or a budget. Do not cite them as official statistics.
