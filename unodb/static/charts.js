// Charts on the player page, drawn with uPlot from /player/<name>/charts.json.
// All numbers are computed on the server; this only draws them.
"use strict";

(function () {
  const movingEl = document.getElementById("moving-chart");
  const histogramEl = document.getElementById("histogram-chart");
  if (!movingEl || typeof uPlot === "undefined") return;

  const HEIGHT = 260;
  let data = null;
  let plots = [];

  // colors from Pico, so the charts follow light/dark mode
  function colors() {
    const style = getComputedStyle(document.body);
    const get = (name) => style.getPropertyValue(name).trim();
    return {
      series: get("--pico-primary"),
      text: get("--pico-muted-color"),
      grid: get("--pico-muted-border-color"),
    };
  }

  function axis(c, extra) {
    return Object.assign(
      {
        stroke: c.text,
        grid: { stroke: c.grid, width: 1 },
        ticks: { stroke: c.grid, width: 1 },
      },
      extra,
    );
  }

  function movingChart(c) {
    const m = data.moving;
    document.getElementById("window").textContent = m.window;
    return new uPlot(
      {
        width: movingEl.clientWidth,
        height: HEIGHT,
        scales: { x: { time: false } },
        series: [
          {
            label: "Game",
            value: (u, v) => (v == null ? "–" : `${v} (${m.date[v - 1]})`),
          },
          {
            label: "Points per game",
            stroke: c.series,
            width: 2,
            points: { show: false },
            value: (u, v) => (v == null ? "–" : v.toFixed(1)),
          },
        ],
        axes: [axis(c, { label: "Game" }), axis(c, { size: 50 })],
      },
      [m.game, m.average],
      movingEl,
    );
  }

  function histogramChart(c) {
    const h = data.histogram;
    const index = h.labels.map((_, i) => i);
    const narrow = histogramEl.clientWidth < 600;
    return new uPlot(
      {
        width: histogramEl.clientWidth,
        height: HEIGHT,
        scales: { x: { time: false, range: [-0.5, h.labels.length - 0.5] } },
        series: [
          {
            label: "Points",
            value: (u, v) => (v == null ? "–" : h.labels[v]),
          },
          {
            label: "Games",
            fill: c.series,
            stroke: c.series,
            width: 0,
            points: { show: false },
            paths: uPlot.paths.bars({ size: [0.7, 24], radius: 0.2 }),
          },
        ],
        axes: [
          axis(c, {
            label: "Points in the game",
            splits: () => index,
            values: (u, splits) =>
              splits.map((i) => (narrow && i % 2 ? "" : h.labels[i])),
          }),
          axis(c, { size: 50 }),
        ],
      },
      [index, h.counts],
      histogramEl,
    );
  }

  function draw() {
    plots.forEach((p) => p.destroy());
    const c = colors();
    plots = [movingChart(c), histogramChart(c)];
  }

  fetch(movingEl.dataset.src)
    .then((response) => response.json())
    .then((json) => {
      data = json;
      draw();
      new ResizeObserver(() => {
        plots[0].setSize({ width: movingEl.clientWidth, height: HEIGHT });
        plots[1].setSize({ width: histogramEl.clientWidth, height: HEIGHT });
      }).observe(movingEl);
      window
        .matchMedia("(prefers-color-scheme: dark)")
        .addEventListener("change", draw);
    });
})();
