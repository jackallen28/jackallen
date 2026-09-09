/**
 * Mind Jeopardy — game state machine.
 *
 * Phases, in the order a lesson walks through them:
 *   setup        host names the teams (any number, decided in the room)
 *   board        the grid is up; the picking team chooses a clue
 *   clue         clue is on the projector, buzzers CLOSED while the host reads
 *   open         buzzers live
 *   answering    one team has it and is typing; a countdown is running
 *   revealed     answer is up, host reads the teaching note, then back to board
 *   finalIntro   Final Jeopardy category announced, before anyone sees the clue
 *   finalWager   every team commits a wager privately
 *   finalClue    clue is up; every team writes an answer at the same time
 *   finalReveal  host reveals team by team — answer, then wager, then new score
 *   gameOver     final scores
 *
 * House rules, kept deliberately simple:
 *   - No Daily Doubles.
 *   - No "in the form of a question" requirement.
 *   - A wrong answer costs you the clue, not points. You are locked out and the
 *     buzzers reopen for everyone else. Nobody can go backwards, so no team is
 *     ever mathematically out of it before Final Jeopardy.
 *   - A Final Jeopardy wager cannot exceed your score, so scores never go
 *     negative anywhere in the game.
 */

import { CATEGORIES, FINAL, findClue } from './questions.js';

const DEFAULTS = {
  answerSeconds: 15,   // countdown once a team has buzzed; 0 disables it
  finalSeconds: 60,    // writing time for Final Jeopardy
  wagerSeconds: 45,    // thinking time for the wager
};

export class Game {
  constructor(options = {}) {
    this.settings = { ...DEFAULTS, ...options };
    this.reset();
  }

  reset() {
    this.phase = 'setup';
    this.teams = [];          // [{ id, name, score }]
    this.nextTeamNumber = 1;
    this.used = CATEGORIES.map((c) => c.clues.map(() => false));
    this.picker = null;       // team id whose turn it is to choose
    this.active = null;       // the clue in play
    this.final = null;
    this.lastEvent = null;
    this.log = [];
    this.winner = null;
    this.version = 0;
  }

  touch() { this.version += 1; }

  note(kind, detail = {}) {
    this.lastEvent = { kind, at: Date.now(), ...detail };
    this.log.unshift(this.lastEvent);
    if (this.log.length > 60) this.log.pop();
  }

  team(id) { return this.teams.find((t) => t.id === id) || null; }
  teamName(id) { return this.team(id)?.name || '—'; }

  /* ---------------------------------------------------------------- */
  /* setup                                                             */
  /* ---------------------------------------------------------------- */

  addTeam(name) {
    if (this.phase !== 'setup') return { error: 'The game has already started.' };
    if (this.teams.length >= 8) return { error: 'Eight teams is the maximum.' };
    const id = `t${this.nextTeamNumber++}`;
    this.teams.push({
      id,
      name: String(name || '').trim().slice(0, 24) || `Team ${this.teams.length + 1}`,
      score: 0,
    });
    this.touch();
    return { ok: true, id };
  }

  removeTeam(id) {
    if (this.phase !== 'setup') return { error: 'The game has already started.' };
    this.teams = this.teams.filter((t) => t.id !== id);
    this.touch();
    return { ok: true };
  }

  renameTeam(id, name) {
    const team = this.team(id);
    if (!team) return { error: 'No such team.' };
    team.name = String(name || '').trim().slice(0, 24) || team.name;
    this.touch();
    return { ok: true };
  }

  startGame() {
    if (this.teams.length < 2) return { error: 'Add at least two teams.' };
    this.phase = 'board';
    this.picker = this.teams[0].id;
    this.note('gameStart', { teams: this.teams.length });
    this.touch();
    return { ok: true, fx: 'themeIn' };
  }

  /* ---------------------------------------------------------------- */
  /* the board                                                         */
  /* ---------------------------------------------------------------- */

  pickClue(categoryIndex, clueIndex) {
    if (this.phase !== 'board') return { error: 'Not on the board right now.' };
    const found = findClue(categoryIndex, clueIndex);
    if (!found) return { error: 'No such clue.' };
    if (this.used[categoryIndex][clueIndex]) return { error: 'That clue is gone.' };

    this.used[categoryIndex][clueIndex] = true;
    this.active = {
      categoryIndex,
      clueIndex,
      value: found.clue.value,
      buzzedBy: null,
      lockedOut: [],
      secondsLeft: 0,
      running: false,
      correctBy: null,
    };
    this.phase = 'clue';
    this.note('clueUp', { category: found.category.name, value: found.clue.value });
    this.touch();
    return { ok: true, fx: 'select' };
  }

