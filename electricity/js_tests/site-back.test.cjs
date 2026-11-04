const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");
const script = readFileSync(join(__dirname, "../static/electricity/js/site-back.js"), "utf8");

function page({ path = "/consultation-booking/step-1/", referrer = "", saved = null, blocked = false } = {}) {
    let stored = saved;
    const events = {};
    const link = { href: "/services/", setAttribute(name, value) { this[name] = value; } };
    const document = {
        referrer, readyState: "complete",
        querySelectorAll: selector => selector === "a[data-site-back]" ? [link] : [],
    };
    runInNewContext(script, {
        URL, document,
        window: { location: { href: "https://rwmel.se" + path }, addEventListener: (name, fn) => events[name] = fn },
        sessionStorage: {
            getItem() { if (blocked) throw Error("blocked"); return stored; },
            setItem(key, value) { if (blocked) throw Error("blocked"); stored = value; },
        },
    });
    return { link, saved: stored, events };
}

test("entry Back returns to the page that opened the flow", () => {
    assert.equal(page({ referrer: "https://rwmel.se/pricing/" }).link.href, "/pricing/");
});
test("reloads and POST validation keep the previous distinct page", () => {
    const first = page({ referrer: "https://rwmel.se/services/?category=lighting" });
    const reload = page({ referrer: "https://rwmel.se/consultation-booking/step-1/", saved: first.saved });
    assert.equal(reload.link.href, "/services/?category=lighting");
});
test("navigation works without a referrer using the current tab", () => {
    const first = page({ path: "/pricing/" });
    assert.equal(page({ saved: first.saved }).link.href, "/pricing/");
});
test("direct entry keeps the ordinary fallback link", () => {
    assert.equal(page().link.href, "/services/");
});
test("external or malformed stored destinations cannot redirect off site", () => {
    for (const saved of ["bad json", JSON.stringify({current: "https://example.org/", previous: "javascript:alert(1)"})]) {
        assert.equal(page({referrer: "https://example.org/", saved}).link.href, "/services/");
    }
});
test("referrer navigation still works if session storage is blocked", () => {
    assert.equal(page({ referrer: "https://rwmel.se/contact/", blocked: true }).link.href, "/contact/");
});
test("browser cache restoration retains the original previous page", () => {
    const result = page({referrer: "https://rwmel.se/pricing/"});
    result.events.pageshow();
    assert.equal(result.link.href, "/pricing/");
});
