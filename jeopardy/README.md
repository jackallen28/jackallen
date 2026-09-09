# Mind Jeopardy

A Jeopardy-style buzzer game for the Year 9/10 Humanities unit
**"Where is My Mind? Perception, Consciousness and Artificial Intelligence."**

Six categories, thirty clues, Final Jeopardy. Any number of teams from 2 to 8.
The teacher runs it from two windows — a control screen on their laptop and a
board on the projector — and each team joins from their own computer.

**→ [TEACHER-GUIDE.md](TEACHER-GUIDE.md) is the run sheet.** Read that to run
the lesson. This file covers how it works and how to change it.

This is a standalone project. It shares no code with Mind Feud in the parent
directory and deploys as its own Render service.

---

## Quick start

```bash
npm install
npm start
```

Then, on the teacher's laptop:

1. Open <http://localhost:3000/> — this is your **control screen**.
2. Click **⬈ Open projector window** and drag that window to the projector.
3. Add your teams, then start.

Team computers open the `http://<your-ip>:3000/play` link the terminal prints,
which is also displayed on the projector during setup.

An `ANTHROPIC_API_KEY` is **optional** — see *Answer judging* below.

---

## The two-window setup

This is the part that makes it runnable live, and it is why the game has three
front ends rather than two.

| Window | Who sees it | What it shows |
|---|---|---|
| `/` | the teacher, on their laptop | The step-by-step panel, the clue **and its answer**, a teaching note to read out, the full grid with every answer written in, scores, and a live feed of what teams typed |
| `/board` | the class, on the projector | The grid, the clue, who buzzed, the clock, the scores. **Never an unrevealed answer, and never a teaching note** |
| `/play` | one per team | A buzzer, an answer box, and a wager box in Final Jeopardy |

The separation is enforced on the server, not in the browser: `snapshot(audience)`
builds a different object per audience, so an answer that has not been revealed
is never sent to the projector or to a team at all. There is nothing to find in
the page source.

### The step-by-step panel

The control screen is organised around one question: *what should I do right
now?* The panel at the top answers it in a sentence and renders only the
buttons that are valid at this moment — so there is nothing to get wrong live.

```
CLUE IS UP
Read it out loud
The class can see it on the projector. When you have
finished reading, open the buzzers.
                                    [ 🔔 Open the buzzers ]
```

**The space bar always presses the primary button**, so the whole game can be
driven without looking for anything. During an answer, `Y` and `N` overrule the
automatic ruling.

---

## How the game was adapted

Kept from the real format, because they are what makes Jeopardy work:

- **The picking team is whoever answered last.** A team on a run controls the
  board, which is the show's core rhythm.
- **A wrong answer reopens the clue to everyone else.** Buzzing is per clue, not
  per turn, so nobody switches off.
- **Final Jeopardy wagering**, revealed poorest-first.

Deliberately left out, to keep it simple and to fit a 30-minute lesson:

| Left out | Why |
|---|---|
| **Daily Doubles** | More rules to explain than drama they add at this length. |
| **"In the form of a question"** | Iconic, but with 30 clues in 30 minutes it generates rulings and groans rather than learning. Answers are accepted with or without it. |
| **Negative scores** | A wrong answer costs you the clue, not points. No team can be mathematically out of it before Final Jeopardy, and nobody sits on −400 for twenty minutes. |
| **Double Jeopardy** | One board plus Final is the 30-minute shape. |

Because a Final Jeopardy wager can never exceed a team's score, **no score can
go below zero anywhere in the game.**

---

## Answer judging

Two layers, in this order:

**1. Local matcher (always, instant, no network).** Normalises the typed answer
— lowercase, strips accents and punctuation, drops filler words, stems plurals
— then matches against the alias list each clue carries, tolerating typos via
edit distance scaled to word length. `"occums razor"`, `"chinees room"`,
`"mcgerk"` and `"what is materialism"` all land correctly with no API call.
Jeopardy phrasing is treated as filler, so it is accepted but never required.

