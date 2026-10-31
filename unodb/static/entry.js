// Game entry form: the winner has no points, so choosing a winner empties and
// disables that player's points field (and enables the others again). The
// server checks the same rules; this only makes a wrong entry impossible.
function syncWinner(form) {
  for (const radio of form.querySelectorAll("input[data-winner]")) {
    const row = radio.closest("tr");
    const points = row && row.querySelector("input[type=number]");
    if (!points) continue;
    if (radio.checked) points.value = "";
    points.disabled = radio.checked;
  }
}

document.addEventListener("change", (event) => {
  const form = event.target.closest && event.target.closest("[data-game-form]");
  if (form && event.target.matches("input[data-winner]")) syncWinner(form);
});

function initGameForms(root) {
  for (const form of root.querySelectorAll("[data-game-form]")) syncWinner(form);
}
document.addEventListener("DOMContentLoaded", () => initGameForms(document));
document.addEventListener("htmx:afterSwap", (event) => initGameForms(event.target));
