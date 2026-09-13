# Human or Not? — bilingual edition

A copy of the classroom activity, rebuilt for a group working across **English and
中文**. Participants choose a language, chat for two minutes with either a colleague
or an AI, and guess which. The same rationale as the original; the difference is
that the two people talking need not share a language.

This is a **separate application**. It shares no runtime code with the activity in
the repository root, so changing one cannot break the other. Both live in the same
package, so there is only one `npm install`.

```bash
npm run start:bilingual                 # default port 3000
PORT=3100 npm run start:bilingual       # run alongside the original activity
npm run test:bilingual
```

## What is different

**Language first.** Before anything else a participant picks English or 中文. Every
screen after that — sign-in, the conduct rules, the chat, the reveal — is in that
language. The choice is remembered for the browser tab and can be changed from the
sign-in screen.

**Messages are translated.** When two participants pick different languages, each
message is translated for the recipient as it is delivered. The sender always sees
exactly what they typed. Deliveries are chained per conversation, so a slow
translation cannot let a later message overtake an earlier one. If translation fails
— no key, an outage — the original text is delivered untranslated rather than lost.

The AI partner is **not** translated: it is told to write directly in its partner's
language, which reads better than translating into it.

**The report has a language toggle.** `Report EN | 中文` in the console header. It
sets the language of the HTML report and the transcripts file. The CSV keeps English
column names in both, so spreadsheet formulas and scripts keep working whichever
language was picked; it gains a `language` column recording each participant's
choice.

**Participants see a class summary.** After the facilitator reveals, each participant
gets an aggregate-only screen: how many took part, what share identified their
partner correctly, and the split against AI and against people. No individual result
for anyone, including themselves beyond their own reveal.

## How participants identify themselves

The first card on the set-up screen offers two ways in, and the choice is locked
once the room opens.

**Assigned logins** (the default). You hand out cards beforehand and upload the
CSV; only those logins are accepted. Nobody types a name, so no personal
information enters the activity at all.

**Participants type a name.** No cards, no list. Everyone chooses what to be
called when they arrive. The login list card disappears, because it has nothing
to do.

Names are matched case- and space-insensitively, so `Li Wei`, `li  wei` and
`  LI WEI ` are the same person coming back after a refresh, while the display
keeps whatever they actually typed. A name already in use by someone still
connected is refused rather than treated as a reconnect, so two people cannot end
up sharing one conversation. Chinese names work as identities exactly as English
ones do.

**Chat partners never see the name.** It appears on your screens and in the
report, nowhere else — the conversation stays anonymous, which is the point of
the activity. The console says so in an amber note whenever name entry is on,
because switching it on does change what personal information the activity holds.
The participant's own screen asks for "a first name or nickname".

## A caveat worth understanding before you run it

Machine translation flattens voice. A colleague's blunt, typo-ridden message arrives
smoothed out, which makes **a real person read more like a machine**. Translation
therefore pushes errors in one direction: participants in cross-language pairs are
more likely to call a human an AI.

The translator is instructed to preserve register — keep it short, keep it casual,
do not fix the typos — which helps but does not eliminate it. Three ways to handle it:

1. Treat it as part of the discussion. For a group of language teachers this is
   arguably the most interesting thing in the room.
2. Put same-language participants together so translation is rare.
3. Ask for a uniform-translation mode, where the AI's output is machine-translated
   too so that every message has the same texture. Not built — say the word.

## The classroom pack

`classroom/` holds four files that tell the bot who to be. **Three of them are
placeholders** and should be replaced before running this with real participants:

| File | State |
|---|---|
| `01-context.md` | Placeholder. What the group shares, and the vocabulary boundary. |
| `02-bot-scope.md` | Usable as-is. Register rules and the safeguards. |
| `03-personas.md` | Two thin placeholder personas. Replace with real ones. |
| `04-writing-samples.md` | Empty. Real participant register goes here. |

Persona headings must keep the `## Persona X — Name` format; the loader splits the
file on them. Add as many as you like — the console lists whatever it finds.

Until `04-writing-samples.md` has content the bot falls back on generic register and
will be easier to spot than it needs to be.

## Environment

Everything the original supports, plus:

- `TRANSLATE_MODEL` — defaults to `claude-haiku-4-5`, chosen because translation sits
  on the critical path of a live chat and speed matters more than depth
