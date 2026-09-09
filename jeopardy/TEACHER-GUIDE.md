# Mind Jeopardy — Teacher's Run Sheet

**"Where is My Mind?" · Years 9/10 Humanities · 30 minutes**

---

## The setup: two windows

This is the thing to get right before the bell.

**Window 1 — your laptop screen.** The control screen. It tells you exactly what
to do next and shows you every answer. **Never project this.**

**Window 2 — the projector.** The board the class watches. It never shows an
answer before you have revealed it.

To get there:

1. Open the control screen (`http://localhost:3000/`, or your Render link with
   `?token=...` on the end).
2. Click **⬈ Open projector window** at the top.
3. Drag that new window onto the projector and make it full screen.
4. Back on your laptop, add your teams and press start.

Team computers open the `/play` link, which is displayed on the projector
during setup along with the game code, if there is one.

> **One rule:** if you can see the answers, the class can't. If the class can
> see the board, you're on the wrong window.

---

## The 30-minute plan

| Time | What happens |
|---|---|
| 0:00–0:04 | Teams pick names, you add them, rules explained in 30 seconds |
| 0:04–0:24 | The board — roughly 20 clues at about a minute each |
| 0:24–0:29 | Final Jeopardy: wagers, clue, reveal |
| 0:29–0:30 | The debrief question below |

**You will not clear all 30 clues in 30 minutes, and that is fine.** Around 20
is a good pace. When you are five minutes out, stop mid-board and go to Final
Jeopardy — the control screen has the button whenever you want it.

**To speed up:** drop the answer clock from 15 seconds to 10 in Settings.
**To slow down:** set it to 0 to turn it off and run on your own judgement.

---

## How a clue runs

The control screen walks you through it. Every step, it tells you what to do and
shows only the buttons that make sense. **The space bar always presses the main
button**, so you can run the whole game without hunting.

1. **"The Cartesians choose"** — ask them for a category and value, then click
   that cell on your grid. Your grid has every answer written into it, so you
   always know what is coming.
2. **"Read it out loud"** — the clue is on the projector. Read it with some
   theatre. Press **space** when you have finished.
3. **"Waiting for a buzz"** — buzzers are live. First team in wins.
4. **"Team X has it"** — they say it out loud, then type it. It is judged
   automatically, or press **`Y`** / **`N`** to rule yourself.
   - **Right** → they score, and *they pick next*.
   - **Wrong** → they lose the clue but **not** any points, and the buzzers
     reopen for everyone else.
   - If all teams miss, the answer comes up automatically.
5. **"Answer revealed"** — the control screen now shows a **teaching note**.
   Read it out. This is where the actual learning happens; the clue was just
   the setup.
6. Space again to go back to the board.

### Things that will happen

**"They said it right but typed it wrong."** Press `Y`. Your ruling always wins.

**"They're arguing that their answer counts."** The note on your screen usually
settles it — most disputes in this unit are two concepts being confused, and
the note names the distinction.

**"A team is miles ahead."** They still can't run away with it: Final Jeopardy
lets anyone wager everything.

---

## Final Jeopardy

Press **★ Start Final Jeopardy** whenever you are five minutes out.

1. **Announce the category** — it appears on the projector. Say it out loud and
   let them argue about it. *Do not read the clue yet.*
2. **Open the wagers.** Each team bets anything from 0 up to their own score.
   The projector shows *who* has locked in, never how much. Teams cannot see
   each other's wagers, and nobody can bet more than they have — so no score
   can ever go negative.
3. **Show the clue.** Everyone writes at once, 60 seconds by default.
4. **Stop writing & reveal.** Now go team by team, **poorest first** — the
   control screen puts them in order and gives you one button at a time.
   Read out what they wrote. Pause. Then reveal.

The last reveal decides the game. That is the whole point of the format.

---

## The debrief (one minute, do not skip)

With the final scores up:

> "Look at the SOURCE CODE column. Four of those five clues were PCASTLE
> letters or significance criteria. Which one is the one you're most likely to
> skip in the assessment, and why does skipping it cost you marks?"

(*Evidence* — it is the letter that decides whether a source is worth citing
at all, and it is the one most often left out of a paragraph.)

If there is time, the Final Jeopardy note on your screen is the second question:
three unrelated objections — from metaphysics, physics and logic — all landing
on dualism. That convergence is exactly the move to run in the essay.

---

## Quick reference

| Key | Does |
|---|---|
| `Space` | Presses the main button — reads as "next step" all game |
| `Y` / `N` | Rule the current answer correct or wrong |

**Settings** (right-hand column): answer clock, Final Jeopardy writing time,
sound on/off. The `−` and `+` buttons beside each team adjust scores by 100 if
you ever need to fix something by hand.

**Between classes:** press **Reset** in the top right. Teams, scores and the
whole board clear.

**If a team's computer crashes or the wifi drops:** they just reload `/play` and
pick their team again. Nothing is lost — the game state lives on your machine,
not theirs. If a team has no working computer at all, you can hand them the
clue yourself with the *Give it to…* buttons that appear while the buzzers are
live, and rule with `Y` / `N`.
