/**
 * Mind Feud — game state machine.
 *
 * Phases:
 *   lobby      teams join, host sees who is connected
 *   intro      round title card on the big screen
 *   buzzing    question is up, buzzers live, first team in takes control
 *   answering  the team in control types guesses until they get one wrong
 *   roundOver  full board revealed, scores updated
 *   finalIntro the leading team is called up
 *   final      rapid fire against the clock
 *   spoiler    the trailing team gets the questions the leaders missed
 *   gameOver   final scores
 *
 * House rules (deliberately different from the TV show — see README):
 *   - 6 answers per board, not 8.
 *   - ONE wrong answer ends your turn, not three strikes.
 *   - Points go to whichever team reveals the answer, so a hot streak pays.
 *   - Control alternates on every miss until the board is cleared or the
 *     round's miss limit is hit.
 */

import { ROUNDS, RAPID_FIRE } from './questions.js';

export const TEAMS = ['A', 'B'];

const DEFAULTS = {
  teamNames: { A: 'Team A', B: 'Team B' },
  missLimit: 4,          // total misses (both teams) before the round is called
  buzzToReclaim: false,  // true = both teams re-buzz for control after a miss
  finalSeconds: 90,
  spoilerSeconds: 45,
  finalTarget: 70,       // points needed in the final to trigger the big bonus
  finalBonus: 200,
  rapidValue: 10,
  spoilerValue: 15,
  enableSpoiler: true,
};

export class Game {
  constructor(options = {}) {
    this.settings = { ...DEFAULTS, ...options };
    this.reset();
  }

  reset() {
    this.phase = 'lobby';
    this.scores = { A: 0, B: 0 };
    this.roundIndex = -1;
    this.questionIndex = 0;
    this.board = null;         // { question, revealed[], misses, roundId, multiplier }
    this.control = null;       // 'A' | 'B'
    this.buzzLocked = true;
    this.buzzedBy = null;
    this.lastEvent = null;     // { kind, team, text, detail }
    this.log = [];
    this.usedQuestions = new Set();
    this.final = null;
    this.spoiler = null;
    this.winner = null;
    this.version = 0;
  }

  /* ---------------------------------------------------------------- */
  /* helpers                                                           */
  /* ---------------------------------------------------------------- */

  touch() {
    this.version += 1;
  }

  note(kind, detail = {}) {
    this.lastEvent = { kind, at: Date.now(), ...detail };
    this.log.unshift(this.lastEvent);
    if (this.log.length > 60) this.log.pop();
  }

  otherTeam(team) {
    return team === 'A' ? 'B' : 'A';
  }

  leadingTeam() {
    if (this.scores.A === this.scores.B) return null;
    return this.scores.A > this.scores.B ? 'A' : 'B';
  }

  get round() {
    return this.roundIndex >= 0 ? ROUNDS[this.roundIndex] : null;
  }

  /* ---------------------------------------------------------------- */
  /* board rounds                                                      */
  /* ---------------------------------------------------------------- */

  /** Move to a round. Pass an index, or omit to advance to the next one. */
  startRound(index = this.roundIndex + 1) {
    if (index < 0 || index >= ROUNDS.length) return { error: 'No such round.' };
    this.roundIndex = index;
    this.questionIndex = 0;
    this.phase = 'intro';
    this.board = null;
    this.control = null;
    this.buzzLocked = true;
    this.buzzedBy = null;
    this.note('roundIntro', { round: ROUNDS[index].name });
    this.touch();
    return { ok: true };
  }

  /**
   * Put a question on the board with the buzzers live.
   * @param {string} [questionId] specific question, else the next unused one.
   */
  openQuestion(questionId) {
    const round = this.round;
    if (!round) return { error: 'Start a round first.' };

    let question = questionId
      ? round.questions.find((q) => q.id === questionId)
      : round.questions.find((q) => !this.usedQuestions.has(q.id)) || round.questions[0];
    if (!question) return { error: 'No question available.' };

    this.usedQuestions.add(question.id);
    this.board = {
      questionId: question.id,
      prompt: question.prompt,
      multiplier: round.multiplier,
      revealed: question.answers.map(() => null), // null | 'A' | 'B' | 'host'
      misses: 0,
      pot: { A: 0, B: 0 },
      nearMissesHit: [],
    };
    this.phase = 'buzzing';
    this.control = null;
    this.buzzLocked = false;
    this.buzzedBy = null;
    this.note('questionOpen', { prompt: question.prompt });
    this.touch();
    return { ok: true };
  }

