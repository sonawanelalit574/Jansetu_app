(function () {
  var boot = JSON.parse(document.getElementById("boot").textContent);
  var channel = "web";
  var voiceMode = "phone";
  var district = document.getElementById("district");
  var body = document.getElementById("body");
  var transcript = document.getElementById("transcript");
  var reading = document.getElementById("reading");
  var receipt = document.getElementById("receipt");
  var fileRow = document.getElementById("file-row");
  var sms = document.getElementById("as-sms");
  var smsCount = document.getElementById("sms-count");
  var timer = null;
  var recognition = null;

  function selectedLang() {
    var opt = district.selectedOptions[0];
    return (opt && opt.dataset.lang) || "hi";
  }

  function setChannel(next) {
    channel = next;
    document.querySelectorAll("[data-channel]").forEach(function (btn) {
      btn.classList.toggle("is-on", btn.dataset.channel === next);
    });
    document.querySelectorAll("[data-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.panel !== next;
    });
    fileRow.hidden = next === "whatsapp";
  }

  function setVoice(next) {
    voiceMode = next;
    document.querySelectorAll("[data-voice]").forEach(function (btn) {
      btn.classList.toggle("is-on", btn.dataset.voice === next);
    });
    document.querySelectorAll("[data-voice-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.voicePanel !== next;
    });
    fileRow.hidden = channel === "whatsapp" || (channel === "voice" && next === "ivr");
  }

  document.querySelectorAll("[data-channel]").forEach(function (btn) {
    btn.addEventListener("click", function () { setChannel(btn.dataset.channel); });
  });
  document.querySelectorAll("[data-voice]").forEach(function (btn) {
    btn.addEventListener("click", function () { setVoice(btn.dataset.voice); });
  });

  function currentText() {
    if (channel === "voice") return transcript.value.trim();
    return body.value.trim();
  }

  function paintReading(data) {
    if (!data || !data.reading) {
      reading.innerHTML = "<p class='muted'>Start writing. The language, the need, and the severity show up here before you file.</p>";
      return;
    }
    var r = data.reading;
    var preview = "";
    if (data.preview) {
      preview = "<p>" + escapeHtml(data.preview.district) + " · " + escapeHtml(data.preview.sector_label) +
        " is at priority " + data.preview.priority + " (" + escapeHtml(data.preview.signal) + "), from " +
        data.preview.requests + " records already on file.</p>";
    }
    var ask = data.reply ? "<p><strong>" + escapeHtml(data.reply) + "</strong></p>" : "";
    reading.innerHTML =
      "<div class='reading-card'><b>" + escapeHtml(r.language_native || r.language_label) + "</b>" +
      "<p>" + escapeHtml(r.sector_label) + " · severity " + r.severity + " of 5 · confidence " + Math.round(r.confidence * 100) + "%</p>" +
      "<p>" + escapeHtml(r.gloss) + "</p>" + ask + preview + "</div>";
    if (data.district_id && !district.value) district.value = String(data.district_id);
  }

  function analyze() {
    var text = currentText();
    if (text.length < 2) return;
    fetch("/api/analyze", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: text, district_id: district.value || null, channel: channel === "voice" ? "voice" : (sms.checked ? "sms" : "web")})
    }).then(function (res) { return res.json(); }).then(paintReading).catch(function () {
      reading.innerHTML = "<p>The reading could not be fetched. You can still file.</p>";
    });
  }

  body.addEventListener("input", function () {
    if (sms.checked) {
      smsCount.hidden = false;
      smsCount.textContent = body.value.length + " / 160";
      if (body.value.length > 160) body.value = body.value.slice(0, 160);
    }
    clearTimeout(timer);
    timer = setTimeout(analyze, 280);
  });
  transcript.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(analyze, 280);
  });
  district.addEventListener("change", analyze);
  sms.addEventListener("change", function () {
    smsCount.hidden = !sms.checked;
    body.maxLength = sms.checked ? 160 : 800;
    if (sms.checked && body.value.length > 160) body.value = body.value.slice(0, 160);
    smsCount.textContent = body.value.length + " / 160";
  });

  document.querySelectorAll("[data-sample]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setChannel("web");
      district.value = btn.dataset.district;
      body.value = btn.dataset.text;
      analyze();
    });
  });

  document.getElementById("composer").addEventListener("submit", function (event) {
    event.preventDefault();
    var text = currentText();
    if (text.length < 8) {
      reading.innerHTML = "<p>Say a little more about the need.</p>";
      return;
    }
    file({
      text: text,
      district_id: district.value || null,
      channel: channel === "voice" ? "voice" : (sms.checked ? "sms" : "web")
    });
  });

  function file(payload) {
    var button = document.getElementById("file");
    button.disabled = true;
    fetch("/api/requests", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    }).then(function (res) { return res.json(); }).then(function (data) {
      button.disabled = false;
      if (!data.ok) {
        paintReading(data);
        return;
      }
      showReceipt(data);
    }).catch(function () {
      button.disabled = false;
      reading.innerHTML = "<p>The request did not go through. Try once more.</p>";
    });
  }

  function showReceipt(data) {
    receipt.hidden = false;
    receipt.className = "receipt";
    receipt.innerHTML =
      "<p class='eyebrow'>Recorded</p><p class='ref'>" + escapeHtml(data.ref) + "</p>" +
      "<p>" + escapeHtml(data.reply) + "</p><p>" + escapeHtml(data.effect) + "</p>" +
      "<p><a href='" + escapeHtml(data.track) + "'>Track this reference</a> · <a href='" + escapeHtml(data.note) + "'>Open the cabinet note</a></p>";
  }

  var mic = document.getElementById("mic");
  var Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Speech) {
    document.getElementById("mic-hint").textContent = "This browser has no speech engine. Paste a transcript and file it as voice.";
  } else {
    recognition = new Speech();
    recognition.interimResults = false;
    recognition.onresult = function (event) {
      transcript.value = event.results[0][0].transcript;
      mic.classList.remove("is-live");
      analyze();
    };
    recognition.onend = function () { mic.classList.remove("is-live"); };
    recognition.onerror = function () { mic.classList.remove("is-live"); };
    mic.addEventListener("click", function () {
      recognition.lang = ({hi:"hi-IN", en:"en-IN", ta:"ta-IN", te:"te-IN", bn:"bn-IN", mr:"mr-IN", kn:"kn-IN", ml:"ml-IN", gu:"gu-IN", pa:"pa-IN", or:"or-IN", as:"as-IN"})[selectedLang()] || "hi-IN";
      mic.classList.add("is-live");
      recognition.start();
    });
  }

  document.getElementById("keypad").addEventListener("click", function (event) {
    var key = event.target.closest("[data-key]");
    if (!key) return;
    if (!district.value) {
      reading.innerHTML = "<p>Choose the district first. A missed call still has to land in a district.</p>";
      district.focus();
      return;
    }
    var lang = selectedLang();
    var text = (boot.ivr[lang] && boot.ivr[lang][key.dataset.key]) || "";
    file({text: text, district_id: district.value, channel: "ivr", sector: key.dataset.key});
  });

  var thread = document.getElementById("thread");
  var waInput = document.getElementById("wa-input");
  addBubble("bot", "नमस्ते। पानी, सड़क, स्कूल, अस्पताल, बिजली — अपनी भाषा में लिखिए। जिला ऊपर चुन सकते हैं, या नाम लिख सकते हैं।");

  document.getElementById("wa-send").addEventListener("click", sendWa);
  waInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") { event.preventDefault(); sendWa(); }
  });

  function sendWa() {
    var text = waInput.value.trim();
    if (!text) return;
    waInput.value = "";
    addBubble("user", text);
    fetch("/api/requests", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: text, district_id: district.value || null, channel: "whatsapp"})
    }).then(function (res) { return res.json(); }).then(function (data) {
      if (!data.ok) {
        addBubble("bot", data.reply || "I need a district and a clear need.");
        if (data.needs && data.needs.indexOf("sector") !== -1) showSectorPick(text);
        return;
      }
      addBubble("bot", data.reply);
      showReceipt(data);
    });
  }

  function showSectorPick(text) {
    var row = document.createElement("div");
    row.className = "sector-pick";
    Object.keys(boot.sectors).forEach(function (code) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = boot.sectors[code].label;
      btn.addEventListener("click", function () {
        row.remove();
        fetch("/api/requests", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text: text, district_id: district.value || null, channel: "whatsapp", sector: code})
        }).then(function (res) { return res.json(); }).then(function (data) {
          addBubble("bot", data.reply || data.error || "Try again.");
          if (data.ok) showReceipt(data);
        });
      });
      row.appendChild(btn);
    });
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
  }

  function addBubble(role, text) {
    var node = document.createElement("div");
    node.className = "bubble " + role;
    node.textContent = text;
    thread.appendChild(node);
    thread.scrollTop = thread.scrollHeight;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch];
    });
  }
})();
