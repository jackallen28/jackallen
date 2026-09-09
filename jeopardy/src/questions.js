/**
 * Clue bank for "Mind Jeopardy".
 *
 * Six categories of five clues, values 100–500, difficulty climbing with the
 * value. Then one Final Jeopardy clue that only pays off if you have followed
 * several weeks at once.
 *
 * Each clue carries:
 *   text    - what the host reads out and what goes up on the projector
 *   answer  - the canonical answer, shown on the host's laptop the whole time
 *             and on the projector only once the clue is over
 *   accept  - alias phrases the local matcher accepts. A guess matches an alias
 *             when every significant word of that alias appears in it (fuzzily,
 *             so typos and plurals are fine). Keep aliases specific: a bare
 *             'brain' would match half the board.
 *   note    - optional; printed on the host screen only, to say out loud after
 *             the reveal. This is where the teaching happens.
 */

export const CATEGORIES = [
  {
    id: 'perception',
    name: 'PERCEPTION DECEPTION',
    blurb: 'Weeks 2–3 — sensation, perception, illusion',
    clues: [
      {
        value: 100,
        text: 'This is the raw physical data your eyes, ears and skin collect. What your brain then does with it is called perception.',
        answer: 'Sensation',
        accept: ['sensation', 'sensory input', 'raw sensory data', 'raw data'],
        note: 'Sensation is collection; perception is interpretation. Every illusion in this unit lives in the gap between them.',
      },
      {
        value: 200,
        text: 'In this classic test, naming the colour of the ink fights against your automatic urge to read the word itself.',
        answer: 'The Stroop Test',
        accept: ['the stroop test', 'stroop test', 'stroop'],
        note: 'Reading is so automatic it interferes with a task you are consciously trying to do — top-down processing you cannot switch off.',
      },
      {
        value: 300,
        text: 'Closure, proximity and similarity are grouping principles from this school of psychology, whose German name means "shape" or "form".',
        answer: 'Gestalt psychology',
        accept: ['gestalt', 'gestalt psychology', 'gestalt principles'],
        note: 'All unified by the Law of Prägnanz — the brain always reaches for the simplest, most ordered reading available.',
      },
      {
        value: 400,
        text: 'Watch lips mouth "ga" while a speaker plays "ba", and you will hear "da". This effect proves vision can overrule hearing.',
        answer: 'The McGurk Effect',
        accept: ['the mcgurk effect', 'mcgurk effect', 'mcgurk'],
        note: 'You cannot un-hear it even when you know the trick. Perception is not something you consciously control.',
      },
      {
        value: 500,
        text: 'Synchronised brushing convinces your brain that a fake limb on the table is part of your body. Today it helps amputees with phantom limb pain.',
        answer: 'The Rubber Hand Illusion',
        accept: ['the rubber hand illusion', 'rubber hand illusion', 'rubber hand'],
        note: 'Your sense of which body is yours is a construction too — and one that can be edited in about 90 seconds.',
      },
    ],
  },

  {
    id: 'soul',
    name: 'THE SOUL SHOP',
    blurb: 'Weeks 4–5 — ancient and religious accounts of the self',
    clues: [
      {
        value: 100,
        text: 'Plato pictured the soul as a charioteer driving two horses. This part of the soul is the charioteer itself.',
        answer: 'Reason',
        accept: ['reason', 'the charioteer', 'nous', 'rationality', 'rational part'],
        note: 'The white horse is Spirit, the black horse Appetite. Reason is meant to steer both — Plato is not confident it always does.',
      },
      {
        value: 200,
        text: 'In this tradition the soul is created by God, immortal, made in his image — imago Dei — and faces judgement after death.',
        answer: 'Christianity',
        accept: ['christianity', 'christian', 'the christian soul', 'christian tradition'],
        note: 'Note how much this shares with Descartes: a soul that is not the body and can outlast it.',
      },
      {
        value: 300,
        text: 'One of the Three Marks of Existence, this Buddhist doctrine says there is no permanent, fixed self at all.',
        answer: 'Anattā (non-self)',
        accept: ['anatta', 'non self', 'no self', 'the doctrine of no self'],
        note: 'The Chariot Analogy: take a chariot apart and there is no chariot left over. "Self" is a label for parts working together.',
      },
      {
        value: 400,
        text: 'In Hinduism this is the eternal, unchanging true Self — ultimately identical with Brahman.',
        answer: 'Ātman',
        accept: ['atman', 'the atman'],
        note: 'Ātman and anattā are direct opposites, and both are answers to the same question. Useful for a compare-and-contrast paragraph.',
      },
      {
        value: 500,
        text: 'This Persian philosopher imagined a person created fully formed, floating in mid-air with every sense shrouded — who still cannot doubt that they exist.',
        answer: 'Avicenna (Ibn Sina)',
        accept: ['avicenna', 'ibn sina', 'the floating man', 'the flying man'],
        note: 'Six centuries before Descartes, and it reaches almost exactly the cogito. Worth raising if anyone calls Descartes original.',
      },
    ],
  },

  {
    id: 'descartes',
    name: "DESCARTES' DOUBTS",
    blurb: 'Week 5 — dualism, the method of doubt, the objections',
    clues: [
      {
        value: 100,
        text: 'Three Latin words that survive everything else Descartes managed to doubt.',
        answer: 'Cogito, ergo sum',
        accept: ['cogito ergo sum', 'i think therefore i am', 'the cogito', 'cogito'],
        note: 'Doubting is a kind of thinking. So the harder he doubts, the more certain he becomes that something is doing the doubting.',
      },
      {
        value: 200,
        text: 'Descartes\' view that mind and body are two fundamentally different kinds of stuff goes by this two-word name.',
        answer: 'Substance dualism',
        accept: ['substance dualism', 'cartesian dualism', 'dualism'],
        note: 'Substance, not just "two things" — he means two different kinds of existence: thinking stuff and extended stuff.',
      },
      {
        value: 300,
        text: 'Descartes claimed the mind and body made contact at this small structure in the brain.',
        answer: 'The pineal gland',
        accept: ['the pineal gland', 'pineal gland', 'pineal'],
        note: 'It answers where, and never how. Naming a location does not explain the interaction — that is the whole problem.',
      },
      {
        value: 400,
        text: 'In 1643 this princess asked Descartes how something with no size, shape or location could possibly push a physical body around.',
        answer: 'Elisabeth of Bohemia',
        accept: ['elisabeth of bohemia', 'princess elisabeth', 'elizabeth of bohemia', 'elisabeth'],
        note: 'The Interaction Problem. Four centuries on, no dualist has a clean answer — this is the single strongest objection in the unit.',
      },
      {
        value: 500,
        text: 'This principle — prefer the explanation making the fewest assumptions — counts against dualism, since one substance is simpler than two.',
        answer: "Ockham's Razor",
        accept: ['ockhams razor', 'occams razor', 'the razor', 'parsimony'],
        note: 'Not proof that dualism is false — an argument that it is doing more work than it needs to. A useful distinction for essays.',
      },
    ],
  },

  {
    id: 'brain',
    name: 'THIS IS YOUR BRAIN',
    blurb: 'Week 6 — neuroscience, pharmacology, consciousness',
    clues: [
      {
        value: 100,
        text: 'In 1848 this railroad foreman survived a 1.1-metre tamping iron blasting straight through his left frontal lobe.',
        answer: 'Phineas Gage',
        accept: ['phineas gage', 'gage'],
        note: 'He was conscious and talking within minutes. The physical damage was never the interesting part.',
      },
      {
        value: 200,
        text: 'Gage kept his speech, memory, movement and intelligence. This is what changed so completely that friends said he was "no longer Gage".',
        answer: 'His personality',
        accept: ['his personality', 'personality', 'his character', 'his temperament'],
        note: 'Specific damage, specific change. That precision is what makes it evidence rather than an anecdote.',
      },
      {
        value: 300,
        text: 'The position that everything mental is caused by, or simply identical to, physical brain processes.',
        answer: 'Materialism (physicalism)',
        accept: ['materialism', 'physicalism', 'monism', 'material monism'],
        note: 'It dissolves the Interaction Problem entirely — if there is only one kind of stuff, nothing has to reach across a gap.',
      },
      {
        value: 400,
        text: 'Dualists answer Gage with this analogy: smash the receiver and the music distorts, but the music never came from inside the box.',
        answer: 'The damaged radio',
        accept: ['the damaged radio', 'damaged radio', 'broken radio', 'the radio analogy', 'radio'],
        note: 'It is a real answer, not a dodge. Ask which is simpler — and you are back at Ockham\'s Razor.',
      },
      {
        value: 500,
        text: 'In "The Nature of Mind" this Australian philosopher defined consciousness as awareness of the state of our own mind — an inner eye.',
        answer: 'David Armstrong',
        accept: ['david armstrong', 'armstrong'],
        note: 'His driving example: you can travel miles on autopilot with no awareness of doing it. Thought without consciousness.',
      },
    ],
  },

  {
    id: 'machines',
    name: 'MACHINE MINDS',
    blurb: 'Weeks 7–8 — Turing, functionalism, Searle',
    clues: [
      {
        value: 100,
        text: 'Turing\'s own name for the test we now name after him.',
        answer: 'The Imitation Game',
        accept: ['the imitation game', 'imitation game'],
        note: 'He replaced "can machines think?" — which he thought meaningless — with a question you can actually run.',
      },
      {
        value: 200,
        text: 'The view that a mind is defined by what it does, not what it happens to be made of.',
        answer: 'Functionalism',
        accept: ['functionalism', 'functionalist', 'functional'],
        note: 'If it is the job that matters and not the material, then carbon has no special claim over silicon.',
      },
      {
        value: 300,
        text: 'In Searle\'s 1980 thought experiment, a man locked in a room follows a rulebook to shuffle symbols he does not understand a word of.',
        answer: 'The Chinese Room',
        accept: ['the chinese room', 'chinese room', 'searles chinese room'],
        note: 'From outside, the room passes the Turing Test in Chinese. From inside, nobody understands anything.',
      },
      {
        value: 400,
        text: 'Four words: Searle\'s conclusion about why shuffling symbols by rule can never amount to understanding.',
        answer: 'Syntax is not semantics',
        accept: ['syntax is not semantics', 'syntax isnt semantics', 'syntax not semantics',
                 'rules are not meaning', 'symbols are not meaning'],
        note: 'Syntax is the rules for moving symbols. Semantics is what they mean. Searle says you never get the second from the first.',
      },
      {
        value: 500,
        text: 'This 2014 chatbot was built to pose as a 13-year-old Ukrainian boy, so that its mistakes read as youth and a second language.',
        answer: 'Eugene Goostman',
        accept: ['eugene goostman', 'goostman', 'eugene'],
        note: 'It did not get smarter — it lowered what counted as passing. Exactly the loophole Searle predicted.',
      },
    ],
  },

  {
    id: 'source',
    name: 'SOURCE CODE',
    blurb: 'Assessment skills — PCASTLE and the five significance criteria',
    clues: [
      {
        value: 100,
        text: 'The "A" in PCASTLE: who made the source, and what background or expertise they brought to it.',
        answer: 'Author',
        accept: ['author', 'a for author', 'who made it', 'who wrote it'],
        note: 'Not just a name — what they knew, what they believed, and what they stood to gain.',
      },
      {
        value: 200,
        text: 'The "P" in PCASTLE: the question of why the source was made at all, and what its creator wanted from it.',
        answer: 'Purpose',
        accept: ['purpose', 'p for purpose', 'why it was made', 'why it was created'],
        note: 'Usually the most productive letter. Almost every source was made to do something to somebody.',
      },
      {
        value: 300,
        text: 'This significance criterion asks how long the effects lasted, and whether the thing is still shaping how we think today.',
        answer: 'Durability',
        accept: ['durability', 'how long it lasted', 'lasting effects'],
        note: 'Durability is about time. Do not confuse it with Relevance, which is about us, now.',
      },
      {
        value: 400,
        text: 'The "E" in PCASTLE: what facts the source actually provides, how reliable they are, and what it leaves out.',
        answer: 'Evidence',
        accept: ['evidence', 'e for evidence', 'the facts provided', 'reliability'],
        note: 'The letter students skip most often, and the one that decides whether a source is any use to you.',
      },
      {
        value: 500,
        text: 'This significance criterion asks how profoundly an event changed people\'s thinking — as opposed to Quantity, which asks how many it touched.',
        answer: 'Depth',
        accept: ['depth', 'how deeply it changed thinking', 'how deeply'],
        note: 'Depth versus Quantity is the classic essay move: a thing can change everything for a few, or a little for millions.',
      },
    ],
  },
];

/**
 * Final Jeopardy. Every team wagers before seeing the clue, so it has to be
 * attemptable by anyone who has followed the unit — the drama comes from the
 * wager, not from the clue being impossible.
 */
export const FINAL = {
  category: 'THE BIG PICTURE',
  text: 'Elisabeth of Bohemia\'s Interaction Problem, the Law of Conservation of Energy, and Ockham\'s Razor are three completely different objections — all aimed at the same theory. Name that theory.',
  answer: 'Substance dualism (Cartesian dualism)',
  accept: ['substance dualism', 'cartesian dualism', 'dualism', 'descartes dualism',
           'descartes theory of mind and body', 'mind body dualism'],
  note: 'Three objections from three different directions — metaphysics, physics and logic — converging on one target. That convergence is what makes an argument strong, and it is exactly the move to run in the essay.',
};

export function totalClues() {
  return CATEGORIES.reduce((n, c) => n + c.clues.length, 0);
}

export function findClue(categoryIndex, clueIndex) {
  const category = CATEGORIES[categoryIndex];
  if (!category) return null;
  const clue = category.clues[clueIndex];
  return clue ? { category, clue } : null;
}