  /** A team hits the space bar. First one in wins; the rest are ignored. */
  buzz(team, playerName) {
    if (this.phase === 'final' || this.phase === 'spoiler') {
      return this.finalPass(team);
    }
    if (this.phase !== 'buzzing') return { error: 'Buzzers are not live.' };
    if (this.buzzLocked) return { error: 'Buzzers are locked.' };
    if (this.buzzedBy) return { error: 'Too late.' };

    this.buzzLocked = true;
    this.buzzedBy = team;
    this.control = team;
    this.phase = 'answering';
    this.note('buzz', { team, player: playerName });
    this.touch();
    return { ok: true, fx: 'buzz' };
  }

  /**
   * Apply a judged guess to the board.
   * @param {'A'|'B'} team
   * @param {string} text the raw typed guess, for the transcript
   * @param {{kind:'board'|'nearmiss'|'none', index:number, source:string}} verdict
   */
  applyGuess(team, text, verdict) {
    if (this.phase !== 'answering') return { error: 'Nobody has control right now.' };
    if (team !== this.control) return { error: 'It is not your turn.' };
    const question = this.currentQuestion();
    if (!question) return { error: 'No question on the board.' };

    if (verdict.kind === 'board') {
      if (this.board.revealed[verdict.index]) {
        // Already up there. Costs nothing but the clock — the show does the
        // same, and penalising it would punish a team for not reading fast.
        this.note('duplicate', { team, text, index: verdict.index });
        this.touch();
        return { ok: true, outcome: 'duplicate', fx: 'duplicate', index: verdict.index };
      }
      const value = question.answers[verdict.index].points * this.board.multiplier;
      this.board.revealed[verdict.index] = team;
      this.board.pot[team] += value;
      this.scores[team] += value;
      this.note('correct', {
        team, text, index: verdict.index, value, source: verdict.source,
        answer: question.answers[verdict.index].text,
      });
      this.touch();

      if (this.board.revealed.every(Boolean)) {
        this.endRoundBoard('swept');
        return { ok: true, outcome: 'correct', fx: 'sweep', index: verdict.index, value };
      }
      return { ok: true, outcome: 'correct', fx: 'ding', index: verdict.index, value };
    }

    // Wrong — including a correct-but-not-on-the-board near miss, which is the
    // rule and also the best teaching moment in the game.
    const near = verdict.kind === 'nearmiss'
      ? (question.nearMiss || [])[verdict.index]
      : null;
    if (near) this.board.nearMissesHit.push(near.text);

    this.board.misses += 1;
    this.note(near ? 'nearMiss' : 'wrong', {
      team, text, source: verdict.source, detail: near ? near.text : null,
    });

    if (this.board.misses >= this.settings.missLimit || this.board.revealed.every(Boolean)) {
      this.endRoundBoard('missLimit');
      this.touch();
      return { ok: true, outcome: near ? 'nearmiss' : 'wrong', fx: near ? 'nearmiss' : 'strike', ended: true };
    }

    this.control = this.otherTeam(team);
    if (this.settings.buzzToReclaim) {
      this.phase = 'buzzing';
      this.control = null;
      this.buzzedBy = null;
      this.buzzLocked = false;
    }
    this.touch();
    return {
      ok: true,
      outcome: near ? 'nearmiss' : 'wrong',
      fx: near ? 'nearmiss' : 'strike',
      passedTo: this.control,
    };
  }

  /** Host reveals a slot by hand — for an answer shouted correctly but mistyped. */
  hostReveal(index, team = null) {
    if (!this.board) return { error: 'No board.' };
    if (this.board.revealed[index]) return { error: 'Already revealed.' };
    const question = this.currentQuestion();
    const value = question.answers[index].points * this.board.multiplier;
    this.board.revealed[index] = team || 'host';
    if (team) {
      this.board.pot[team] += value;
      this.scores[team] += value;
    }
    this.note('hostReveal', {
      index, team, value: team ? value : 0, answer: question.answers[index].text,
    });
    if (this.board.revealed.every(Boolean)) this.endRoundBoard('swept');
    this.touch();
    return { ok: true, fx: 'ding' };
  }

  endRoundBoard(reason = 'ended') {
    if (!this.board) return { error: 'No board.' };
    this.board.revealed = this.board.revealed.map((r) => r || 'unrevealed');
    this.phase = 'roundOver';
    this.control = null;
    this.buzzLocked = true;
    this.buzzedBy = null;
    this.note('roundOver', { reason, pot: { ...this.board.pot } });
    this.touch();
    return { ok: true, fx: 'roundEnd' };
  }

  currentQuestion() {
    if (!this.board) return null;
    for (const round of ROUNDS) {
      const q = round.questions.find((x) => x.id === this.board.questionId);
      if (q) return q;
    }
    return null;
  }

  /* ---------------------------------------------------------------- */
  /* final round                                                       */
  /* ---------------------------------------------------------------- */

