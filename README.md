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

Open `http://localhost:3000/teacher` for yourself and point students at
`http://localhost:3000/`.

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
3. **Set the round** — pick a length (2 minutes is the default) and what share of
   the class gets an AI partner (50% by default).
4. **Press Start** — everyone is paired at that moment and the countdown begins on
   every screen at once.
5. **While it runs** — your table shows who's paired with whom. It's blurred by
   default so the screen is safe to project; click *Reveal pairings* when you want
   to see it.
6. **Time's up** — students get the vote screen automatically. Each one sees their
   own answer as soon as they've locked it in.
7. **Debrief** — press *Show results*, then *Load transcripts*. The per-partner
   accuracy split ("correct when talking to a peer" vs "correct when talking to
   AI") is usually the most interesting number in the room, and the transcripts
   show exactly what gave the bot away.
8. **Go again** — *New round* re-pairs everyone. You'll be asked whether to keep
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

Tunable in `.env`:

- `BOT_MODEL` — defaults to `claude-opus-5`. `claude-haiku-4-5` is the cheapest
  and fastest option and `claude-sonnet-5` sits in between. The optional request
  parameters are gated on the model: `effort` and the server-side refusal
  fallback are only sent to models that accept them, because a model that
  rejects them would fail *every* turn and quietly drop the class onto the
  scripted fallback. If you set a model outside the families listed in
  `server/bot.js`, check the Terminal for `[bot]` errors before running a lesson.
- `BOT_PERSONA` — replaces the persona instructions entirely, if you want to run
  the activity with a different character or in another language

The configured model is printed at startup, so you can confirm a change took.

## Tests

```bash
npm test
```

Two suites. `test/e2e.mjs` boots the server and drives a five-student round over
real websockets: joining, pairing, chatting, the rate limiter, reconnecting
mid-round, the countdown expiring on its own, voting, scoring, transcripts, reset,
and that students can't invoke teacher commands. `test/bot-mock.mjs` points the
Anthropic SDK at a local stand-in and asserts the exact request shape, the
markdown stripping, the refusal path, and the offline fallback.

## Deploying

It's a single Node process holding state in memory, so any host that runs a
long-lived container works (Render, Railway, Fly.io, a VM). Two requirements:
the host must support websockets, and you must run **one** instance — a second
replica would have its own separate lobby. Set `ANTHROPIC_API_KEY`,
`TEACHER_PASSCODE`, and `PORT` in the host's environment.

State is deliberately not persisted. Restarting the server clears the room, and
nothing about a student is stored beyond the number they typed in.

## Layout

```
server/
  index.js    HTTP + websocket wiring, teacher auth, broadcasting
  state.js    the round state machine: roster, pairing, chat routing, scoring
  bot.js      the Anthropic call, persona, typing delays, offline fallback
  pairing.js  shuffling and the human/AI split
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
