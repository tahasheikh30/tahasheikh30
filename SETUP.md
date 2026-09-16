# Setup checklist

Everything in `scripts/`, `.github/workflows/`, `README.md`, `.gitattributes` and
`preview.html` is already built and tested. What's left is the part nobody else
can do for you: your photo, your links, your GitHub account settings.

## 1. The magic repo (5 min)
- [ ] Go to github.com/new
- [ ] Repository name = **exactly** your GitHub username
- [ ] Public
- [ ] Don't add a README (you already have one, from this folder)

## 2. Fill in your details (15–20 min)
Open `README.md` and do a find-and-replace for each of these:

| Placeholder | Replace with |
|---|---|
| `YOUR_USERNAME` | your GitHub username |
| `YOUR_NAME` | your display name |
| `YOUR_LINKEDIN` | your LinkedIn handle |
| `YOUR_EMAIL` | your email address |
| `YOUR_PORTFOLIO` | your portfolio URL (or delete that badge/line if you don't have one) |
| `PROJECT_ONE` .. `PROJECT_FOUR` | four of your repo names, e.g. `attendance-intelligence`, `gims`, `speak-up`, `reinsurance-automation` |

Also rewrite the `whoami` bullets in `README.md` — those are placeholders, not
your actual bullets. Edit `assets/skills.json` with your own self-rated numbers
(0–100, 5–8 axes).

Edit `assets/projects.json` — it already has four entries pointed at the repos
in your memory (`attendance-intelligence`, `gims`, `speak-up`,
`reinsurance-automation`); adjust names/descriptions if any of those aren't
public repos on your account, or swap in different ones.

## 3. Your photo (5 min)
- [ ] Pick a photo, ideally with the background removed (any background-remover
      site works) and saved as a transparent PNG. This makes `--equalize` measure
      only you, not the backdrop.
- [ ] Drop it in the repo root as `me.png`.
- [ ] Install the one dependency: `pip install pillow`
- [ ] Generate the portrait:
  ```
  python scripts/dotify.py me.png -o assets/portrait --cols 100 --equalize --detail 0.5 --color
  ```
  (This overwrites the demo portrait already in `assets/` — that one was
  generated from a placeholder test image, not a real photo.)

## 4. Look at it before anyone else does (2 min)
- [ ] Open `preview.html` in a browser. Check both the dark and light cards for
      every asset.

## 5. Push it
```
cd github-profile-readme
git init
git add -A
git commit -m "profile readme"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_USERNAME.git
git push -u origin main
```

## 6. Two GitHub settings the workflows need
- [ ] **Repo → Settings → Actions → General → Workflow permissions** →
      "Read and write permissions" → Save.
- [ ] **Personal access token, classic** (not fine-grained):
  - github.com/settings/tokens → Generate new token (classic)
  - scope: `read:user` (add `repo` too if you want private contributions counted)
  - Repo → Settings → Secrets and variables → Actions → New repository secret
  - Name it exactly `METRICS_TOKEN`, paste the token value

## 7. Turn on the robots
- [ ] Go to the Actions tab, click through the "workflows aren't running yet"
      banner if you see one.
- [ ] Run each of the three workflows once by hand ("Run workflow"): `metrics`,
      `snake`, `charts-and-cards`. First runs take a couple of minutes each.
- [ ] Open `.github/workflows/metrics.yml` and double-check `YOUR_USERNAME` got
      replaced in all three `user:` lines (the find-and-replace above should
      have caught it, but this file is worth a manual glance).

## 8. Final checks
- [ ] Profile looks right in dark mode (Settings → Appearance to switch, then
      reload github.com/YOUR_USERNAME)
- [ ] Profile looks right in light mode too
- [ ] Profile looks right on your phone
- [ ] Go set real one-line descriptions on the four repos you featured — it's
      what shows up in search and in your repo list either way

That's it. From here, `metrics` refreshes every 6h, `snake` every 12h, and
`charts-and-cards` once a day — nothing else needed from you until a token
expires.
