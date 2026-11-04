const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");
const script = readFileSync(join(__dirname, "../static/electricity/js/consultation-start.js"), "utf8");

function setup(configs, readyState = "complete", navigation = {}) {
    const stepLabel = {dataset: {customerBusiness: "Project details", customerPrivate: "Work details"}};
    const popups = configs.map(({name, value = null, flags = []}) => {
        const events = {}, rootEvents = {}, formEvents = {};
        const attributes = new Set(flags);
        let submissions = 0;
        const form = {noValidate: false, addEventListener: (n, fn) => formEvents[n] = fn, requestSubmit() {submissions++;}};
        const input = {value, checked: Boolean(value), focus() {}, closest: () => ({querySelector: () => ({textContent: input.value})})};
        const selected = () => input.value ? input : null;
        const summaryLabel = {};
        const change = {addEventListener: (n, fn) => events.reopen = fn, focus() {}};
        const summary = {hidden: true, querySelector: s => s.includes("label") ? summaryLabel : change};
        const fieldset = {
            dataset: {choiceName: name},
            querySelector: s => {assert(s.includes(`name="${name}"`) || s === "input"); return s.includes(":checked") ? selected() : input;},
            addEventListener: (n, fn) => events[n] = fn,
        };
        const dismiss = {addEventListener: (n, fn) => events.dismiss = fn};
        const dialog = {
            open: false,
            showModal() {this.open = true;}, close() {this.open = false; events.close();},
            querySelector: s => s.includes("dismiss") ? dismiss : {append(node) {assert.equal(node, fieldset);}},
            addEventListener: (n, fn) => events[n] = fn,
        };
        const root = {
            dataset: {},
            querySelector: s => s.includes("dialog") ? dialog : s.includes("fieldset") ? fieldset : s.includes("summary") ? summary : null,
            addEventListener: (n, fn) => rootEvents[n] = fn,
            hasAttribute: n => attributes.has(n), closest: () => form,
            dispatchEvent: e => {rootEvents[e.type]?.(e);},
        };
        return {events, rootEvents, formEvents, root, dialog, input, form, summary, summaryLabel, submissions: () => submissions};
    });
    runInNewContext(script, {
        URL,
        window: {location: {href: navigation.current || "https://rwmel.se/book-electrician/step-2/"}},
        CustomEvent: class { constructor(type, options) {this.type = type; this.detail = options.detail;} },
        document: {readyState, referrer: navigation.referrer || "", addEventListener() {}, activeElement: {focus() {}}, querySelectorAll: s => s === "[data-customer-popup]" ? popups.map(p => p.root) : [stepLabel]},
    });
    return {popups, stepLabel};
}
for (const name of ["contact_type", "customer_type", "account_type"]) {
    test(`${name}: starts with popup, requires a choice, and supports changing it`, () => {
        const {popups: [p]} = setup([{name}]);
        assert(p.dialog.open);
        let prevented = false;
        p.events.cancel({preventDefault() {prevented = true;}});
        assert(prevented);
        p.input.value = "business";
        p.events.change({target: {name}});
        assert(!p.dialog.open && !p.summary.hidden);
        assert.equal(p.summaryLabel.textContent, "business");
        p.events.reopen();
        p.input.value = "private";
        p.events.change({target: {name}});
        assert.equal(p.summaryLabel.textContent, "private");
    });
}
test("separate popup instances on the same page do not share choices", () => {
    const {popups: [quote, booking]} = setup([
        {name: "customer_type", flags: ["data-popup-manual"]},
        {name: "customer_type", value: "business", flags: ["data-popup-manual"]},
    ]);
    assert(!quote.dialog.open && !booking.dialog.open);
    quote.rootEvents["customer-type-open"]();
    quote.input.value = "private";
    quote.events.change({target: {name: "customer_type"}});
    assert.equal(quote.summaryLabel.textContent, "private");
    assert.equal(booking.summaryLabel.textContent, "business");
});
test("saved choice still opens the popup and same-choice clicks close it", () => {
    const {popups: [p]} = setup([{name: "customer_type", value: "business"}]);
    assert(p.dialog.open, "a previous Business draft must not skip the entry popup");
    p.events.click({target: {matches: () => false}});
    assert(p.dialog.open, "label click must wait for native radio selection");
    p.events.click({target: {matches: () => true, checked: true}});
    assert(!p.dialog.open);
});
test("homepage selection posts directly into booking", () => {
    const {popups: [p]} = setup([{name: "customer_type", flags: ["data-popup-manual", "data-submit-on-choice"]}]);
    p.rootEvents["customer-type-open"]();
    p.input.value = "private";
    p.events.change({target: {name: "customer_type"}});
    assert.equal(p.submissions(), 1);
});
test("Jour only submits immediately for Private; Business stays in its agreement form", () => {
    for (const value of ["private", "business"]) {
        const {popups: [p]} = setup([{name: "customer_type", flags: ["data-submit-on-private"]}]);
        p.input.value = value;
        p.events.change({target: {name: "customer_type"}});
        assert.equal(p.submissions(), value === "private" ? 1 : 0);
        assert.equal(p.form.noValidate, value === "private");
    }
});
test("quick quote waits for interaction and allows returning to browsing", () => {
    const {popups: [p]} = setup([{name: "customer_type", flags: ["data-popup-manual", "data-popup-on-focus"]}]);
    assert(!p.dialog.open);
    p.formEvents.focusin();
    assert(p.dialog.open);
    p.events.dismiss();
    assert(!p.dialog.open);
});
test("business choice updates the booking path labels", () => {
    const {stepLabel} = setup([{name: "customer_type", value: "business"}]);
    assert.equal(stepLabel.textContent, "Project details");
});