  /** Host has finished reading the clue aloud. */
  openBuzzers() {
    if (!this.active) return { error: 'No clue in play.' };
    if (this.phase !== 'clue' && this.phase !== 'answering') {
      return { error: 'Buzzers cannot open from here.' };
    }
    if (this.everyoneLockedOut()) return this.revealAnswer('all locked out');
    this.phase = 'open';
    this.active.buzzedBy = null;
    this.active.running = false;
    this.active.secondsLeft = 0;
    this.note('buzzersOpen');
    this.touch();
    return { ok: true, fx: 'open' };
  }

  everyoneLockedOut() {
    return this.teams.every((t) => this.active.lockedOut.includes(t.id));
  }

  buzz(teamId) {
    if (this.phase !== 'open') return { error: 'Buzzers are not live.' };
    if (!this.team(teamId)) return { error: 'Unknown team.' };
    if (this.active.lockedOut.includes(teamId)) return { error: 'You have already had a go.' };
    if (this.active.buzzedBy) return { error: 'Too late.' };

    this.active.buzzedBy = teamId;
    this.active.secondsLeft = this.settings.answerSeconds;
    this.active.running = this.settings.answerSeconds > 0;
    this.phase = 'answering';
    this.note('buzz', { team: teamId, name: this.teamName(teamId) });
    this.touch();
    return { ok: true, fx: 'buzz' };
  }

  /**
   * Resolve the team currently holding the clue.
   * @param {boolean} correct
   * @param {string} text what they typed, for the transcript
   * @param {string} source who decided — 'local', 'ai' or 'host'
   */
  resolveAnswer(correct, text = '', source = 'host') {
    if (this.phase !== 'answering' || !this.active?.buzzedBy) {
      return { error: 'Nobody is holding the clue.' };
    }
    const teamId = this.active.buzzedBy;
    const team = this.team(teamId);
    this.active.running = false;

    if (correct) {
      team.score += this.active.value;
      this.active.correctBy = teamId;
      this.picker = teamId; // you pick next, exactly as on the show
      this.note('correct', { team: teamId, name: team.name, text, value: this.active.value, source });
      this.touch();
      return this.revealAnswer('correct');
    }

    // Wrong: you lose the clue, not points. Everyone else gets another shot.
    this.active.lockedOut.push(teamId);
    this.active.buzzedBy = null;
    this.note('wrong', { team: teamId, name: team.name, text, source });

    if (this.everyoneLockedOut()) return this.revealAnswer('nobody got it');

    this.phase = 'open';
    this.active.secondsLeft = 0;
    this.touch();
    return { ok: true, fx: 'wrong', reopened: true };
  }

  /** Time ran out while a team held the clue. Same as a wrong answer. */
  timeUp() {
    if (this.phase !== 'answering' || !this.active?.buzzedBy) return { error: 'Nothing running.' };
    const teamId = this.active.buzzedBy;
    this.note('timeUp', { team: teamId, name: this.teamName(teamId) });
    const result = this.resolveAnswer(false, '(ran out of time)', 'clock');
    return { ...result, fx: 'timeup' };
  }

  revealAnswer(reason = 'revealed') {
    if (!this.active) return { error: 'No clue in play.' };
    this.phase = 'revealed';
    this.active.running = false;
    this.active.buzzedBy = null;
    this.note('revealed', { reason });
    this.touch();
    return { ok: true, fx: reason === 'correct' ? 'correct' : 'reveal' };
  }

  backToBoard() {
    if (this.phase !== 'revealed') return { error: 'Not showing an answer.' };
    this.active = null;
    this.phase = this.boardCleared() ? 'boardCleared' : 'board';
    this.touch();
    return { ok: true };
  }

  boardCleared() {
    return this.used.every((col) => col.every(Boolean));
  }

  cluesLeft() {
    return this.used.flat().filter((x) => !x).length;
  }

  /* ---------------------------------------------------------------- */
  /* Final Jeopardy                                                    */
  /* ---------------------------------------------------------------- */

  startFinal() {
    if (this.teams.length === 0) return { error: 'No teams.' };
    this.final = {
      wagers: {},        // teamId -> number
      answers: {},       // teamId -> string
      results: {},       // teamId -> { correct, source, reason }
      revealed: [],      // teamIds already shown, in order
      secondsLeft: this.settings.wagerSeconds,
      running: false,
      stage: 'intro',
    };
    this.active = null;
    this.phase = 'finalIntro';
    this.note('finalIntro', { category: FINAL.category });
    this.touch();
    return { ok: true, fx: 'final' };
  }