**2. Claude (only when layer 1 says no).** For phrasings nobody wrote an alias
for: *"the lady who asked how the mind pushes the body"*. Claude sees the clue
and the official answer and rules on it — generous on spelling and phrasing,
strict on substance, so materialism is never accepted for dualism.

Uses `claude-opus-5` at low effort with a JSON schema, plus server-side refusal
fallbacks. Override with `ANTHROPIC_MODEL`.

**Without an API key the game runs on layer 1 alone**, which is entirely
playable, and every ruling has a one-click override on the control screen.
The game never blocks on the network: if the API is slow or down, the local
verdict stands.

---

## Editing the clues

Everything is in [`src/questions.js`](src/questions.js). Each clue needs:

```js
{
  value: 300,
  text: 'Closure, proximity and similarity are grouping principles from this school…',
  answer: 'Gestalt psychology',
  accept: ['gestalt', 'gestalt psychology', 'gestalt principles'],
  note: 'All unified by the Law of Prägnanz — the brain always reaches for…',
}
```

`note` is printed on the control screen **after** the answer is revealed, for
the teacher to say out loud. It never reaches any other screen.

An alias matches when **every significant word of it** appears in the guess, so
keep aliases specific. Run `node test/matcher.test.js` after editing — it
checks structure, that every clue is reachable by its own answer and by each of
its own aliases, and, most usefully, that **no clue's answer is accepted by a
different clue.** That last check is what caught `"gage"` matching `"game"` and
`"pineal"` matching `"phineas"` during development.

---

## Tests

```bash
npm test    # all three, or run them individually:

node test/matcher.test.js      # 1146 checks, offline, no API key needed
node test/playthrough.test.js  # boots the server, plays clues and the whole final
node test/deploy.test.js       # boots it as Render would, and tries to break in
```

The playthrough test connects a host, a projector and three teams to a real
server and covers what actually breaks live: the three-way buzzer race, lockout
after a wrong answer, the answer clock expiring, whether the projector or a team
can see an unrevealed answer or a teaching note (they cannot), the wager cap,
and the Final Jeopardy arithmetic in both directions.

The deploy test boots the server as Render does and attacks it: a host or
projector with no key or a wrong key, a player with no code or a wrong code. It
checks each is refused, that a refused socket receives no state at all and
cannot buzz, answer or reset the game, and that neither code leaks through the
public config endpoint.

---

## Hosting it on Render

Push the repo and choose **New → Blueprint**. [`render.yaml`](render.yaml)
configures the service, including `rootDir: jeopardy` so it builds from this
directory only.

Then, under **Environment**:

| Variable | What to do |
|---|---|
| `HOST_TOKEN` | Generated. Your control screen is `https://your-app.onrender.com/?token=<HOST_TOKEN>`. **Bookmark it.** |
| `JOIN_CODE` | Generated. Change it to something memorable — the class types it. |
| `ANTHROPIC_API_KEY` | Optional. |

The server turns both gates on automatically when it detects a public host. The
**host key guards the control screen and the projector window**, since both show
more than a student should see; the projector window is opened from the control
screen so it carries the key automatically. The **game code guards `/play`**.

Two Render notes: the free plan sleeps after 15 minutes idle and takes ~50s to
wake, so open the board a couple of minutes before class; and one instance is
one game, so `numInstances` is pinned to 1.

### Splitting this into its own repository

The project is self-contained, so lifting it out is one command:

```bash
git subtree split --prefix=jeopardy -b mind-jeopardy
# then push that branch to a new empty repo as its main branch
```

Delete the `rootDir: jeopardy` line from `render.yaml` afterwards.

---

## Layout

```
server.js              HTTP + websockets; three audiences, two access gates
src/game.js            the state machine — phases, buzzing, Final Jeopardy
src/judge.js           local matcher, then Claude
src/questions.js       the clue bank — this is the file you will edit
public/host.*          the teacher's control screen
public/board.*         the projector window
public/play.*          a team console
public/sfx.js          all sounds, synthesised in-browser (no audio files)
test/                  clue bank checks, a full playthrough, deployment gates
render.yaml            Render blueprint
```

State lives on the server, so a team refreshing mid-clue loses nothing and the
projector window can be closed and reopened at will.
