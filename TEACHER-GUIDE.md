# Mind Feud — Teacher's Run Sheet

**"Where is My Mind?" · Years 9/10 Humanities · 30 minutes**

---

## Before the lesson

There are two ways to run this. **Pick one.**

### Option A — hosted on Render (nothing to install)

If the game is deployed (see the README), you have two links:

- **Host board** — `https://your-app.onrender.com/?token=...` → bookmark this,
  open it, project it. It is the only link with the answers on it.
- **Team computers** — `https://your-app.onrender.com/play` → the students type
  the **game code** shown in huge type on your lobby screen.

**Open the board two minutes before class, not as the bell goes.** Render's
free plan puts the app to sleep after 15 minutes of quiet, and waking it takes
about 50 seconds. Once a game is running it stays awake.

**Between classes**, hit `Reset everything` in the panel. One deployment runs
one game at a time — two classes at once need two deployments.

Then skip to *The 30-minute plan* below.

### Option B — from your own laptop (5 minutes, the day before)

1. On your laptop, in this folder:
   ```bash
   npm install
   npm start
   ```
2. The terminal prints two things. Keep it open.
   - **Host board** — `http://localhost:3000/` → open it and project it.
   - **Team link** — e.g. `http://192.168.1.42:3000/play` → this is what the
     team computers type in. It is also displayed in huge type on the lobby
     screen, so you can just point at the projector.
3. Walk to each team computer, open the link, pick Team A / Team B, hit join.
   Leave the tabs open.
4. Press a key on the host screen once so the browser allows sound.

There is no password on this option — anyone who can reach your laptop is
already in the room.

**If the school network blocks the team computers from reaching your laptop**,
don't panic — see *No-network mode* at the bottom. The game still runs. (This
is also the usual reason to prefer Option A: a hosted game reaches the team
computers through the normal internet, not the school LAN.)

---

## The 30-minute plan

| Time | What happens | Your move |
|---|---|---|
| 0:00–0:03 | Teams pick names, rules explained | Lobby screen is up; read out the game code; type team names into the panel |
| 0:03–0:08 | **Round 1** — Sensation, Perception & Illusion (×1) | `Start / Next Round`, then `Put Question Up` |
| 0:08–0:13 | **Round 2** — Souls, Selves & Substances (×2) | `Start / Next Round`, then `Put Question Up` |
| 0:13–0:19 | **Round 3** — Source Analysis & Significance (×2) | The PCASTLE board — the best round for the assessment |
| 0:19–0:24 | **Round 4** — Brains, Machines & Minds (×3) | Triple points. Nobody is out of it |
| 0:24–0:29 | **Final** — Rapid Fire + Spoiler Round | `Call Up Leaders` → `Start Clock` |
| 0:29–0:30 | Winner, and the one-minute debrief below | |

**Running late?** Skip a board round — the multipliers mean Round 4 alone can
swing the game, so cut Round 1 or 2, never Round 4. Each round has three
questions in the bank; you only need one.

**Running early?** Put a second question up in the same round.

---

## How a round runs

1. **Read the question aloud** with some theatre. It is on the screen too.
2. **Buzzers are live.** Both teams hammer the space bar. First one in wins —
   their score panel lights up gold.
3. **They shout their answer out loud**, then **type it**. The shout is what
   keeps the class alive; the typing is what the game scores.
4. **DING** → it goes up on the board with its points, and *they keep going*.
5. **✗** → one wrong answer and the board passes to the other team. No three
   strikes. This is the change that makes it fast.
6. The round ends when the board is cleared, or after **4 total misses**.

### The three things that will happen, and what to do

**"They said it right but typed it wrong."**
Use `Reveal by hand` in the panel. Click `A` or `B` next to the answer to
credit that team, or the wide button to reveal it uncredited. On the keyboard:
press `1`–`6` to reveal that slot for whoever currently has control.

**"The computer said no and it should have said yes."**
Same fix — reveal it by hand. Your call always wins. The feed at the bottom of
the panel shows exactly what they typed and why it was judged that way.

**"They said something correct that isn't on the board."**
The screen calls it out in gold — *"Correct — but NOT on the board"* — and it
still costs them their turn. **Stop for ten seconds here.** This is the single
best teaching moment in the game, and it is deliberate. The PCASTLE round is
built around it: seven letters, six slots, and *E — Evidence* is not up there.

---

## The final round

`Call Up Leaders` puts the **higher-scoring team** on the clock. (If it's a tie,
use `Force A` / `Force B`.)

- **90 seconds**, one short question at a time, on their screen and yours.
- Each correct answer is **10 points**. Hitting **70** earns a **+200 bonus**.
- **SPACE passes** — and here is the hook: every question they pass on falls
  into the **spoiler pile**.

Then the trailing team gets **45 seconds** on that pile, at **15 points each**.
A big enough pile is a genuine comeback. This is why the losing team stays
awake for the last five minutes instead of watching.

---

## The one-minute debrief (do not skip this)

While the winner's screen is up, ask:

> "Round 3 — which PCASTLE letter did we leave off the board on purpose, and
> why does it matter most for your assessment?"

(*Evidence.* It is the one that decides whether a source is any good, and it is
the one students most often skip.)

And:

> "In Round 4, both the materialist evidence and the dualist rebuttals were on
> the same board. Which side got the higher-scoring answers, and does that
> actually tell us who's right?"

(No — survey popularity is not truth. That's a free lesson in *Importance* vs
*Depth* from the significance criteria.)

---

## Panel cheat sheet

| Key | Does |
|---|---|
| `N` | Put the next question up |
| `B` | Re-open the buzzers |
| `1`–`6` | Reveal that answer for whoever has control |
| `E` | End the round and reveal the whole board |
| `A` / `L` | Buzz for Team A / Team B (no-network mode) |
| `H` | Hide the control panel — a clean screen for photos |

---

## No-network mode

If the team computers cannot reach your laptop, run the entire game from the
host screen and never touch the team consoles:

- A team shouts → you press **`A`** or **`L`** to give them control.
- They answer → you press **`1`**–**`6`** to reveal it, or **`✗`** never needs
  pressing (use `Give A control` / `Give B control` to pass).

It plays almost identically. Students buzz by *shouting*, which some classes
prefer anyway. Nothing about the question bank, scoring, multipliers or the
final round changes.

---

## Settings worth knowing

In the panel, under **Settings**:

- **Miss limit** (default 4) — lower it to 2 or 3 if you are short on time.
- **Re-buzz for control after every miss** — off by default. Turn it on for a
  more chaotic, more buzzer-heavy game where a team can win the board straight
  back. Good for a livelier class; it does make rounds longer.
- **Spoiler round** — on by default. Turn it off if you want a clean
  "the leaders seal it" ending.