for (const name of ["contact_type", "customer_type", "account_type"]) {
    test(`${name}: saved booking choices do not bypass the entry question`, () => {
        const {popups: [p]} = setup([{name, value: "business"}]);
        assert(p.dialog.open);
        assert.equal(p.summaryLabel.textContent, "business");
    });
}
test("a choice just made in the entry popup is not asked twice", () => {
    const {popups: [p]} = setup([{name: "customer_type", value: "private", flags: ["data-popup-confirmed"]}]);
    assert(!p.dialog.open);
    p.events.reopen();
    assert(p.dialog.open);
});
test("confirmation cannot hide the popup when no customer type is selected", () => {
    const {popups: [p]} = setup([{name: "customer_type", flags: ["data-popup-confirmed"]}]);
    assert(p.dialog.open);
});

test("popup opens while the document is still loading", () => {
    const {popups: [p]} = setup([{name: "customer_type", value: "business"}], "loading");
    assert(p.dialog.open, "opening must not wait for DOMContentLoaded or third-party scripts");
});

test("returning from a later step keeps the existing choice without reopening", () => {
    for (const [flow, entry] of [["book-electrician", 2], ["consultation-booking", 1], ["service-booking", 1], ["on-call-booking", 1], ["request-a-quote", 1]]) {
        const {popups: [p]} = setup([{name: "customer_type", value: "private"}], "complete", {
            current: `https://rwmel.se/${flow}/step-${entry}/`,
            referrer: `https://rwmel.se/${flow}/step-${entry + 1}/`,
        });
        assert(!p.dialog.open, flow);
        p.events.reopen();
        assert(p.dialog.open, "Change must still open the popup");
    }
});
test("new booking entry from another page or flow still asks for customer type", () => {
    for (const referrer of ["https://rwmel.se/services/", "https://rwmel.se/consultation-booking/step-3/", "https://example.com/book-electrician/step-3/"]) {
        const {popups: [p]} = setup([{name: "customer_type", value: "business"}], "complete", {referrer});
        assert(p.dialog.open, referrer);
    }
});
test("returning without a saved choice still opens the popup", () => {
    const {popups: [p]} = setup([{name: "customer_type"}], "complete", {referrer: "https://rwmel.se/book-electrician/step-3/"});
    assert(p.dialog.open);
});
