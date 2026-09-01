# Human or Not? — classroom edition

A short classroom activity, in the spirit of [humanornot.so](https://humanornot.so/).
Students join with a 6-digit number, wait in a lobby, and when you press **Start**
they get two minutes of chat with an anonymous partner. Some are paired with a
classmate; the rest are paired with an AI running on the Anthropic API. When the
clock runs out, each student votes **classmate** or **AI bot**, and your console
shows who was talking to what, who guessed right, and the full transcripts.

There are two pages, both served by the same app:

| Page | URL | Who it's for |
|---|---|---|
| Student | `/` | Sign in, wait, chat, vote, see their result |
| Teacher | `/teacher` | Watch students arrive, start and time the round, see results |

## Quick start

```bash
npm install
cp .env.example .env      # then edit .env
npm start
```

Open `http://localhost:3000/teacher` for yourself. The Terminal prints the
address students should use — see *Getting students connected* below.

On **Windows**, the app is identical; only the setup commands differ. Use
PowerShell, and swap the copy step:

```powershell
git clone -b claude/human-or-not-classroom-c5gvde https://github.com/jackallen28/jackallen.git humanornot
cd humanornot
npm install
copy .env.example .env
notepad .env
npm start
```

## Getting students connected

`localhost` works only on the machine running the server. On startup the app
prints every address it can be reached on from the local network, and the same
address appears in the teacher console header — that is what students type.

Students must be on the same Wi-Fi, and the address is `http://`, not `https`.
Allow the firewall prompt the first time you start it (macOS asks about
"node"; Windows asks to allow Node.js on **private** networks).

If your own machine loads the page but another device on the same Wi-Fi cannot,
the network is probably using client isolation, which stops devices reaching
each other. No application setting can work around that — use a different SSID,
a phone/laptop hotspot for a small group, or deploy it (see *Deploying*).

The two settings that matter in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...   # the AI partner
TEACHER_PASSCODE=something     # keeps students out of your console
```

Without an API key the app still runs, but AI partners fall back to short canned
replies that students will spot immediately. The teacher console shows a warning
banner when that's the case, so you'll know before the lesson starts rather than
during it.

## Running the activity

1. **Before class** — start the server, open `/teacher`, enter your passcode.
2. **Students join** — they enter any 6-digit number (student ID, or numbers you
   hand out). Their number appears in your waiting room as they arrive. A green
   dot means connected; a faded chip means they've dropped off.
3. **Set the round** — pick a length (2 minutes is the default), what share of the
   class gets an AI partner (50% by default), and which models those partners
   use. Tick as many models as you like and drag their sliders to set the split;
   the percentages next to each one are what the class will actually get.
4. **Press Start** — everyone is paired at that moment and the countdown begins on
   every screen at once.
5. **While it runs** — your table shows who's paired with whom. It's blurred by
   default so the screen is safe to project; click *Reveal pairings* when you want
   to see it.
6. **Time's up** — students get the vote screen automatically. Each one sees their
   own answer as soon as they've locked it in.
7. **Debrief** — press *Show results*, then *Load transcripts*. The **By model**
   table is the interesting one when you've run several models at once: its
   *fooled rate* is the share of students facing that model who believed they
   were talking to a classmate, so a higher number means a more convincing bot.
   The per-partner accuracy split ("correct when talking to a peer" vs "correct
   when talking to AI") and the transcripts fill in the rest.
8. **Download the report** — *Download report* gives you a single HTML file with
   the metrics, the per-model breakdown, every student's result and every
   transcript. It has no external assets, so it opens anywhere and prints to PDF.
   *CSV* gives one row per student, transcript included, for a spreadsheet.
9. **Go again** — *New round* re-pairs everyone. You'll be asked whether to keep
   the current students signed in or clear the roster entirely.

You can also press *End early* if the conversation dies, and double-click any
number in the waiting room to remove it.

## How pairing works

Students are shuffled, then a slice of them is assigned AI partners and the rest
are paired off with each other. Because human pairs need two students, the AI
count is nudged by one where the numbers don't divide evenly — so an odd class
always works out, and a lone student gets a bot rather than an empty room.

Anyone who joins after you press Start sits the round out and is told so; they're
picked up automatically by the next round.

## The AI partner

`server/bot.js` calls the Messages API once per bot turn, with a persona that
tells the model to write like a bored 15-year-old: a few words, lowercase, patchy
punctuation, no lists, and a flat refusal to be impressive. The classic probes
("what's 17 times 43", "spell this backwards") get a teenager's answer, not an
assistant's. Replies are stripped of any markdown and delayed in proportion to
their length, with a typing indicator, so they don't arrive suspiciously fast.

Bots open with a "hey" if the student hasn't said anything after a few seconds,
so nobody stares at an empty window. If the API call fails — no key, rate limit,
outage — the bot drops to scripted replies rather than going silent, which keeps
a live classroom moving.

### Choosing models

Pick the models in the teacher console — no restart, no editing files. The
catalog lives in `server/models.js` (Opus 5, Sonnet 5, Haiku 4.5 by default) and
each entry carries its price per million tokens, which is what the report uses to
estimate what a round cost.

**You can run several models in the same round.** Tick two or three, set their
weights, and the AI-paired students are split between them using largest-
remainder rounding, so the split matches the weights as closely as whole students
allow. That turns the activity into a comparison: same class, same two minutes,
and you can see which model held the persona best.

The catalog is server-owned on purpose. The console sends model *ids* and
anything not in the catalog is rejected, so a tampered-with browser can't choose
the model or run up the bill.

Two request parameters are gated per model: `effort` and the server-side refusal
fallback are only sent to models that accept them. Haiku 4.5 rejects `effort`, and
sending it anyway would fail *every* turn and quietly drop that student onto the
scripted fallback. Add a model outside the families listed in `server/models.js`
and you should check the Terminal for `[bot]` errors before running a lesson.

Also tunable in `.env`:

- `BOT_MODEL` — the model used when a round doesn't specify one
- `BOT_PERSONA` — replaces the persona instructions entirely, if you want to run
  the activity with a different character or in another language

## Tests

```bash
npm test
```

Two suites. `test/e2e.mjs` boots the server and drives a five-student round over
real websockets: joining, pairing, chatting, the rate limiter, reconnecting
mid-round, the countdown expiring on its own, voting, scoring, transcripts, reset,
and that students can't invoke teacher commands, plus a multi-model round, the
rejection of unknown model ids, and both report formats. `test/bot-mock.mjs`
points the Anthropic SDK at a local stand-in and asserts the exact request shape
per model, token accounting, the markdown stripping, the refusal path, and the
offline fallback.

## Deploying

Hosting it removes every local-network problem at once: no Node install on the
teaching machine, no firewall rules, no client isolation. Students open a link.

`render.yaml` in this repo is a ready-made blueprint for [Render](https://render.com).
Point Render at the repo, it reads that file, and prompts for the two secrets
(`ANTHROPIC_API_KEY` and `TEACHER_PASSCODE`) so they never enter git.

Three constraints apply to any host:

- **Websockets must be supported.** Serverless platforms (Vercel, Netlify,
  Cloudflare Workers) will not work — the app needs one long-lived process.
- **Run exactly one instance.** The classroom lives in memory, so a second
  replica would have its own separate lobby and half the class would vanish.
- **Set `PUBLIC_URL`** to the deployed address, so the console and the startup
  banner advertise a URL students can actually reach rather than the container's
  private address. Render sets `RENDER_EXTERNAL_URL` itself and the app picks
  that up automatically.

On a free tier the service usually sleeps after a period of inactivity and cold
starts take up to a minute. Open the teacher console a few minutes before the
lesson to wake it. A restart also clears the room, so avoid restarting mid-class.

**Once it is on the public internet, anyone with the link can join as a student**
— the 6-digit number is an identifier, not a password. Use a strong
`TEACHER_PASSCODE`, since that is the only thing protecting the console.

State is deliberately not persisted. Restarting the server clears the room, and
nothing about a student is stored beyond the number they typed in.

## Layout

```
server/
  index.js    HTTP + websocket wiring, teacher auth, broadcasting
  state.js    the round state machine: roster, pairing, chat routing, scoring
  bot.js      the Anthropic call, persona, typing delays, offline fallback
  models.js   the model catalog, per-model capability gating, cost estimates
  pairing.js  shuffling, the human/AI split, and the model allocation
  report.js   the downloadable HTML and CSV reports
public/
  index.html  student app        js/student.js
  teacher.html teacher console   js/teacher.js
  css/app.css shared styles
test/
  run.mjs     boots a server, then runs e2e.mjs
  e2e.mjs     full round over websockets
  bot-mock.mjs the Anthropic request path, against a local mock
```

## A note on the deception

The activity only works because students don't know which partner they have, and
that's fine — it's a game with a reveal built into it, the same shape as the site
it's modelled on. It's worth telling the class up front that some of them will be
talking to an AI, so the surprise is *which one they got*, not that an AI was in
the room at all. The transcripts make a much better debrief than the scores do.