  openWagers() {
    if (!this.final) return { error: 'Final Jeopardy has not started.' };
    this.final.stage = 'wager';
    this.final.secondsLeft = this.settings.wagerSeconds;
    this.final.running = this.settings.wagerSeconds > 0;
    this.phase = 'finalWager';
    this.note('wagersOpen');
    this.touch();
    return { ok: true, fx: 'open' };
  }

  submitWager(teamId, amount) {
    if (this.phase !== 'finalWager') return { error: 'Wagers are not open.' };
    const team = this.team(teamId);
    if (!team) return { error: 'Unknown team.' };
    const n = Math.floor(Number(amount));
    if (!Number.isFinite(n) || n < 0) return { error: 'Enter a whole number, zero or more.' };
    // Capping at the team's score is what keeps every score at or above zero.
    if (n > team.score) return { error: `You cannot wager more than ${team.score}.` };
    this.final.wagers[teamId] = n;
    this.note('wager', { team: teamId, name: team.name });
    this.touch();
    return { ok: true, fx: 'lock' };
  }

  allWagersIn() {
    return this.teams.every((t) => this.final.wagers[t.id] !== undefined);
  }

  openFinalClue() {
    if (!this.final) return { error: 'Final Jeopardy has not started.' };
    // Anyone who never wagered has wagered nothing.
    for (const t of this.teams) {
      if (this.final.wagers[t.id] === undefined) this.final.wagers[t.id] = 0;
    }
    this.final.stage = 'clue';
    this.final.secondsLeft = this.settings.finalSeconds;
    this.final.running = this.settings.finalSeconds > 0;
    this.phase = 'finalClue';
    this.note('finalClue');
    this.touch();
    return { ok: true, fx: 'final' };
  }

  submitFinalAnswer(teamId, text) {
    if (this.phase !== 'finalClue') return { error: 'Not taking answers.' };
    if (!this.team(teamId)) return { error: 'Unknown team.' };
    this.final.answers[teamId] = String(text || '').slice(0, 200);
    this.note('finalAnswer', { team: teamId, name: this.teamName(teamId) });
    this.touch();
    return { ok: true, fx: 'lock' };
  }

  allAnswersIn() {
    return this.teams.every((t) => this.final.answers[t.id] !== undefined);
  }

  /** Record a judged verdict without applying it — the host reveals later. */
  recordFinalVerdict(teamId, verdict) {
    if (!this.final) return { error: 'No final round.' };
    this.final.results[teamId] = verdict;
    this.touch();
    return { ok: true };
  }

  closeFinalWriting() {
    if (!this.final) return { error: 'No final round.' };
    for (const t of this.teams) {
      if (this.final.answers[t.id] === undefined) this.final.answers[t.id] = '';
    }
    this.final.running = false;
    this.final.stage = 'reveal';
    this.phase = 'finalReveal';
    this.note('finalWritingClosed');
    this.touch();
    return { ok: true, fx: 'reveal' };
  }

  /**
   * Reveal one team's Final Jeopardy result and apply it to their score.
   * Lowest score first is the convention, and it is also the most dramatic.
   */
  revealFinalTeam(teamId, overrideCorrect = null) {
    if (this.phase !== 'finalReveal') return { error: 'Not revealing yet.' };
    const team = this.team(teamId);
    if (!team) return { error: 'Unknown team.' };
    if (this.final.revealed.includes(teamId)) return { error: 'Already revealed.' };

    const verdict = this.final.results[teamId] || { correct: false, source: 'offline', reason: '' };
    const correct = overrideCorrect === null ? verdict.correct : Boolean(overrideCorrect);
    const wager = this.final.wagers[teamId] ?? 0;

    team.score += correct ? wager : -wager;
    this.final.results[teamId] = { ...verdict, correct, applied: true };
    this.final.revealed.push(teamId);
    this.note(correct ? 'finalCorrect' : 'finalWrong', {
      team: teamId, name: team.name, wager, text: this.final.answers[teamId] || '',
    });

    if (this.final.revealed.length === this.teams.length) this.finish();
    this.touch();
    return { ok: true, fx: correct ? 'correct' : 'wrong' };
  }

  /** The order the host should reveal in: poorest first. */
  revealOrder() {
    return [...this.teams]
      .sort((a, b) => a.score - b.score)
      .map((t) => t.id)
      .filter((id) => !this.final.revealed.includes(id));
  }

  finish() {
    this.phase = 'gameOver';
    const top = Math.max(...this.teams.map((t) => t.score));
    const winners = this.teams.filter((t) => t.score === top);
    this.winner = winners.length === 1 ? winners[0].id : 'tie';
    this.note('gameOver', { winner: this.winner });
    this.touch();
  }