  /**
   * @param {'A'|'B'} [team] override the automatic pick (needed on a tie).
   */
  startFinal(team) {
    const chosen = team || this.leadingTeam();
    if (!chosen) return { error: 'Scores are tied — pick which team plays the final.' };

    const deck = shuffle([...RAPID_FIRE]);
    this.final = {
      team: chosen,
      deck,
      cursor: 0,
      correct: 0,
      points: 0,
      missed: [],       // indices into deck, for the spoiler round
      secondsLeft: this.settings.finalSeconds,
      running: false,
      hitTarget: false,
    };
    this.spoiler = null;
    this.phase = 'finalIntro';
    this.control = chosen;
    this.note('finalIntro', { team: chosen });
    this.touch();
    return { ok: true };
  }

  startFinalClock() {
    if (!this.final) return { error: 'No final round set up.' };
    this.final.running = true;
    this.phase = 'final';
    this.note('finalStart', { team: this.final.team });
    this.touch();
    return { ok: true, fx: 'go' };
  }

  currentRapid() {
    const stage = this.phase === 'spoiler' ? this.spoiler : this.final;
    if (!stage) return null;
    if (this.phase === 'spoiler') {
      const idx = stage.queue[stage.cursor];
      return idx === undefined ? null : this.final.deck[idx];
    }
    return stage.deck[stage.cursor] || null;
  }

  applyRapidGuess(team, text, correct) {
    const isSpoiler = this.phase === 'spoiler';
    const stage = isSpoiler ? this.spoiler : this.final;
    if (!stage || !stage.running) return { error: 'The clock is not running.' };
    if (team !== stage.team) return { error: 'It is not your turn.' };

    const question = this.currentRapid();
    if (!question) return { error: 'No question up.' };

    if (correct) {
      const value = isSpoiler ? this.settings.spoilerValue : this.settings.rapidValue;
      stage.correct += 1;
      stage.points += value;
      this.scores[team] += value;
      this.note('rapidCorrect', { team, text, value, prompt: question.prompt });
      this.advanceRapid(true);
      return { ok: true, outcome: 'correct', fx: 'ding', value };
    }

    this.note('rapidWrong', { team, text, prompt: question.prompt });
    this.touch();
    return { ok: true, outcome: 'wrong', fx: 'strike' };
  }

  /** Space bar during the final = pass. The question falls to the spoiler pile. */
  finalPass(team) {
    const isSpoiler = this.phase === 'spoiler';
    const stage = isSpoiler ? this.spoiler : this.final;
    if (!stage || !stage.running) return { error: 'The clock is not running.' };
    if (team !== stage.team) return { error: 'Not your turn.' };
    this.note('rapidPass', { team });
    this.advanceRapid(false);
    return { ok: true, fx: 'pass' };
  }

  advanceRapid(wasCorrect) {
    const isSpoiler = this.phase === 'spoiler';
    const stage = isSpoiler ? this.spoiler : this.final;
    if (!isSpoiler && !wasCorrect) this.final.missed.push(this.final.cursor);
    stage.cursor += 1;
    const exhausted = isSpoiler
      ? stage.cursor >= stage.queue.length
      : stage.cursor >= stage.deck.length;
    if (exhausted) this.endRapid();
    this.touch();
  }

  tickClock() {
    const stage = this.phase === 'spoiler' ? this.spoiler
      : this.phase === 'final' ? this.final : null;
    if (!stage || !stage.running) return false;
    stage.secondsLeft -= 1;
    if (stage.secondsLeft <= 0) {
      stage.secondsLeft = 0;
      this.endRapid();
    }
    this.touch();
    return true;
  }

  endRapid() {
    if (this.phase === 'final' && this.final) {
      this.final.running = false;
      this.final.hitTarget = this.final.points >= this.settings.finalTarget;
      if (this.final.hitTarget) {
        this.scores[this.final.team] += this.settings.finalBonus;
      }
      this.note('finalEnd', {
        team: this.final.team,
        points: this.final.points,
        hitTarget: this.final.hitTarget,
        bonus: this.final.hitTarget ? this.settings.finalBonus : 0,
      });

      // The spoiler pile is everything the leaders passed on, then everything
      // the clock never let them reach — so the trailing team always gets a
      // live comeback shot rather than watching the last five minutes.
      const spoilerTeam = this.otherTeam(this.final.team);
      const passed = this.final.missed.filter((i) => i < this.final.deck.length);
      const unreached = [];
      for (let i = this.final.cursor; i < this.final.deck.length; i++) {
        if (!passed.includes(i)) unreached.push(i);
      }
      const queue = [...passed, ...unreached];
      if (this.settings.enableSpoiler && queue.length > 0) {
        this.spoiler = {
          team: spoilerTeam,
          queue,
          cursor: 0,
          correct: 0,
          points: 0,
          secondsLeft: this.settings.spoilerSeconds,
          running: false,
        };
        this.phase = 'spoilerIntro';
      } else {
        this.finish();
      }
      this.touch();
      return;
    }

    if (this.phase === 'spoiler' && this.spoiler) {
      this.spoiler.running = false;
      this.note('spoilerEnd', { team: this.spoiler.team, points: this.spoiler.points });
      this.finish();
      this.touch();
    }
  }

