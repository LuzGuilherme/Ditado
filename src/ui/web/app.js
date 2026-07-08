/* DITADO — front-end "Fita". Fala com Python via window.pywebview.api. */
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const app = {
  S: null,          // bootstrap state vindo do Python
  liveState: "idle",
  clearArmed: false,

  /* ---------------- arranque ---------------- */
  async boot() {
    this.S = await pywebview.api.get_bootstrap();
    $("#ver").textContent = "v" + this.S.version;
    this.renderTopline();
    this.renderDeck();
    this.renderTakes();
    this.renderDefs();
    this.renderApi();
    this.renderCounter();
    this.wireChrome();
  },

  /* ---------------- canal Python → JS ---------------- */
  push(evt, data) {
    if (evt === "state") { this.liveState = data; this.paintState(); }
    if (evt === "history") { this.S.history = data; this.renderTakes(); this.renderCounter(); }
    if (evt === "enabled") { this.S.enabled = data; this.paintState(); }
  },

  /* ---------------- painel ---------------- */
  renderTopline() {
    const now = new Date();
    const dias = ["DOMINGO", "SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO"];
    const meses = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];
    $("#dateline").textContent =
      `${dias[now.getDay()]}  ·  ${now.getDate()} ${meses[now.getMonth()]} ${now.getFullYear()}`;

    const st = this.S.streak;
    const box = $("#streak");
    if (st > 0) {
      box.hidden = false;
      $("#streakcells").innerHTML = Array.from({ length: 7 },
        (_, i) => `<span class="cell${i < Math.min(st, 7) ? " hot" : ""}"></span>`).join("");
      $("#streakn").textContent = st + (st === 1 ? " dia" : " dias");
    } else {
      box.hidden = true;
    }

    const h = now.getHours();
    const slot = h >= 5 && h < 12 ? "Bom dia" : h >= 12 && h < 20 ? "Boa tarde" : "Boa noite";
    const nome = this.S.first_name;
    $("#hello").textContent = nome ? `${slot}, ${nome}.` : `${slot}.`;
  },

  hotkeyHtml(hk) {
    const map = (p) => {
      p = p.trim().toLowerCase();
      if (p.startsWith("ctrl")) return "CTRL";
      if (p.startsWith("cmd")) return "WIN";
      if (p.startsWith("alt")) return "ALT";
      if (p.startsWith("shift")) return "SHIFT";
      if (p === "caps_lock") return "CAPS LOCK";
      return p.replace(/_/g, " ").toUpperCase();
    };
    return hk.split("+").map((p) => `<kbd>${esc(map(p))}</kbd>`)
      .join(`<span class="kplus">+</span>`);
  },

  renderDeck() {
    $("#hotkeys").innerHTML = this.hotkeyHtml(this.S.settings.hotkey);
    // barras VU com alturas e fases determinísticas mas orgânicas
    $("#vu").innerHTML = Array.from({ length: 56 }, (_, i) => {
      const h = 18 + Math.abs(Math.sin(i * 1.7)) * 64 + (i * 37 % 17);
      return `<i style="--h:${Math.min(h, 96)}%;--d:${(i * 0.031).toFixed(3)}"></i>`;
    }).join("");
    this.paintState();
  },

  paintState() {
    const deck = $("#deck");
    const dot = $("#branddot");
    const line = $("#deckline");
    deck.className = "";
    dot.className = "dot";

    if (!this.S.has_api_key) {
      deck.classList.add("off");
      $("#status").textContent = "CONFIGURAÇÃO NECESSÁRIA";
      line.innerHTML = `Falta a chave OpenAI. Cola-a no separador <em>Ligação</em> e começa a ditar em segundos.`;
      $("#btn-hotkey").textContent = "Configurar ligação";
      return;
    }
    $("#btn-hotkey").textContent = "Alterar tecla";
    line.innerHTML = `Mantém a tecla, fala, solta. As tuas palavras aparecem <em>onde estiver o cursor</em> — em qualquer aplicação.`;

    if (!this.S.enabled) {
      deck.classList.add("off");
      $("#status").textContent = "EM PAUSA · DITADO DESLIGADO";
      return;
    }
    const st = this.liveState;
    if (st === "recording") {
      deck.classList.add("rec"); dot.classList.add("live");
      $("#status").textContent = "A GRAVAR";
    } else if (st === "transcribing" || st === "processing") {
      deck.classList.add("busy"); $("#status").textContent = "A TRANSCREVER";
    } else if (st === "enhancing") {
      deck.classList.add("busy"); $("#status").textContent = "A POLIR";
    } else if (st === "typing") {
      deck.classList.add("busy"); $("#status").textContent = "A ESCREVER";
    } else if (st === "error") {
      $("#status").textContent = "O ÚLTIMO TAKE FALHOU";
      $("#status").style.color = "var(--rec)";
      return;
    } else {
      $("#status").textContent = "EM ESPERA";
    }
    $("#status").style.color = "";
  },

  /* ---------------- takes ---------------- */
  relTime(iso) {
    const d = new Date(iso), now = new Date();
    const s = (now - d) / 1000;
    if (s < 60) return "agora mesmo";
    if (s < 3600) return `há ${Math.floor(s / 60)} min`;
    if (s < 86400 && d.getDate() === now.getDate()) return `há ${Math.floor(s / 3600)} h`;
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ontem = new Date(now); ontem.setDate(now.getDate() - 1);
    if (d.toDateString() === ontem.toDateString()) return `ontem, ${hh}:${mm}`;
    const meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
    return `${d.getDate()} ${meses[d.getMonth()]}, ${hh}:${mm}`;
  },

  timecode(sec) {
    const m = Math.floor(sec / 60), s = Math.round(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  },

  waveHtml(seed, n = 34) {
    // hash simples e determinístico: o mesmo take desenha sempre a mesma onda
    let h = 2166136261;
    for (const c of seed) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
    const rnd = () => { h ^= h << 13; h ^= h >>> 17; h ^= h << 5; return ((h >>> 0) % 1000) / 1000; };
    return Array.from({ length: n }, (_, i) => {
      const env = Math.sin(((i + 1) / n) * Math.PI) * 0.75 + 0.25;
      return `<i style="--h:${Math.max(10, Math.round((rnd() * 0.6 + 0.4) * env * 100))}%"></i>`;
    }).join("");
  },

  renderTakes() {
    const takes = this.S.history || [];
    $("#empty").hidden = takes.length > 0;
    $("#emptyhint").innerHTML = takes.length ? "" :
      `Mantém ${this.hotkeyHtml(this.S.settings.hotkey)} e fala`;
    $("#takes").innerHTML = takes.slice(0, 6).map((t) => `
      <article class="take" data-id="${esc(t.id)}" title="Clicar copia o texto">
        <div class="meta">
          <span class="tc">${this.timecode(t.duration)}</span>
          <span class="rel caps">${esc(this.relTime(t.timestamp))}</span>
          <button class="copy" data-id="${esc(t.id)}">Copiar</button>
        </div>
        <p class="txt">${esc(t.text)}</p>
        <div class="wave">${this.waveHtml(t.id)}</div>
      </article>`).join("");

    document.querySelectorAll(".take").forEach((el) => {
      el.addEventListener("click", () => this.copyTake(el.dataset.id, el.querySelector(".copy")));
    });
  },

  async copyTake(id, btn) {
    const r = await pywebview.api.copy_take(id);
    if (r.ok && btn) {
      btn.textContent = "✓ Copiado"; btn.classList.add("done");
      setTimeout(() => { btn.textContent = "Copiar"; btn.classList.remove("done"); }, 1500);
    }
  },

  /* ---------------- definições ---------------- */
  row(label, desc, controlHtml) {
    return `<div class="row">
      <div class="lab"><div class="t">${label}</div>${desc ? `<div class="d">${desc}</div>` : ""}</div>
      ${controlHtml}
    </div>`;
  },
  toggle(id, on) {
    return `<label class="toggle"><input type="checkbox" id="${id}" ${on ? "checked" : ""}><span class="track"></span></label>`;
  },

  renderDefs() {
    const s = this.S.settings;
    const devs = [`<option value="">Predefinido do sistema</option>`]
      .concat(this.S.audio_devices.map((d) =>
        `<option value="${d.index}" ${s.audio_device_index === d.index ? "selected" : ""}>${esc(d.name)}</option>`));
    const langs = this.S.languages.map((l) =>
      `<option value="${l.code}" ${s.language === l.code ? "selected" : ""}>${esc(l.name)}</option>`);
    const durs = [[60, "1 min"], [120, "2 min"], [300, "5 min"], [600, "10 min"], [900, "15 min"], [0, "Sem limite"]]
      .map(([v, t]) => `<option value="${v}" ${s.max_recording_seconds === v ? "selected" : ""}>${t}</option>`);
    const poss = [["top-left", "Cima, esquerda"], ["top-right", "Cima, direita"], ["bottom-left", "Baixo, esquerda"],
      ["bottom-center", "Baixo, centro"], ["bottom-right", "Baixo, direita"]]
      .map(([v, t]) => `<option value="${v}" ${s.indicator_position === v ? "selected" : ""}>${t}</option>`);

    $("#defs-body").innerHTML = `
      <div class="sec"><span class="caps">Gravação</span><div class="card">
        ${this.row("Tecla de ditado", "Mantém premida para gravar",
          `<span id="defs-hotkey">${this.hotkeyHtml(s.hotkey)}</span>
           <button class="btn ghost" id="btn-capture">Capturar</button>`)}
        ${this.row("Microfone", "",
          `<select id="f-device">${devs.join("")}</select>
           <button class="btn ghost" id="btn-mic">Testar</button>`)}
        ${this.row("", "", `<span class="status dim" id="mic-status"></span>`)}
        ${this.row("Idioma do ditado", "", `<select id="f-lang">${langs.join("")}</select>`)}
        ${this.row("Duração máxima", "Com paragem automática ao atingir o limite",
          `<select id="f-dur">${durs.join("")}</select>${this.toggle("f-autostop", s.auto_stop_recording)}`)}
      </div></div>

      <div class="sec"><span class="caps">Preferências</span><div class="card">
        ${this.row("O teu primeiro nome", "Aparece na saudação do painel",
          `<input type="text" id="f-nome" value="${esc(this.S.first_name_setting)}" placeholder="Guilherme">`)}
        ${this.row("Polimento do texto", "O GPT remove hesitações e corrige a gramática",
          this.toggle("f-enhance", s.enhance_text))}
        ${this.row("Posição do indicador", "", `<select id="f-pos">${poss.join("")}</select>`)}
        ${this.row("Silenciar o sistema ao gravar", "Evita que a música entre na transcrição",
          this.toggle("f-mute", s.mute_system_audio))}
        ${this.row("Sinais sonoros", "Um clique ao começar e ao terminar",
          this.toggle("f-sound", s.sound_feedback))}
      </div></div>

      <div class="sec"><span class="caps">Sistema</span><div class="card">
        ${this.row("Arrancar com o Windows", "", this.toggle("f-boot", s.auto_start_on_boot))}
        ${this.row("Guardar o texto no histórico", "Desligado, o histórico guarda apenas contagens — nada fica escrito em disco",
          this.toggle("f-privacy", this.S.store_full_text))}
      </div></div>`;

    $("#btn-capture").addEventListener("click", () => this.captureHotkey());
    $("#btn-mic").addEventListener("click", () => this.testMic());
    $("#btn-save-defs").addEventListener("click", () => this.save());
  },

  async captureHotkey() {
    const b = $("#btn-capture");
    b.disabled = true; b.textContent = "Mantém as teclas…";
    const r = await pywebview.api.capture_hotkey();
    b.disabled = false; b.textContent = "Capturar";
    if (r.ok) {
      this.S.settings.hotkey = r.hotkey;
      $("#defs-hotkey").innerHTML = this.hotkeyHtml(r.hotkey);
      this.toast("Nova tecla capturada — guarda as alterações para aplicar");
    } else {
      this.toast(r.msg || "Não foi possível capturar", true);
    }
  },

  async testMic() {
    const b = $("#btn-mic"), st = $("#mic-status");
    b.disabled = true;
    st.className = "status dim"; st.textContent = "A gravar uma amostra de 1s…";
    const dev = $("#f-device").value;
    const r = await pywebview.api.test_microphone(dev === "" ? null : Number(dev));
    b.disabled = false;
    st.className = "status " + (r.ok ? "ok" : "err");
    st.textContent = r.msg;
  },

  /* ---------------- ligação (API) ---------------- */
  renderApi() {
    const s = this.S.settings;
    const wm = ["whisper-1"].map((m) =>
      `<option ${s.whisper_model === m ? "selected" : ""}>${m}</option>`);
    const gm = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"].map((m) =>
      `<option ${s.gpt_model === m ? "selected" : ""}>${m}</option>`);

    $("#api-body").innerHTML = `
      <div class="sec"><span class="caps">Chave OpenAI</span><div class="card">
        ${this.row("Chave da API", "Guardada em segurança no Gestor de Credenciais do Windows",
          `<input type="password" class="mono wide" id="f-key" value="${esc(this.S.api_key)}" placeholder="sk-…">
           <button class="btn ghost" id="btn-eye">Mostrar</button>`)}
        ${this.row("", "", `<button class="btn ghost" id="btn-testapi">Testar ligação</button>
           <span class="status dim" id="api-status"></span>`)}
        ${this.row("Ainda não tens chave?", "",
          `<button class="linkish" id="btn-getkey" style="text-transform:none;letter-spacing:.02em;font-size:12px">Obter uma na OpenAI →</button>`)}
      </div></div>

      <div class="sec"><span class="caps">Modelos</span><div class="card">
        ${this.row("Transcrição (Whisper)", "", `<select id="f-whisper">${wm.join("")}</select>`)}
        ${this.row("Polimento (GPT)", "", `<select id="f-gpt">${gm.join("")}</select>`)}
        ${this.row("Custo típico", "Whisper ~$0.006/min · GPT ~$0.0003 por take. Com 30 min/dia, espera $5-6/mês.", `<span></span>`)}
      </div></div>`;

    $("#btn-eye").addEventListener("click", () => {
      const k = $("#f-key");
      const show = k.type === "password";
      k.type = show ? "text" : "password";
      $("#btn-eye").textContent = show ? "Ocultar" : "Mostrar";
    });
    $("#btn-testapi").addEventListener("click", async () => {
      const b = $("#btn-testapi"), st = $("#api-status");
      b.disabled = true;
      st.className = "status dim"; st.textContent = "A contactar a OpenAI…";
      const r = await pywebview.api.test_api($("#f-key").value.trim());
      b.disabled = false;
      st.className = "status " + (r.ok ? "ok" : "err");
      st.textContent = r.msg;
    });
    $("#btn-getkey").addEventListener("click", () =>
      pywebview.api.open_url("https://platform.openai.com/api-keys"));
    $("#btn-save-api").addEventListener("click", () => this.save());
  },

  /* ---------------- contador ---------------- */
  renderCounter() {
    const t = this.S.stats;
    const c = this.S.costs;
    const crow = (lab, val, unit = "", hot = false) => `
      <div class="crow"><span class="lab">${lab}</span>
        <span class="val${hot ? " hot" : ""}">${val}</span>${unit ? `<span class="unit">${unit}</span>` : ""}
      </div>`;
    $("#counterwrap").innerHTML = `
      <div class="sec"><span class="caps">Esta sessão</span><div class="card">
        ${crow("Takes", t.session_requests)}
        ${crow("Tempo de voz", t.session_minutes.toFixed(1), "min")}
      </div></div>
      <div class="sec"><span class="caps">Desde sempre${t.first_use ? " · " + esc(t.first_use) : ""}</span><div class="card">
        ${crow("Takes", t.total_requests)}
        ${crow("Tempo de voz", t.total_minutes.toFixed(1), "min")}
        ${crow("Palavras ditadas", t.total_words.toLocaleString("pt-PT"), "", true)}
        ${crow("Semanas ativas", t.weeks_active)}
      </div></div>
      <div class="sec"><span class="caps">Custo estimado</span><div class="card">
        ${crow("Whisper", "$" + c.whisper.toFixed(3))}
        ${crow("GPT", "$" + c.gpt.toFixed(3))}
        ${crow("Total", "$" + c.total.toFixed(3), "", true)}
      </div></div>`;
  },

  /* ---------------- guardar ---------------- */
  async save() {
    const payload = {
      hotkey: this.S.settings.hotkey,
      language: $("#f-lang").value,
      indicator_position: $("#f-pos").value,
      enhance_text: $("#f-enhance").checked,
      api_key: $("#f-key").value.trim(),
      whisper_model: $("#f-whisper").value,
      gpt_model: $("#f-gpt").value,
      max_recording_seconds: Number($("#f-dur").value),
      auto_stop_recording: $("#f-autostop").checked,
      mute_system_audio: $("#f-mute").checked,
      sound_feedback: $("#f-sound").checked,
      auto_start_on_boot: $("#f-boot").checked,
      store_full_text: $("#f-privacy").checked,
      user_first_name: $("#f-nome").value.trim(),
      audio_device_index: $("#f-device").value === "" ? null : Number($("#f-device").value),
    };
    const r = await pywebview.api.save_settings(payload);
    if (r.ok) {
      Object.assign(this.S.settings, payload);
      this.S.has_api_key = !!payload.api_key;
      this.S.first_name = payload.user_first_name || this.S.first_name_fallback;
      this.S.store_full_text = payload.store_full_text;
      this.renderTopline(); this.paintState();
      $("#hotkeys").innerHTML = this.hotkeyHtml(payload.hotkey);
      this.toast("Alterações guardadas");
    } else {
      this.toast(r.msg || "Não foi possível guardar", true);
    }
  },

  /* ---------------- chrome ---------------- */
  wireChrome() {
    document.querySelectorAll(".nav").forEach((b) => {
      b.addEventListener("click", () => {
        document.querySelectorAll(".nav").forEach((x) => x.classList.remove("active"));
        document.querySelectorAll(".tab").forEach((x) => x.classList.remove("on"));
        b.classList.add("active");
        $("#tab-" + b.dataset.tab).classList.add("on");
        $("#stage").scrollTop = 0;
      });
    });
    $("#btn-min").addEventListener("click", () => pywebview.api.minimize_window());
    $("#btn-close").addEventListener("click", () => pywebview.api.hide_window());
    $("#btn-defs").addEventListener("click", () => $('.nav[data-tab="defs"]').click());
    $("#btn-hotkey").addEventListener("click", () => {
      if (!this.S.has_api_key) $('.nav[data-tab="api"]').click();
      else { $('.nav[data-tab="defs"]').click(); }
    });
    $("#btn-clear").addEventListener("click", async () => {
      const b = $("#btn-clear");
      if (!this.clearArmed) {
        this.clearArmed = true;
        b.textContent = "Clica outra vez para apagar";
        b.classList.add("armed");
        setTimeout(() => {
          this.clearArmed = false;
          b.textContent = "Limpar histórico";
          b.classList.remove("armed");
        }, 3000);
        return;
      }
      this.clearArmed = false;
      b.textContent = "Limpar histórico";
      b.classList.remove("armed");
      await pywebview.api.clear_history();
      this.S.history = [];
      this.renderTakes();
      this.toast("Histórico apagado");
    });
  },

  toast(msg, isErr = false) {
    const t = $("#toast");
    t.textContent = msg;
    t.className = "show" + (isErr ? " err" : "");
    clearTimeout(this._toastT);
    this._toastT = setTimeout(() => (t.className = ""), 2600);
  },
};

window.addEventListener("pywebviewready", () => app.boot());