  /* ---------------------------------------------------------------- */
  /* clock                                                             */
  /* ---------------------------------------------------------------- */

  /** Called once a second by the server. Returns true if anything moved. */
  tick() {
    const stage = this.phase === 'answering' ? this.active
      : (this.phase === 'finalWager' || this.phase === 'finalClue') ? this.final
        : null;
    if (!stage || !stage.running) return false;

    stage.secondsLeft -= 1;
    if (stage.secondsLeft > 0) { this.touch(); return true; }

    stage.secondsLeft = 0;
    stage.running = false;
    if (this.phase === 'answering') this.timeUp();
    else if (this.phase === 'finalWager') this.openFinalClue();
    else if (this.phase === 'finalClue') this.closeFinalWriting();
    this.touch();
    return true;
  }

  adjustScore(teamId, delta) {
    const team = this.team(teamId);
    if (!team) return { error: 'Unknown team.' };
    team.score = Math.max(0, team.score + delta);
    this.note('adjust', { team: teamId, name: team.name, delta });
    this.touch();
    return { ok: true };
  }

  setPicker(teamId) {
    if (!this.team(teamId)) return { error: 'Unknown team.' };
    this.picker = teamId;
    this.touch();
    return { ok: true };
  }

  /* ---------------------------------------------------------------- */
  /* serialisation                                                     */
  /* ---------------------------------------------------------------- */

  /**
   * @param {'host'|'board'|string} audience — 'host' is the teacher's laptop and
   *   sees everything. 'board' is the projector. Anything else is a team id.
   *   Only the host is ever sent an answer that is not yet revealed.
   */
  snapshot(audience = 'board') {
    const isHost = audience === 'host';
    const found = this.active ? findClue(this.active.categoryIndex, this.active.clueIndex) : null;
    const answerIsPublic = this.phase === 'revealed';

    let clue = null;
    if (this.active && found) {
      clue = {
        category: found.category.name,
        value: this.active.value,
        text: found.clue.text,
        buzzedBy: this.active.buzzedBy,
        lockedOut: this.active.lockedOut,
        secondsLeft: this.active.secondsLeft,
        running: this.active.running,
        correctBy: this.active.correctBy,
        answer: (isHost || answerIsPublic) ? found.clue.answer : null,
        // The teaching note is for the teacher to say out loud, never a screen.
        note: isHost ? (found.clue.note || '') : null,
      };
    }

    let final = null;
    if (this.final) {
      const showAnswer = isHost || this.phase === 'finalReveal' || this.phase === 'gameOver';
      final = {
        stage: this.final.stage,
        category: FINAL.category,
        // The clue itself stays hidden until wagers are locked and it is opened.
        text: (isHost || ['finalClue', 'finalReveal', 'gameOver'].includes(this.phase))
          ? FINAL.text : null,
        answer: showAnswer ? FINAL.answer : null,
        note: isHost ? FINAL.note : null,
        secondsLeft: this.final.secondsLeft,
        running: this.final.running,
        revealed: this.final.revealed,
        revealOrder: this.phase === 'finalReveal' ? this.revealOrder() : [],
        // Who has committed, for the host's progress list. Amounts and text go
        // only to the host and to the team that wrote them.
        submitted: this.teams.map((t) => ({
          id: t.id,
          wagered: this.final.wagers[t.id] !== undefined,
          answered: this.final.answers[t.id] !== undefined,
        })),
        results: (isHost || this.phase === 'gameOver') ? this.final.results : {},
        detail: this.teams.reduce((acc, t) => {
          const mine = isHost || audience === t.id
            || this.final.revealed.includes(t.id) || this.phase === 'gameOver';
          if (mine) {
            acc[t.id] = {
              wager: this.final.wagers[t.id] ?? null,
              answer: this.final.answers[t.id] ?? null,
            };
          }
          return acc;
        }, {}),
      };
    }

    return {
      version: this.version,
      phase: this.phase,
      teams: this.teams.map((t) => ({ id: t.id, name: t.name, score: t.score })),
      picker: this.picker,
      you: audience,
      categories: CATEGORIES.map((c, ci) => ({
        name: c.name,
        blurb: isHost ? c.blurb : null,
        clues: c.clues.map((cl, li) => ({
          value: cl.value,
          used: this.used[ci][li],
          // The host's laptop lists every answer so the teacher can see what is
          // coming; the projector never gets them.
          answer: isHost ? cl.answer : null,
        })),
      })),
      clue,
      final,
      cluesLeft: this.cluesLeft(),
      lastEvent: this.lastEvent,
      log: isHost ? this.log.slice(0, 12) : [],
      winner: this.winner,
      settings: { ...this.settings },
    };
  }
}