  startSpoilerClock() {
    if (!this.spoiler) return { error: 'No spoiler round.' };
    this.spoiler.running = true;
    this.phase = 'spoiler';
    this.note('spoilerStart', { team: this.spoiler.team });
    this.touch();
    return { ok: true, fx: 'go' };
  }

  finish() {
    this.phase = 'gameOver';
    this.winner = this.scores.A === this.scores.B ? 'tie'
      : this.scores.A > this.scores.B ? 'A' : 'B';
    this.note('gameOver', { winner: this.winner, scores: { ...this.scores } });
    this.touch();
  }

  adjustScore(team, delta) {
    this.scores[team] = Math.max(0, this.scores[team] + delta);
    this.note('adjust', { team, delta });
    this.touch();
    return { ok: true };
  }

  setTeamName(team, name) {
    this.settings.teamNames[team] = String(name || '').slice(0, 24) || `Team ${team}`;
    this.touch();
    return { ok: true };
  }

  /* ---------------------------------------------------------------- */
  /* serialisation                                                     */
  /* ---------------------------------------------------------------- */

  /**
   * @param {'host'|'A'|'B'} audience — players never receive unrevealed answers.
   */
  snapshot(audience = 'host') {
    const question = this.currentQuestion();
    const isHost = audience === 'host';

    let board = null;
    if (this.board && question) {
      board = {
        prompt: this.board.prompt,
        multiplier: this.board.multiplier,
        misses: this.board.misses,
        missLimit: this.settings.missLimit,
        pot: this.board.pot,
        nearMissesHit: this.board.nearMissesHit,
        slots: question.answers.map((a, i) => {
          const state = this.board.revealed[i];
          const open = state && state !== 'unrevealed';
          const shown = open || state === 'unrevealed';
          return {
            index: i,
            revealed: Boolean(state),
            by: open ? state : null,
            missed: state === 'unrevealed',
            // The host screen is the teacher's screen and always shows
            // everything; team screens only ever see what is on the board.
            text: (shown || isHost) ? a.text : null,
            points: (shown || isHost) ? a.points * this.board.multiplier : null,
          };
        }),
      };
    }

    const rapidQuestion = this.currentRapid();
    const stage = this.phase === 'spoiler' ? this.spoiler : this.final;

    return {
      version: this.version,
      phase: this.phase,
      scores: this.scores,
      teamNames: this.settings.teamNames,
      round: this.round
        ? { index: this.roundIndex, name: this.round.name, weeks: this.round.weeks, multiplier: this.round.multiplier, total: ROUNDS.length }
        : null,
      roundList: ROUNDS.map((r, i) => ({
        index: i, name: r.name, multiplier: r.multiplier,
        questions: r.questions.map((q) => ({ id: q.id, prompt: q.prompt, used: this.usedQuestions.has(q.id) })),
      })),
      board,
      control: this.control,
      buzzedBy: this.buzzedBy,
      buzzLocked: this.buzzLocked,
      lastEvent: this.lastEvent,
      log: isHost ? this.log.slice(0, 12) : [],
      final: this.final ? {
        team: this.final.team,
        correct: this.final.correct,
        points: this.final.points,
        secondsLeft: this.final.secondsLeft,
        running: this.final.running,
        target: this.settings.finalTarget,
        bonus: this.settings.finalBonus,
        asked: this.final.cursor,
        total: this.final.deck.length,
        hitTarget: this.final.hitTarget,
        missedCount: this.final.missed.length,
      } : null,
      spoiler: this.spoiler ? {
        team: this.spoiler.team,
        correct: this.spoiler.correct,
        points: this.spoiler.points,
        secondsLeft: this.spoiler.secondsLeft,
        running: this.spoiler.running,
        asked: this.spoiler.cursor,
        total: this.spoiler.queue.length,
      } : null,
      // The rapid-fire prompt goes to the host and to the team on the clock.
      rapidPrompt: (rapidQuestion && stage && (isHost || audience === stage.team))
        ? rapidQuestion.prompt : null,
      winner: this.winner,
      settings: {
        missLimit: this.settings.missLimit,
        buzzToReclaim: this.settings.buzzToReclaim,
        enableSpoiler: this.settings.enableSpoiler,
      },
    };
  }
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}
