// Charts on the player and compare pages, drawn with uPlot from JSON.
// All numbers are computed on the server; this only draws them.
// Runs on every page load and again after htmx swapped in new content.
"use strict";

(function () {
  const HEIGHT = 260;
  const SMALL_HEIGHT = 160;
  let plots = [];
  let resizers = [];

  // colors from CSS (Pico and style.css), so charts follow light/dark mode
  function colors() {
    const style = getComputedStyle(document.body);
    const get = (name) => style.getPropertyValue(name).trim();
    const series = [];
    for (let i = 1; i <= 6; i++) series.push(get(`--series-${i}`));
    return {
      primary: get("--pico-primary"),
      series,
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

  const utc = (ts) => uPlot.tzDate(new Date(ts * 1e3), "Etc/UTC");
  const day = uPlot.fmtDate("{YYYY}-{MM}-{DD}");

  // x axis + legend entry for game numbers or dates
  function xSeries(byDate, dates) {
    if (byDate) {
      return { label: "Date", value: (u, v) => (v == null ? "–" : day(utc(v))) };
    }
    return {
      label: "Game",
      value: (u, v) =>
        v == null ? "–" : dates && dates.length ? `${v} (${dates[v - 1]})` : v,
    };
  }

  // null in the data: no game at that point (skipped, uPlot wants
  // undefined for that), except at a break: a long pause, left as a gap
  function withBreaks(values, breaks) {
    const gaps = new Set(breaks);
    return values.map((v, i) => (v === null && !gaps.has(i) ? undefined : v));
  }

  function lineChart(el, c, byDate, dates, x, lines) {
    return new uPlot(
      {
        width: el.clientWidth,
        height: HEIGHT,
        tzDate: utc,
        scales: { x: { time: byDate } },
        series: [
          xSeries(byDate, dates),
          ...lines.map((line) => ({
            label: line.label,
            stroke: line.color,
            width: 2,
            points: { show: false },
            value: (u, v) => (v == null ? "–" : v.toFixed(1)),
          })),
        ],
        axes: [
          axis(c, byDate ? {} : { label: "Game" }),
          axis(c, { size: 50 }),
        ],
      },
      [x, ...lines.map((line) => line.values)],
      el,
    );
  }

  function barChart(el, c, labels, values, color, opts) {
    const index = labels.map((_, i) => i);
    // label every step-th bin so the labels don't run into each other
    const step = Math.max(1, Math.ceil((labels.length * 55) / el.clientWidth));
    return new uPlot(
      {
        width: el.clientWidth,
        height: opts.height,
        legend: { show: opts.legend },
        scales: {
          x: { time: false, range: [-0.5, labels.length - 0.5] },
          y: opts.yMax ? { range: [0, opts.yMax] } : {},
        },
        series: [
          { label: "Points", value: (u, v) => (v == null ? "–" : labels[v]) },
          {
            label: opts.label,
            fill: color,
            stroke: color,
            width: 0,
            points: { show: false },
            paths: uPlot.paths.bars({ size: [0.7, 24], radius: 0.2 }),
            value: opts.format,
          },
        ],
        axes: [
          axis(c, {
            label: opts.xLabel,
            splits: () => index,
            values: (u, splits) =>
              splits.map((i) => (i % step ? "" : labels[i])),
          }),
          axis(c, { size: 50 }),
        ],
      },
      [index, values],
      el,
    );
  }

  function playerCharts(el, data) {
    const c = colors();
    const m = data.moving;
    document.getElementById("window").textContent = m.window;
    const hist = document.getElementById("histogram-chart");
    return [
      [
        el,
        lineChart(el, c, m.by_date, m.date, m.x, [
          {
            label: "Points per game",
            color: c.primary,
            values: withBreaks(m.average, m.breaks),
          },
        ]),
      ],
      [
        hist,
        barChart(hist, c, data.histogram.labels, data.histogram.counts, c.primary, {
          height: HEIGHT,
          legend: true,
          label: "Games",
          xLabel: "Points in the game",
        }),
      ],
    ];
  }

  function compareCharts(el, data) {
    const c = colors();
    document.getElementById("window").textContent = data.window;
    const lines = data.names.map((name, i) => ({
      label: name,
      color: c.series[i],
      values: withBreaks(data.series[i], data.breaks[i]),
    }));
    const result = [[el, lineChart(el, c, data.by_date, null, data.x, lines)]];

    const h = data.histogram;
    const yMax = Math.max(1, ...h.percent.flat());
    document.querySelectorAll("[data-histogram]").forEach((small) => {
      const i = Number(small.dataset.histogram);
      result.push([
        small,
        barChart(small, c, h.labels, h.percent[i], c.series[i], {
          height: SMALL_HEIGHT,
          legend: false,
          label: "Share of games",
          yMax,
          format: (u, v) => (v == null ? "–" : `${v}%`),
        }),
      ]);
    });
    return result;
  }

  function clear() {
    plots.forEach(([, p]) => p.destroy());
    resizers.forEach((r) => r.disconnect());
    plots = [];
    resizers = [];
  }

  function init() {
    clear();
    const player = document.getElementById("moving-chart");
    const compare = document.getElementById("compare-chart");
    const el = player || compare;
    if (!el || typeof uPlot === "undefined") return;

    fetch(el.dataset.src)
      .then((response) => response.json())
      .then((data) => {
        if (!el.isConnected) return; // page changed in the meantime
        clear();
        plots = player ? playerCharts(el, data) : compareCharts(el, data);
        const observer = new ResizeObserver(() =>
          plots.forEach(([target, p]) =>
            p.setSize({ width: target.clientWidth, height: p.height }),
          ),
        );
        observer.observe(el);
        resizers.push(observer);
      });
  }

  init();
  document.addEventListener("htmx:afterSettle", init);
  document.addEventListener("htmx:historyRestore", init);
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", init);
})();
