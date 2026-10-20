document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".pp-main");
  if (!root) return;
  const number = (value) => Number.parseFloat(String(value).replace(",", ".")) || 0;
  const laborRate = number(root.dataset.labor);
  const transport = number(root.dataset.transport);
  const rotPercent = number(root.dataset.rot);
  const currency = root.dataset.currency || "SEK";
  let hours = 3;
  const format = (value) => new Intl.NumberFormat(document.documentElement.lang || "en", { maximumFractionDigits: 1 }).format(value) + " " + currency;
  const update = () => {
    const applyRot = document.querySelector("#pp-rot").checked;
    const labour = hours * laborRate;
    const discount = applyRot ? labour * rotPercent / 100 : 0;
    document.querySelector("#pp-hours").textContent = hours;
    document.querySelector("#pp-result-hours").textContent = hours;
    document.querySelector("#pp-labour").textContent = format(labour);
    document.querySelector("#pp-transport").textContent = format(transport);
    document.querySelector("#pp-discount").textContent = discount ? "−" + format(discount) : format(0);
    document.querySelector("#pp-total").textContent = format(labour + transport - discount);
  };
  document.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", () => {
    hours = Math.min(24, Math.max(1, hours + Number(button.dataset.step)));
    update();
  }));
  document.querySelector("#pp-rot").addEventListener("change", update);
  document.querySelectorAll("input[name='property']").forEach((input) => input.addEventListener("change", () => {
    const rot = document.querySelector("#pp-rot");
    rot.checked = input.value === "private";
    rot.disabled = input.value === "business";
    update();
  }));
  update();
});
