// Injectable readers are a unit-test seam only. Production runners always pass readWindowsMemory.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const execute = promisify(execFile);
export async function readWindowsMemory() {
  const { stdout } = await execute('powershell', ['-NoProfile', '-Command', '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'], { windowsHide: true, timeout: 3000 });
  if (!stdout.trim()) throw Error('RAM measurement empty');
  const gib = Number(stdout.trim()) / 1048576;
  if (!Number.isFinite(gib) || gib < 0) throw Error('RAM measurement invalid');
  return gib;
}
export class ResourceBlocked extends Error {
  constructor(reason) { super(`BLOCKED: ${reason}`); this.name = 'ResourceBlocked'; }
}
export class QaResourceGuard {
  constructor({ read, wait = ms => new Promise(r => setTimeout(r, ms)), every = (fn, ms) => setInterval(fn, ms), cancel = clearInterval, now = Date.now, onSample = () => {}, onBlock = () => {}, maximumMs = 180000 }) {
    Object.assign(this, { read, wait, every, cancel, now, onSample, onBlock, maximumMs });
    this.ready = false; this.started = now(); this.blocked = null; this.browser = null; this.closed = new WeakSet(); this.busy = false;
    this.aborted = new Promise((_, reject) => { this.abort = reject; });
    this.aborted.catch(() => {});
  }
  assertAllowed() { if (this.blocked) throw this.blocked; }
  async closeOwned() {
    const owned = this.browser;
    if (!owned || this.closed.has(owned)) return;
    this.closed.add(owned);
    // Close only the instance returned by this guard's launch callback. No OS process enumeration/kill.
    await Promise.race([Promise.resolve().then(() => owned.close()).catch(() => {}), new Promise(r => { const t=setTimeout(r,3000); t.unref?.(); })]);
  }
  block(reason) {
    if (!this.blocked) {
      this.blocked = new ResourceBlocked(reason);
      try { this.onBlock(this.blocked); } catch { /* evidence failure must not prevent cancellation */ }
      this.abort(this.blocked);
      void this.closeOwned();
    }
    return this.blocked;
  }
  async sample(minimum, phase) {
    this.assertAllowed();
    try {
      const gib = await this.read();
      if (!Number.isFinite(gib) || gib < 0) throw Error('RAM measurement invalid');
      this.onSample({ at_ms: this.now() - this.started, gib, phase });
      if (gib < minimum) throw this.block(`${phase}: available ${gib.toFixed(3)} GiB < ${minimum} GiB`);
      if (this.now() - this.started > this.maximumMs) throw this.block('180-second execution bound');
      this.assertAllowed(); return gib;
    } catch (error) {
      if (error instanceof ResourceBlocked) throw error;
      throw this.block(`RAM measurement/evidence failure: ${error.message}`);
    }
  }
  async preflight() { this.ready=false; for (let i=0;i<3;i++) { await this.sample(3,'preflight'); if(i<2) await this.wait(10000); } this.ready=true; }
  async checkpoint() { await this.sample(2.5,'runtime'); }
  start() {
    if (this.timer) return;
    this.timer = this.every(async () => {
      if (this.busy || this.blocked) return;
      this.busy = true; try { await this.checkpoint(); } catch { /* block already closes owned browser */ } finally { this.busy=false; }
    },1000);
  }
  async perform(action) {
    this.assertAllowed();
    return Promise.race([Promise.resolve().then(() => { this.assertAllowed(); return action(); }), this.aborted]);
  }
  async launch(createOwnedBrowser) {
    this.assertAllowed(); if(!this.ready) throw this.block('Three passing preflight samples are required before launch');
    await this.sample(3,'immediately-before-launch');
    this.start(); // monitor also covers launch time and closes a late-resolving owned browser
    return this.perform(async () => {
      const owned = await createOwnedBrowser(); this.browser=owned;
      if (this.blocked) { await this.closeOwned(); throw this.blocked; }
      return owned;
    });
  }
  async dispose() { if(this.timer) this.cancel(this.timer); this.timer=null; await this.closeOwned(); }
}
