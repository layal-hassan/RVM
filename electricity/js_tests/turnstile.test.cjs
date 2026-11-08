const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const form = {};
  const message = { hidden: true };
  const loading = { hidden: false };
  const unavailable = { hidden: true };
  const states = { '[data-turnstile-error]': message, '[data-turnstile-loading]': loading, '[data-turnstile-unavailable]': unavailable };
  const node = {
    dataset: { sitekey: 'public-key' }, visible: true,
    closest: selector => selector === 'form' ? form : { querySelector: name => states[name] },
    getClientRects() { return this.visible ? [{}] : []; },
    scrollIntoView() {},
  };
  const listeners = {};
  let observer;
  let script;
  let timeout;
  const window = {
    addEventListener(type, fn) { listeners[type] = fn; },
    setTimeout(fn) { timeout = fn; return 1; },
    clearTimeout() { timeout = null; },
  };
  const document = {
    querySelectorAll: () => [node], body: {},
    addEventListener(type, fn, capture) { assert.equal(capture, true); listeners[type] = fn; },
    createElement: () => (script = {}), head: { append() {} },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/electricity/js/turnstile.js'), 'utf8'), {
    window, document, MutationObserver: class {
      constructor(fn) { observer = fn; }
      observe() {}
    },
  });
  return { window, node, form, message, loading, unavailable, listeners, get script() { return script; }, observe: () => observer(), expire: () => timeout?.() };
}

test('blocks submission before AJAX handlers while verification is unavailable', () => {
  const env = setup();
  let prevented = false, stopped = false;
  env.listeners.submit({ target: env.form, preventDefault() { prevented = true; }, stopImmediatePropagation() { stopped = true; } });
  assert.ok(prevented && stopped);
  assert.equal(env.message.hidden, false);
});

test('renders a hidden review widget when visible, accepts token, and resets for retry', () => {
  const env = setup();
  env.node.visible = false;
  let rendered = 0, reset = 0, options;
  env.window.turnstile = {
    render(node, config) { rendered++; options = config; return 'widget-id'; },
    getResponse: () => 'verified-token',
    reset(id) { assert.equal(id, 'widget-id'); reset++; },
  };
  env.window.onSubmissionTurnstileLoad();
  assert.equal(rendered, 0);
  env.node.visible = true;
  env.observe();
  env.observe();
  assert.equal(rendered, 1);
  assert.equal(env.loading.hidden, true);
  assert.equal(env.unavailable.hidden, true);
  assert.equal(options.sitekey, 'public-key');
  env.listeners.submit({ target: env.form, preventDefault() { assert.fail('Verified form was blocked'); } });
  options['expired-callback']();
  assert.equal(env.message.hidden, false);
  options.callback();
  assert.equal(env.message.hidden, true);
  env.window.resetSubmissionVerification(env.form);
  assert.equal(reset, 1);
  env.listeners.pageshow({ persisted: true });
  assert.equal(reset, 2);
});

test('shows retry message if the Cloudflare script fails to load', () => {
  const env = setup();
  env.script.onerror();
  assert.equal(env.unavailable.hidden, false);
  assert.equal(env.loading.hidden, true);
});

test('shows a loading failure when the Cloudflare script never responds', () => {
  const env = setup();
  env.expire();
  assert.equal(env.unavailable.hidden, false);
  assert.equal(env.loading.hidden, true);
});
