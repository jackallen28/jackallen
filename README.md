# Mind Feud

A Family Feud–style buzzer game for the Year 9/10 Humanities unit
**"Where is My Mind? Perception, Consciousness and Artificial Intelligence."**

One teacher device hosts and projects the board. Two team computers join over
the local network and buzz in with the space bar. Answers are typed and judged
automatically, with the teacher able to overrule any call in one click.

**→ [TEACHER-GUIDE.md](TEACHER-GUIDE.md) is the run sheet.** Read that to run
the lesson. This file covers how it works and how to change it.

---

## Quick start

```bash
npm install
npm start
```

- **Host board** (project this): <http://localhost:3000/>
- **Team computers**: the `http://<your-ip>:3000/play` link the terminal prints,
  also shown in huge type on the lobby screen.

An `ANTHROPIC_API_KEY` is **optional** — see *Answer judging* below.

```bash
cp .env.example .env    # then: node --env-file=.env server.js
```

---

## How the game was adapted from the real show

You asked for a faster game. Here is what was changed and why, plus the parts
of the real format that were kept because they are what makes it work.

### Kept — these are load-bearing

| Mechanic | Why it stays |
|---|---|
| **The face-off buzz** | Both teams are locked in on every single question, not just their own turn. Remove it and one team disengages for half the game. |
| **Ranked "survey" values** | Answers are worth 28/22/17/14/11/8, not equal points. This is the whole strategy of the show: obvious answers are safe, deep answers pay. It rewards the students who push past the first thing that comes to mind. |
| **Round multipliers** | Rounds run ×1, ×2, ×2, ×3. Nobody is mathematically out of it, so nobody checks out. Round 4 alone can flip the game. |
| **"Survey says"** | The host screen and the sound design play it completely straight. The point values are pre-set by the question bank, not surveyed, but the game never says so. |

### Changed — your rules

| Change | Effect |
|---|---|
| **6 answers, not 8** | A board clears in roughly two thirds the time. |
| **One wrong ends your turn, not three strikes** | The single biggest speed-up. A strike is now genuinely costly, so teams confer fast rather than guessing at random. |
| **Points go to whoever reveals the answer** | Instead of the show's "controlling team banks the whole pot", each answer pays the team that got it. Streaks pay, and the score moves constantly instead of once per round — much better for a projected scoreboard. |
| **Control alternates on a miss** | Replaces the show's single-guess "steal". Simpler to explain, and it keeps the ball moving. |

### Added — three things the show does not have, for a classroom

**1. Near-miss answers.** Some genuinely correct answers are deliberately *not*
on the board. Say one and the screen calls it out in gold — *"Correct, but NOT
on the board"* — and it still costs you your turn.

This is the best feature in the game. Round 3's PCASTLE board has **six slots
for seven letters**, and *E — Evidence* is the one left off. Students groan,
and then they never forget which letter it was. Every board has near-misses
seeded this way, usually with a concept from an adjacent week, so the "wrong"
answer teaches a distinction (functionalism is Turing's *reply*, not an
objection; the Chinese Room is not the Turing Test).

**2. A round miss limit.** Four total misses ends the round and reveals the
board. Without it, two evenly-matched teams can grind on the last two answers
for five minutes. This is a pacing valve, not a scoring rule.

**3. A spoiler round after the final.** You asked for the final round to belong
to the leading team, which it does. But a trailing team with nothing to do for
the last five minutes is a classroom management problem. So: every question the
leaders **pass** on falls into a pile, and the trailing team gets 45 seconds on
that pile at **15 points each** — higher than the 10 the leaders were playing
for. The leaders' incentive to pass is now real pressure, and the trailing team
has a live comeback path right to the final buzzer.

Turn it off in the panel if you want a clean "leaders seal it" ending.

---

## Answer judging

Two layers, in this order:

**1. Local matcher (always, instant, no network).** Normalises the guess —
lowercase, strips accents and punctuation, drops filler words, stems plurals —
then matches it against the alias list every answer carries in the question
bank, tolerating typos via edit distance scaled to word length. `"ockhams
razer"`, `"chinees room"`, `"proximty"` and `"is it primary or secondary"` all
land correctly with no API call. Most guesses in a real game never leave the
laptop.

**2. Claude (only when layer 1 says no).** For the phrasings nobody wrote an
alias for: *"the thing where the hand isn't yours"*, *"you can't touch
something that isn't physical"*. Claude sees the whole board and returns which
slot the guess belongs in — judging generously on spelling and phrasing, and
strictly on substance, so materialism never gets accepted for dualism.

Uses `claude-opus-5` at low effort with a JSON schema, plus server-side refusal
fallbacks. Override the model with `ANTHROPIC_MODEL`.

**Without an API key the game runs on layer 1 alone**, which is entirely
playable — the question bank has aliases for the expected wordings — and the
teacher can reveal any answer by hand in one click. The game never blocks on
the network: if the API is slow or down, the local verdict stands.

---

## Editing the questions

Everything is in [`src/questions.js`](src/questions.js). Each board question
needs exactly **6 answers whose points total 100**, and each answer needs an
`accept` list of alias phrases:

```js
{ text: 'Closure — the brain fills in the missing gaps', points: 26,
  accept: ['closure', 'filling in gaps', 'completing the shape'] },
```

An alias matches when **every significant word of it** appears in the guess, so
keep aliases specific. A one-word alias like `'brain'` would swallow half a
board; `'brain damage'` will not.

`nearMiss` entries use the same shape and are the correct-but-off-the-board
traps described above.

Run `node test/matcher.test.js` after editing — it checks every question has 6
answers totalling 100 and that **every answer is reachable by its own first
alias**, which catches a typo'd alias before you find it mid-lesson.

---

## Tests

```bash
node test/matcher.test.js      # 130 checks, offline, no API key needed
node test/playthrough.test.js  # boots the server, plays a full game over websockets
```

The playthrough test covers the things that actually break in a live game: the
buzzer race between two teams, whether the team that lost the race is refused,
turn passing on a miss, whether a team screen can see unrevealed answers (it
cannot — the server strips them), the clock running down, and the spoiler pile
being handed to the right team.

---

## Layout

```
server.js              HTTP + websockets; broadcasts state on every change
src/game.js            the state machine — phases, scoring, the final round
src/judge.js           local matcher, then Claude
src/questions.js       the question bank — this is the file you will edit
public/host.html/.js   the projected board and the teacher's control panel
public/play.html/.js   the team console
public/sfx.js          all sounds, synthesised in-browser (no audio files)
test/                  offline matcher checks + a full websocket playthrough
```

State lives on the server, so a team refreshing their tab mid-round loses
nothing, and both consoles reconnect silently if the wifi hiccups.

Set `HOST_TOKEN=something` to require `?token=something` on the host board, if
you are worried about students opening the answer screen.
