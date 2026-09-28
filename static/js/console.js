(function () {
  var root = document.getElementById("console-root");
  var stateSel = document.getElementById("filter-state");
  var sectorSel = document.getElementById("filter-sector");
  var query = document.getElementById("filter-q");
  var cache = null;
  var statesReady = false;

  var shortName = {
    "Uttar Pradesh": "U.P.",
    "Madhya Pradesh": "M.P.",
    "Andhra Pradesh": "A.P.",
    "Tamil Nadu": "T.N.",
    "West Bengal": "W.B."
  };

  function hi() { return document.documentElement.dataset.lang === "hi"; }
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch];
    });
  }
  function signalLabel(signal) {
    if (!hi()) return signal;
    return {Hotspot: "हॉटस्पॉट", "Under-heard": "कम सुनी गई", Priority: "प्राथमिकता", Watch: "नज़र में"}[signal] || signal;
  }
  function heat(priority) {
    var t = Math.min(1, Math.max(0, (priority - 42) / 36));
    var a = t < 0.5 ? [239, 230, 212] : [13, 106, 86];
    var b = t < 0.5 ? [13, 106, 86] : [184, 67, 33];
    var u = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
    var c = a.map(function (v, i) { return Math.round(v + (b[i] - v) * u); });
    return {bg: "rgb(" + c.join(",") + ")", fg: t > 0.35 ? "#f6f1e6" : "#1c1915"};
  }

  function load() {
    var params = new URLSearchParams();
    if (stateSel.value) params.set("state", stateSel.value);
    if (sectorSel.value) params.set("sector", sectorSel.value);
    if (query.value.trim()) params.set("q", query.value.trim());
    history.replaceState(null, "", params.toString() ? "?" + params.toString() : location.pathname);
    fetch("/api/console?" + params.toString()).then(function (res) { return res.json(); }).then(function (data) {
      cache = data;
      if (!statesReady) {
        data.states.slice().sort(function (a, b) { return a.state.localeCompare(b.state); }).forEach(function (row) {
          var opt = document.createElement("option");
          opt.value = row.state;
          opt.textContent = row.state;
          stateSel.appendChild(opt);
        });
        var initial = new URLSearchParams(location.search);
        if (initial.get("state")) stateSel.value = initial.get("state");
        if (initial.get("sector")) sectorSel.value = initial.get("sector");
        if (initial.get("q")) query.value = initial.get("q");
        statesReady = true;
        if (initial.get("state") || initial.get("sector") || initial.get("q")) {
          load();
          return;
        }
      }
      render(data);
    }).catch(function () {
      root.innerHTML = "<p>The ledger could not be read. Refresh the page.</p>";
    });
  }

  function render(data) {
    var pulse = data.pulse;
    var maxReq = Math.max.apply(null, data.states.map(function (s) { return s.requests; }).concat([1]));
    var atlas = data.states.map(function (row) {
      var color = heat(row.priority);
      var size = Math.max(58, Math.min(96, 52 + Math.sqrt(row.requests / maxReq) * 48));
      var selected = stateSel.value === row.state ? "outline:3px solid #1c1915;outline-offset:3px;" : "";
      return "<button class='bubble' data-state='" + esc(row.state) + "' style='left:" + row.x + "%;top:" + row.y +
        "%;width:" + size + "px;height:" + size + "px;background:" + color.bg + ";color:" + color.fg + ";" + selected + "' title='" +
        esc(row.district + " · " + row.sector_label) + "'><small>" + esc(shortName[row.state] || row.state) +
        "</small><strong>" + row.priority + "</strong></button>";
    }).join("");

    var briefs = data.briefs.map(function (cell) {
      var label = hi() ? cell.sector_label_hi : cell.sector_label;
      var quote = cell.quotes && cell.quotes[0] ? "<p class='quote'>" + esc(cell.quotes[0].text) + "</p>" : "";
      return "<a class='brief' href='/note/" + esc(cell.slug) + "/" + esc(cell.sector) + "'><span class='tag'>" +
        esc(signalLabel(cell.signal)) + " · " + cell.priority + "</span><strong>" + esc(cell.district) + "</strong>" +
        "<p>" + esc(cell.state) + " · " + esc(label) + " · ₹" + cell.tranche_cr + " Cr indicative, ₹" + cell.allocated_cr +
        " Cr on the line</p>" + quote + "</a>";
    }).join("");

    var under = data.underheard.map(function (cell) {
      var label = hi() ? cell.sector_label_hi : cell.sector_label;
      return "<a class='under-card' href='/note/" + esc(cell.slug) + "/" + esc(cell.sector) + "'><span class='tag under'>" +
        esc(signalLabel("Under-heard")) + "</span><strong>" + esc(cell.district) + "</strong><p>" + esc(label) +
        " · coverage " + cell.infra + "/100 · " + cell.requests + " records · voice reach " + Math.round(cell.voice * 100) +
        "%</p></a>";
    }).join("");

    var rows = data.cells.map(function (cell) {
      var label = hi() ? cell.sector_label_hi : cell.sector_label;
      var tag = cell.signal === "Under-heard" ? " under" : (cell.signal === "Priority" ? " priority" : "");
      return "<tr><td><a href='/note/" + esc(cell.slug) + "/" + esc(cell.sector) + "'>" + esc(cell.district) +
        "</a><div class='hint'>" + esc(cell.state) + "</div></td><td>" + esc(label) + "</td><td>" + cell.requests +
        "</td><td>" + cell.infra + "</td><td>₹" + cell.allocated_cr + "</td><td>₹" + cell.tranche_cr + "</td><td>" +
        cell.priority + "</td><td><span class='tag" + tag + "'>" + esc(signalLabel(cell.signal)) + "</span></td></tr>";
    }).join("");

    var langMax = Math.max.apply(null, data.languages.map(function (row) { return row.count; }).concat([1]));
    var langs = data.languages.filter(function (row) { return row.count; }).map(function (row) {
      return "<li><span>" + esc(row.native) + "</span><span class='bar'><i style='width:" +
        Math.round(row.count / langMax * 100) + "%'></i></span><b>" + row.count + "</b></li>";
    }).join("");

    root.innerHTML =
      "<section class='pulse'>" +
      stat(pulse.requests.toLocaleString("en-IN"), hi() ? "रिकॉर्ड" : "Records on the ledger") +
      stat(String(pulse.languages), hi() ? "भाषाएँ" : "Languages heard") +
      stat(String(pulse.hotspots), hi() ? "हॉटस्पॉट" : "Hotspots") +
      stat("₹" + pulse.unfunded_cr, hi() ? "करोड़ की कमी, छह नोटों पर" : "Cr short on the six notes") +
      stat(pulse.people_label, hi() ? "लोग, उन परियोजनाओं में" : "People named in those projects") +
      "</section>" +
      "<section class='console-layout'><div>" +
      "<div class='atlas' id='atlas'>" + atlas + "</div>" +
      "<table class='board'><thead><tr><th>District</th><th>Need</th><th>Records</th><th>Coverage</th><th>Line ₹ Cr</th><th>Package ₹ Cr</th><th>Score</th><th></th></tr></thead><tbody>" +
      rows + "</tbody></table></div><aside><p class='hint'>" +
      (hi() ? "ये छह नोट राष्ट्रीय पोर्टफोलियो हैं। फ़िल्टर नक्शा और तालिका बदलते हैं।" : "These six notes are the national portfolio. Filters change the map and the table.") +
      "</p><p class='eyebrow'>" + (hi() ? "कैबिनेट नोट" : "Cabinet notes") +
      "</p>" + briefs + "<p class='eyebrow' style='margin-top:1rem'>" + (hi() ? "कम सुनी गई जगहें" : "Under-heard, badly served") +
      "</p><p class='hint'>" + (hi() ? "खामोशी यहाँ संतुष्टि नहीं है।" : "Quiet here is not evidence that the need is met.") +
      "</p>" + under + "</aside></section>" +
      "<section class='split languages-band'><div><p class='eyebrow'>" + (hi() ? "भाषाएँ" : "Languages on file") +
      "</p><h2>" + (hi() ? "इस खाते ने कौन सी भाषाएँ सुनीं।" : "What this ledger was able to hear.") +
      "</h2></div><ul class='lang-bars'>" + langs + "</ul></section>";

    root.querySelectorAll(".bubble").forEach(function (btn) {
      btn.addEventListener("click", function () {
        stateSel.value = stateSel.value === btn.dataset.state ? "" : btn.dataset.state;
        load();
      });
    });
  }

  function stat(value, label) {
    return "<article><b>" + esc(value) + "</b><span>" + esc(label) + "</span></article>";
  }

  stateSel.addEventListener("change", load);
  sectorSel.addEventListener("change", load);
  var qTimer = null;
  query.addEventListener("input", function () {
    clearTimeout(qTimer);
    qTimer = setTimeout(load, 220);
  });
  document.addEventListener("jansetu-lang", function () { if (cache) render(cache); });
  load();
})();
