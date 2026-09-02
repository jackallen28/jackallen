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

## Student logins

A login is **four letters then four numbers** (`WXYZ1234`), handed out on cards
before the lesson. Before opening the room, upload a CSV pairing each login with
a student number:

```
login,student
WXYZ1234,Student 01
ABCD5678,Student 02
```

A header row is optional and the columns can be either way round — the parser
takes whichever cell looks like a login. Rows that contain no valid login are
reported back rather than silently dropped, so a typo does not quietly leave a
student unable to log in. Logins are case-insensitive.

With a list uploaded, only those logins are accepted. Without one, any correctly
formatted login works, so a forgotten upload does not stop the lesson.

The student number is what appears on the teacher's screens and in the report;
no student ever types a name into the activity. The sign-in screen carries the
conduct rules: you may be talking to a person or an AI, be respectful, share no
personal information, and everything is recorded.

## Running the activity

The teacher console is a sequence of screens. Each one has a single button that
moves to the next.

1. **Set up** — upload the login CSV, then choose round length, the share paired
   with AI, which models, and which personas. Students cannot log in yet.
2. **Open the room** — students log in and their **student numbers appear on
   screen** as each one succeeds, counted against the roster.
3. **Begin the round** — a large countdown fills the screen for projection.
   Anyone logging in after this sits the round out.
4. **Time's up** — students choose classmate or AI; the screen shows how many
   have answered.
5. **Reveal** — who was talking to whom, and which partners were never human.
6. **Scores** — who worked it out, class accuracy, and the fooled rate per model
   and per persona.
7. **Report** — one button downloads a single `.zip` containing the full HTML
   report, a results spreadsheet, and every transcript.
8. **Start over** — wipes every login, student number, message and result, and
   returns to a blank set-up screen for the next class. Nothing is written to
   disk, so download the report first; the console warns you if you have not.

A **Reset** button sits in the header on every screen, so a lesson can be
restarted at any point — including mid-round. It always asks *Are you sure?*
first, in an in-page dialog that names what will be lost and warns if the report
has not been downloaded. Cancel, the Escape key and clicking the backdrop all
back out; only the confirm button resets. Resetting mid-round ends it
immediately and returns every student to the login screen with an explanation,
rather than leaving them on a frozen chat.

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

### How fast the bots reply

A reply is paced like a person writing one. Every message waits at least **four
seconds** before anything happens — reading and thinking, with no typing
indicator shown, since a real partner is not visibly typing while they think.
Only then does the indicator appear, and it stays for as long as the message
would actually take to type.

Typing runs at **5 to 60 words per minute** (a word being five characters, the
standard measure). Each conversation draws one speed at the start and keeps it,
because a person does not type at a different pace from one message to the next.
The draw is triangular, so the whole range occurs but the middle is common.

Two things follow from the arithmetic and are deliberate. At 20 wpm a person can
only type about forty words in a two-minute round, so replies are capped at 140
characters and the prompt tells the model it has one short sentence per message
— otherwise a single reply would consume the entire round. And a hard 30-second
ceiling per reply stops a slow typist still "typing" after the bell.

Tunable in `.env`: `BOT_WPM_MIN`, `BOT_WPM_MAX`, `BOT_THINK_MS`, `BOT_REPLY_CAP_MS`.

### What the bots talk about

The prompt restricts them to the subject material: the mind, the brain,
consciousness, the self, and the class's own arguments and thought experiments.
They may ask what the other person thinks, why, or what their evidence is.

They may **not** ask about anyone's day or life — no timetables, no what-class-
have-you-got-next, no weekend, no lunch. That kind of small talk gives a student
nothing to reason about and invites them to share personal details. If a student
raises it, the bot gives it one flat word and returns to the topic.

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

### The classroom pack

`classroom/` holds the teacher-authored briefing that the bot actually runs on:

| File | What it does |
|---|---|
| `01-class-context.md` | What the class has been taught, shared reference points, and the vocabulary boundary — terms students have met, and terms that would expose the bot instantly |
| `02-bot-scope.md` | Register rules, the AI tells to avoid, name handling, and the safeguards |
| `03-personas.md` | Four unnamed composite personas |
| `04-writing-samples.md` | Paraphrased corpus of authentic student register |

**One persona is drawn per conversation and held for the whole round**, as the pack
requires. Personas are assigned independently of models, so a class covers
combinations of the two, and the console reports a fooled rate per persona
alongside the one per model.

The pack is split into two prompt blocks: a shared briefing that is identical for
every conversation and is cached, plus a short persona block that varies. All four
personas therefore read from one cache entry.

`CLASS_BLOCKLIST` (comma-separated first names) fills the blocklist placeholder in
`02-bot-scope.md`, so the bot can never generate a name belonging to someone in the
room. With none set, the pack tells it to pick a common name at random.

Two register guards are enforced in code rather than trusted to the prompt: em and
en dashes are stripped from every reply, and markdown is removed. `max_tokens` is
set high enough that the long-winded persona is not clipped mid-sentence, since a
truncated reply is its own tell.

The safeguards in `02-bot-scope.md` are restated at the very end of the prompt,
after the persona, because they override staying in character.

Delete `classroom/` (or set `BOT_PERSONA`) and the app falls back to the generic
teenager persona plus `voice-samples.txt`, described next.

### Teaching it your students' voice

This is the fallback used when no classroom pack is present.

`voice-samples.txt` at the root of the repo is the highest-leverage file here.
Put real messages your students write into it, one per line, and the bot copies
their sentence length, slang, spelling and punctuation habits. Regional phrasing
is exactly what students use to catch a generic bot, so a class's own voice makes
the activity markedly harder — and the debrief better.

Lines starting with `#` are comments, blank lines are ignored, and up to 60
samples are used. Changes take effect on restart (or redeploy, if hosted — you
can edit the file straight from github.com and let it deploy itself).

**Anonymise them.** The samples are sent to the API with every bot turn, so strip
names, nicknames, usernames and anything identifying a particular student, and
paraphrase anything too recognisable. Style is what matters, not content.

Samples are inserted into the prompt fenced as data with an explicit instruction
never to act on them, so a line like "ignore your instructions" in the file reads
as an example of a sentence rather than a command. There is a test for that.

On a host where editing a file is awkward, `STUDENT_VOICE_SAMPLES` takes the
samples inline instead, and `VOICE_SAMPLES_FILE` points at a different path.

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
  voice.js    loads voice-samples.txt into the bot's prompt, fenced as data
  classroom.js  loads classroom/, splits out the four personas, builds the prompt
classroom/    the teacher's briefing: class context, scope, personas, samples
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
