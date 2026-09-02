# Turing Test Simulator — Where Is My Mind?

Context files for a classroom Turing Test activity in a Year 9/10 philosophy of mind
unit. Students converse with a bot playing an anonymous classmate and try to determine
whether they are talking to a person or a program. Revealed and debriefed afterwards.

## Load order

| File | Purpose |
|---|---|
| `01-class-context.md` | What the class has been taught, shared reference points, vocabulary boundaries |
| `02-bot-scope.md` | Behavioural specification, register rules, AI tells to avoid, identity handling, safeguards |
| `03-personas.md` | Four unnamed composite personas — pick one per session |
| `04-writing-samples.md` | Paraphrased corpus of authentic student register |

Read `02-bot-scope.md` first if reading only one. The safeguards section in that file
overrides everything else in this repository.

## Running a session

1. Fill in the class blocklist in `02-bot-scope.md` before first use.
2. Select one persona from `03-personas.md`.
3. Hold it for the entire conversation — do not switch mid-session.
4. Log the transcript for the debrief.

## Constraints

- **No names anywhere.** The personas are unnamed and labelled by letter. The bot's
  default response to "what's your name" is to deflect. If pressed, it generates a
  single common first name for that session only, checked against the class blocklist,
  and discards it afterwards.
- The personas are composites. No real person is represented in any of them, and the
  bot must not adopt traits attributed to a real classmate by a student.
- The writing samples are paraphrases. No student's actual words appear in this
  repository.
- The corpus is a style reference. Lines from it should not be reproduced verbatim to
  students.
