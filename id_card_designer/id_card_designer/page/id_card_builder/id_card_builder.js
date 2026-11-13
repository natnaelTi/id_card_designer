frappe.pages["id-card-builder"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("ID Card Builder"),
    single_column: true,
  });
  wrapper.builder = new IDCardBuilder(page);
};
frappe.pages["id-card-builder"].on_page_show = function (wrapper) {
  wrapper.builder.load();
};

class IDCardBuilder {
  constructor(page) {
    this.page = page;
    this.side = "front";
    this.zoom = 2;
    this.grid = true;
    this.snap = true;
    this.history = [];
    this.future = [];
    this.selected = -1;
    this.dirty = false;
    this.root = document.createElement("div");
    this.root.style.paddingTop = "var(--page-head-height,60px)";
    page.main.append(this.root);
    this.root.innerHTML = `<style>
        @font-face{font-family:FreeSerif;src:url(/assets/id_card_designer/fonts/FreeSerif.ttf)}.ic-toolbar{position:sticky;top:calc(var(--navbar-height,48px) + var(--page-head-height,60px));z-index:5;background:var(--card-bg);padding:8px 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:16px}.ic-layout{display:grid;align-items:start;grid-template-columns:180px minmax(360px,1fr) 230px;gap:16px}.ic-panel{max-height:75vh;overflow:auto;padding:12px;background:var(--card-bg);border:1px solid var(--border-color);border-radius:8px}.ic-panel button{margin:3px}.ic-panel label{display:block;margin:10px 0 3px;font-size:12px}.ic-panel input,.ic-panel select,.ic-panel textarea{width:100%;border:1px solid var(--border-color);border-radius:4px;padding:5px;background:var(--control-bg);color:var(--text-color)}.ic-stage{max-height:75vh;overflow:auto;min-height:420px;padding:28px;background:var(--subtle-fg)}.ic-canvas{position:relative;background:#f5f3e7;box-shadow:0 6px 24px #0002;overflow:hidden;transform-origin:top left;color:#244b47;font-family:FreeSerif,serif;line-height:1.2}.ic-element{position:absolute;box-sizing:border-box;overflow:hidden;overflow-wrap:anywhere;cursor:move;touch-action:none}.ic-element.selected{outline:2px solid #2490ef}.ic-handle{position:absolute;right:0;bottom:0;width:10px;height:10px;background:#2490ef;cursor:se-resize}.ic-safe{position:absolute;inset:3mm;border:1px dashed #b69555;pointer-events:none}.ic-layer{display:block;width:100%;text-align:left}.ic-status{font-size:12px;color:var(--text-muted)}.ic-code{display:none;grid-column:1/-1}.ic-code textarea{width:100%;min-height:180px;font-family:monospace}.ic-code-editor{height:240px;border:1px solid var(--border-color)}@media(max-width:1000px){.ic-layout{grid-template-columns:1fr}.ic-stage{min-height:300px}}
        </style><div class="ic-toolbar"></div><div class="ic-status" role="status"></div><div class="ic-layout"><aside class="ic-panel ic-tools"></aside><main class="ic-stage"><div class="ic-canvas" tabindex="0" aria-label="Card design canvas"></div></main><aside class="ic-panel ic-properties"></aside><section class="ic-code ic-panel"></section></div>`;
    this.toolbar = this.root.querySelector(".ic-toolbar");
    this.canvas = this.root.querySelector(".ic-canvas");
    this.props = this.root.querySelector(".ic-properties");
    this.tools = this.root.querySelector(".ic-tools");
    this.canvas.addEventListener("keydown", (e) => this.key(e));
    this.canvas.addEventListener("click", (e) => {
      if (e.target === this.canvas) {
        this.selected = -1;
        this.render();
      }
    });
    this.root.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        this.save();
      }
    });
    window.addEventListener("beforeunload", (e) => {
      if (this.dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  }
  async call(method, args = {}) {
    return (await frappe.call("id_card_designer.api." + method, args)).message;
  }
  async load() {
    const name = frappe.get_route()[1];
    if (this.doc && this.doc.name === name) return;
    this.caps = await this.call("capabilities");
    this.fields = await this.call("get_field_schema");
    this.data = await this.call("get_preview_data");
    this.doc = name
      ? await this.call("get_template_for_builder", { name })
      : {
          title: "Untitled template",
          editor_mode: "Visual",
          width_mm: 85.6,
          height_mm: 53.98,
          bleed_mm: 0,
          enabled: 1,
          front_layout: "[]",
          back_layout: "[]",
          front_html: "",
          back_html: "",
          shared_css: "",
        };
    if (!name) Object.assign(this.doc, await this.call("get_builder_defaults"));
    this.scenes = {
      front: JSON.parse(this.doc.front_layout || "[]"),
      back: JSON.parse(this.doc.back_layout || "[]"),
    };
    this.history = [];
    this.future = [];
    this.dirty = false;
    this.selected = -1;
    this.drawUI();
  }
  button(parent, label, action) {
    const b = document.createElement("button");
    b.className = "btn btn-default btn-sm";
    b.textContent = __(label);
    b.onclick = action;
    parent.append(b);
    return b;
  }
  input(parent, label, value, fn, type = "text") {
    const l = document.createElement("label");
    l.textContent = __(label);
    const i = document.createElement(
      type === "textarea" ? "textarea" : "input"
    );
    i.id = "ic-" + frappe.utils.get_random(10);
    l.htmlFor = i.id;
    if (type !== "textarea") i.type = type;
    i.value = value ?? "";
    i.onchange = () => fn(type === "number" ? Number(i.value) : i.value);
    parent.append(l, i);
    return i;
  }
  select(parent, label, value, options, fn) {
    const l = document.createElement("label");
    l.textContent = __(label);
    const el = document.createElement("select");
    el.id = "ic-" + frappe.utils.get_random(10);
    l.htmlFor = el.id;
    for (const [v, t] of options) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = t;
      el.append(o);
    }
    el.value = value || "";
    el.onchange = () => fn(el.value);
    parent.append(l, el);
    return el;
  }
  drawUI() {
    this.toolbar.innerHTML = "";
    this.button(this.toolbar, "Back", () =>
      frappe.set_route("List", "ID Card Template")
    );
    this.input(this.toolbar, "Title", this.doc.title, (v) => {
      this.doc.title = v;
      this.changed();
    }).disabled = !!this.doc.builtin;
    for (const side of ["front", "back"])
      this.button(this.toolbar, side, () => {
        this.side = side;
        this.selected = -1;
        this.render();
      });
    this.button(this.toolbar, "Undo", () => this.undo());
    this.button(this.toolbar, "Redo", () => this.redo());
    this.button(this.toolbar, "Save draft", () => this.save());
    this.button(this.toolbar, "Preview PDF", () => this.preview());
    this.button(this.toolbar, "Preflight", async () => {
      if (!this.doc.builtin && !(await this.save())) return;
      const p = await this.call("preflight_template", {
        name: this.doc.name,
        user: this.previewUser || null,
      });
      frappe.msgprint({
        title: "PDF preflight",
        message: frappe.utils
          .escape_html(
            `${p.pages} pages · Trim ${p.width_mm} × ${
              p.height_mm
            } mm · MediaBox ${p.media_width_mm} × ${p.media_height_mm} mm\n${
              p.font
            }\n${p.warnings.join("\n") || "No basic layout warnings."}`
          )
          .replace(/\n/g, "<br>"),
      });
    });
    if (this.caps.manage) {
      this.button(this.toolbar, "Publish", async () => {
        if (await this.save()) {
          this.doc = await this.call("publish_template", {
            name: this.doc.name,
          });
          this.render();
        }
      });
      this.button(this.toolbar, "Set default", async () => {
        await this.call("set_default_template", { name: this.doc.name });
        frappe.show_alert(__("Default template updated"));
      });
      this.button(this.toolbar, "Restore revision", () => this.restore());
    }
    this.button(this.toolbar, "Duplicate", async () => {
      if (!this.doc.name) return;
      const d = await this.call("duplicate_template", { name: this.doc.name });
      this.dirty = false;
      frappe.set_route("id-card-builder", d.name);
    });
    this.select(
      this.toolbar,
      "Zoom",
      String(this.zoom),
      [
        ["1", "50%"],
        ["2", "100%"],
        ["3", "150%"],
      ],
      (v) => {
        this.zoom = Number(v);
        this.render();
      }
    );
    this.button(this.toolbar, "Grid", () => {
      this.grid = !this.grid;
      this.render();
    });
    this.button(this.toolbar, "Snap", () => {
      this.snap = !this.snap;
      this.render();
    });
    this.select(
      this.toolbar,
      "Mode",
      this.doc.editor_mode,
      [
        ["Visual", "Visual"],
        ["Code", "Code"],
      ],
      (v) => this.changeMode(v)
    );
    this.tools.innerHTML = "<strong>Elements & layers</strong>";
    for (const type of ["text", "image", "shape", "line"])
      this.button(this.tools, "Add " + type, () => this.add(type));
    this.button(this.tools, "Upload image", async () => {
      if (this.doc.builtin)
        return frappe.msgprint(__("Duplicate the protected sample first."));
      if (!this.doc.name && !(await this.save())) return;
      new frappe.ui.FileUploader({
        doctype: "ID Card Template",
        docname: this.doc.name,
        restrictions: {
          allowed_file_types: [".png", ".jpg", ".jpeg", ".webp"],
          max_file_size: 5 * 1024 * 1024,
        },
        on_success: (file) => {
          this.add("image");
          this.items()[this.selected].src = file.file_url;
          this.changed();
          this.render();
        },
      });
    });
    this.button(this.tools, "Saved images", async () => {
      if (!this.doc.name)
        return frappe.msgprint(__("Save this template first."));
      const files = await this.call("list_assets", { name: this.doc.name });
      if (!files.length)
        return frappe.msgprint(__("No images attached to this template yet."));
      frappe.prompt(
        [
          {
            fieldname: "asset",
            label: "Image",
            fieldtype: "Select",
            reqd: 1,
            options: files.map((f) => ({
              value: f.file_url,
              label: f.file_name,
            })),
          },
        ],
        (v) => {
          this.add("image");
          this.items()[this.selected].src = v.asset;
          this.changed();
          this.render();
        }
      );
    });
    this.select(
      this.tools,
      "Size preset",
      "",
      [
        ["", "Custom"],
        ["id1", "ID-1 · 85.60 × 53.98 mm"],
        ["badge", "Badge · 90 × 60 mm"],
      ],
      (v) => {
        if (!v) return;
        [this.doc.width_mm, this.doc.height_mm] =
          v === "id1" ? [85.6, 53.98] : [90, 60];
        this.changed();
        this.drawUI();
      }
    );
    this.input(
      this.tools,
      "Width mm",
      this.doc.width_mm,
      (v) => {
        this.doc.width_mm = v;
        this.changed();
        this.render();
      },
      "number"
    );
    this.input(
      this.tools,
      "Height mm",
      this.doc.height_mm,
      (v) => {
        this.doc.height_mm = v;
        this.changed();
        this.render();
      },
      "number"
    );
    this.select(
      this.tools,
      "Bleed (MediaBox expands)",
      String(this.doc.bleed_mm || 0),
      [
        ["0", "None"],
        ["3", "3 mm"],
      ],
      (v) => {
        this.doc.bleed_mm = Number(v);
        this.changed();
      }
    );
    this.input(
      this.tools,
      "Preview User (blank = fictional)",
      "",
      async (v) => {
        this.data = await this.call("get_preview_data", { user: v || null });
        this.previewUser = v || null;
        this.render();
      }
    );
    this.layerList = document.createElement("div");
    this.tools.append(this.layerList);
    this.render();
  }
  items() {
    return this.scenes[this.side];
  }
  checkpoint() {
    this.history.push(JSON.stringify(this.scenes));
    if (this.history.length > 50) this.history.shift();
    this.future = [];
  }
  changed() {
    this.dirty = true;
    this.status();
  }
  status() {
    this.root.querySelector(".ic-status").textContent = `${
      this.doc.status || "Draft"
    } r${this.doc.revision || 0}${
      this.doc.draft_unpublished ? " (draft changes)" : ""
    } · ${this.side} · ${
      this.doc.builtin
        ? "Protected sample — duplicate to edit"
        : this.dirty
        ? "Unsaved changes"
        : "Saved"
    } · ${this.doc.width_mm} × ${this.doc.height_mm} mm · Grid ${
      this.grid ? "on" : "off"
    }, snap ${this.snap ? "on" : "off"}`;
  }
  undo() {
    if (!this.history.length) return;
    this.future.push(JSON.stringify(this.scenes));
    this.scenes = JSON.parse(this.history.pop());
    this.selected = -1;
    this.changed();
    this.render();
  }
  redo() {
    if (!this.future.length) return;
    this.history.push(JSON.stringify(this.scenes));
    this.scenes = JSON.parse(this.future.pop());
    this.selected = -1;
    this.changed();
    this.render();
  }
  add(type) {
    if (this.doc.builtin)
      return frappe.msgprint(__("Duplicate the protected sample first."));
    this.checkpoint();
    this.items().push({
      type,
      x: 5,
      y: 12,
      width: 25,
      height: type === "line" ? 1 : 10,
      text: type === "text" ? "New text" : "",
      fallback: type === "image" ? "No photo" : "",
      style:
        type === "shape" || type === "line"
          ? { background: "#dae7df" }
          : { "font-size": "9pt", color: "#244b47" },
    });
    this.selected = this.items().length - 1;
    this.changed();
    this.render();
  }
  render() {
    this.status();
    const code = this.doc.editor_mode === "Code";
    this.root.querySelector(".ic-stage").style.display = code ? "none" : "";
    this.props.style.display = code ? "none" : "";
    this.root.querySelector(".ic-code").style.display = code ? "block" : "none";
    if (code) {
      this.renderCode();
      return;
    }
    const scale = (this.zoom * 96) / 25.4;
    const bleed = Number(this.doc.bleed_mm || 0);
    this.bleed = bleed;
    this.scale = scale;
    this.canvas.style.width = (this.doc.width_mm + 2 * bleed) * scale + "px";
    this.canvas.style.height = (this.doc.height_mm + 2 * bleed) * scale + "px";
    this.canvas.style.backgroundImage = this.grid
      ? "linear-gradient(#0001 1px,transparent 1px),linear-gradient(90deg,#0001 1px,transparent 1px)"
      : "";
    this.canvas.style.backgroundSize = `${5 * scale}px ${5 * scale}px`;
    this.canvas.innerHTML = '<div class="ic-safe"></div>';
    this.canvas.querySelector(".ic-safe").style.inset =
      (3 + bleed) * scale + "px";
    this.items().forEach((e, index) => {
      const el = document.createElement("div");
      el.className =
        "ic-element" + (index === this.selected ? " selected" : "");
      el.style.fontSize = `calc(9pt * ${this.zoom})`;
      Object.assign(el.style, e.style || {});
      for (const k of ["x", "y", "width", "height"])
        el.style[{ x: "left", y: "top" }[k] || k] =
          (e[k] + (["x", "y"].includes(k) ? bleed : 0)) * scale + "px";
      // Font and spacing use the same physical-unit scale as geometry.
      for (const k of [
        "font-size",
        "padding",
        "border-radius",
        "letter-spacing",
      ])
        if (e.style?.[k])
          el.style.setProperty(k, `calc(${e.style[k]} * ${this.zoom})`);
      el.style.transform = `rotate(${e.rotation || 0}deg)`;
      let value = this.data[e.field] || e.fallback || e.text || "";
      if (e.date_format && /^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
        const [y, m, d] = value.split("-");
        value =
          e.date_format === "%d/%m/%Y"
            ? `${d}/${m}/${y}`
            : e.date_format === "%d %b %Y"
            ? `${d} ${
                [
                  "Jan",
                  "Feb",
                  "Mar",
                  "Apr",
                  "May",
                  "Jun",
                  "Jul",
                  "Aug",
                  "Sep",
                  "Oct",
                  "Nov",
                  "Dec",
                ][Number(m) - 1]
              } ${y}`
            : value;
      }
      if (e.type === "image") {
        const src = this.data[e.field] || e.src;
        if (src && /^\/(private\/)?files\//.test(src)) {
          const img = document.createElement("img");
          img.src = src;
          img.alt = e.fallback || "Portrait";
          Object.assign(img.style, {
            width: "100%",
            height: "100%",
            objectFit: e.style?.["object-fit"] || "cover",
            pointerEvents: "none",
          });
          el.append(img);
        } else el.textContent = e.fallback || "No photo";
      } else el.textContent = value;
      if (e.visible_if && !this.data[e.visible_if]) el.style.opacity = ".25";
      el.onpointerdown = (event) => this.drag(event, index, el, false);
      if (index === this.selected) {
        const handle = document.createElement("div");
        handle.className = "ic-handle";
        handle.onpointerdown = (event) => {
          event.stopPropagation();
          this.drag(event, index, el, true);
        };
        el.append(handle);
      }
      this.canvas.append(el);
    });
    this.layerList.innerHTML = "<hr><strong>Layers (top first)</strong>";
    [...this.items()].reverse().forEach((e, i) => {
      const index = this.items().length - 1 - i;
      const b = this.button(
        this.layerList,
        `${index + 1}. ${e.field || e.text || e.type}`,
        () => {
          this.selected = index;
          this.render();
        }
      );
      b.classList.add("ic-layer");
    });
    this.properties();
  }
  drag(event, index, el, resize) {
    if (this.doc.builtin) return;
    event.preventDefault();
    this.checkpoint();
    this.selected = index;
    const e = this.items()[index];
    const start = { x: event.clientX, y: event.clientY, ...e };
    el.setPointerCapture(event.pointerId);
    const sx = event.clientX,
      sy = event.clientY;
    const round = (v) =>
      this.snap ? Math.round(v) : Math.round(v * 100) / 100;
    el.onpointermove = (ev) => {
      const dx = (ev.clientX - sx) / this.scale,
        dy = (ev.clientY - sy) / this.scale;
      if (resize) {
        e.width = Math.max(
          1,
          Math.min(
            this.doc.width_mm + this.bleed - e.x,
            round(start.width + dx)
          )
        );
        e.height = Math.max(
          1,
          Math.min(
            this.doc.height_mm + this.bleed - e.y,
            round(start.height + dy)
          )
        );
      } else {
        e.x = Math.max(
          -this.bleed,
          Math.min(
            this.doc.width_mm + this.bleed - e.width,
            round(start.x + dx)
          )
        );
        e.y = Math.max(
          -this.bleed,
          Math.min(
            this.doc.height_mm + this.bleed - e.height,
            round(start.y + dy)
          )
        );
      }
      Object.assign(el.style, {
        left: (e.x + this.bleed) * this.scale + "px",
        top: (e.y + this.bleed) * this.scale + "px",
        width: e.width * this.scale + "px",
        height: e.height * this.scale + "px",
      });
      this.changed();
    };
    el.onpointerup = () => {
      el.onpointermove = null;
      el.onpointerup = null;
      this.render();
      this.canvas.focus();
    };
  }
  properties() {
    this.props.innerHTML = "<strong>Element properties</strong>";
    const e = this.items()[this.selected];
    if (!e) {
      this.props.append(
        document.createTextNode(
          " Select an element to edit. Dashed line shows 3 mm safe area."
        )
      );
      return;
    }
    const change = (k, v) => {
      if (this.doc.builtin) return;
      this.checkpoint();
      e[k] = v;
      this.changed();
      this.render();
    };
    for (const k of ["x", "y", "width", "height", "rotation"])
      this.input(
        this.props,
        k + " (mm; rotation °)",
        e[k] || 0,
        (v) => change(k, v),
        "number"
      );
    this.input(
      this.props,
      "Text",
      e.text,
      (v) => change("text", v),
      "textarea"
    );
    this.select(
      this.props,
      "Field",
      e.field,
      [
        ["", "Static"],
        ...this.fields.map((f) => [
          f.fieldname,
          `${f.label} · ${f.fieldtype} · ${f.source}`,
        ]),
      ],
      (v) => change("field", v)
    );
    this.input(this.props, "Fallback", e.fallback, (v) =>
      change("fallback", v)
    );
    this.select(
      this.props,
      "Date format",
      e.date_format,
      [
        ["", "Original"],
        ["%Y-%m-%d", "YYYY-MM-DD"],
        ["%d %b %Y", "DD Mon YYYY"],
        ["%d/%m/%Y", "DD/MM/YYYY"],
      ],
      (v) => change("date_format", v)
    );
    this.select(
      this.props,
      "Visible when field has value",
      e.visible_if,
      [["", "Always"], ...this.fields.map((f) => [f.fieldname, f.label])],
      (v) => change("visible_if", v)
    );
    if (e.type === "image")
      this.input(this.props, "Uploaded image URL", e.src, (v) =>
        change("src", v)
      );
    for (const [k, def] of Object.entries({
      "font-size": "9pt",
      "font-family": "FreeSerif",
      "font-weight": "normal",
      "line-height": "1.2",
      "text-align": "left",
      color: "#244b47",
      background: "transparent",
      opacity: "1",
      border: "0",
      "border-radius": "0",
      padding: "0",
      "object-fit": "cover",
    }))
      this.input(this.props, k, e.style?.[k] || def, (v) => {
        this.checkpoint();
        e.style = { ...e.style, [k]: v };
        this.changed();
        this.render();
      });
    this.button(this.props, "Duplicate element", () => {
      this.checkpoint();
      this.items().push(JSON.parse(JSON.stringify(e)));
      this.selected = this.items().length - 1;
      this.changed();
      this.render();
    });
    this.button(this.props, "Bring forward", () => this.reorder(1));
    this.button(this.props, "Send backward", () => this.reorder(-1));
    this.button(this.props, "Delete", () => this.remove());
    if (
      e.x < 3 ||
      e.y < 3 ||
      e.x + e.width > this.doc.width_mm - 3 ||
      e.y + e.height > this.doc.height_mm - 3
    )
      this.props.append(
        document.createTextNode(" Warning: element touches the safety margin.")
      );
    if (this.doc.builtin)
      this.props
        .querySelectorAll("input,textarea,select,button")
        .forEach((el) => (el.disabled = true));
  }
  reorder(delta) {
    const i = this.selected,
      j = i + delta;
    if (j < 0 || j >= this.items().length) return;
    this.checkpoint();
    [this.items()[i], this.items()[j]] = [this.items()[j], this.items()[i]];
    this.selected = j;
    this.changed();
    this.render();
  }
  remove() {
    if (this.selected < 0 || this.doc.builtin) return;
    this.checkpoint();
    this.items().splice(this.selected, 1);
    this.selected = -1;
    this.changed();
    this.render();
  }
  key(e) {
    if (e.target !== this.canvas) return;
    if ((e.ctrlKey || e.metaKey) && e.key === "z") {
      e.preventDefault();
      e.shiftKey ? this.redo() : this.undo();
      return;
    }
    if (e.key === "Delete") {
      this.remove();
      return;
    }
    const el = this.items()[this.selected];
    if (!el || this.doc.builtin) return;
    const delta = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[e.key];
    if (delta) {
      e.preventDefault();
      this.checkpoint();
      el.x = Math.max(
        0,
        Math.min(
          this.doc.width_mm - el.width,
          el.x + delta[0] * (e.shiftKey ? 1 : 0.1)
        )
      );
      el.y = Math.max(
        0,
        Math.min(
          this.doc.height_mm - el.height,
          el.y + delta[1] * (e.shiftKey ? 1 : 0.1)
        )
      );
      this.changed();
      this.render();
      this.canvas.focus();
    }
  }
  async save() {
    if (this.doc.builtin) {
      frappe.msgprint(__("Duplicate the protected sample first."));
      return false;
    }
    this.doc.front_layout = JSON.stringify(this.scenes.front);
    this.doc.back_layout = JSON.stringify(this.scenes.back);
    this.doc = await this.call("save_draft", {
      payload: JSON.stringify(this.doc),
    });
    this.dirty = false;
    this.status();
    if (frappe.get_route()[1] !== this.doc.name)
      frappe.set_route("id-card-builder", this.doc.name);
    return true;
  }
  async preview() {
    const tab = window.open("about:blank", "_blank");
    if (!tab) return frappe.msgprint(__("Allow popups to preview PDFs."));
    tab.opener = null;
    try {
      if (!this.doc.builtin && !(await this.save())) {
        tab.close();
        return;
      }
      const url = await this.call("prepare_pdf", {
        name: this.doc.name,
        preview: 1,
        user: this.previewUser || null,
      });
      id_card_designer.deliver_to_tab(tab, url);
    } catch (e) {
      tab.close();
    }
  }
  changeMode(value) {
    if (value === this.doc.editor_mode) return;
    if (value === "Code") {
      frappe.confirm(
        __(
          "Code mode creates a separate draft copy. HTML changes do not convert back into visual layers. Continue?"
        ),
        async () => {
          if (!this.doc.name && !(await this.save())) return;
          const d = await this.call("duplicate_template", {
            name: this.doc.name,
          });
          const esc = frappe.utils.escape_html;
          for (const side of ["front", "back"])
            d[side + "_html"] = this.scenes[side]
              .map(
                (e) =>
                  `<div style="position:absolute;left:${e.x}mm;top:${
                    e.y
                  }mm;width:${e.width}mm;height:${
                    e.height
                  }mm;overflow:hidden;${Object.entries(e.style || {})
                    .map(([k, v]) => `${k}:${esc(String(v))}`)
                    .join(";")}">${
                    e.type === "image"
                      ? `<img src="${
                          e.field === "user_image"
                            ? "{{ user_image }}"
                            : esc(e.src || "")
                        }" style="width:100%;height:100%;object-fit:cover">`
                      : e.field
                      ? "{{ " + e.field + " }}"
                      : esc(e.text || "")
                  }</div>`
              )
              .join("");
          d.editor_mode = "Code";
          const saved = await this.call("save_draft", {
            payload: JSON.stringify(d),
          });
          this.dirty = false;
          frappe.set_route("id-card-builder", saved.name);
        },
        () => this.drawUI()
      );
    } else {
      frappe.msgprint(
        __(
          "Code templates retain their original visual layers but cannot be converted. Duplicate or create a visual template to work with layers."
        )
      );
      this.drawUI();
    }
  }
  renderCode() {
    const panel = this.root.querySelector(".ic-code");
    panel.innerHTML =
      "<p>Only allowlisted {{ field }} placeholders, local uploaded images and scoped CSS. No JavaScript or Jinja. PDF preview validates saved code.</p>";
    for (const [key, mode] of [
      [this.side + "_html", "html"],
      ["shared_css", "css"],
    ]) {
      const label = document.createElement("label");
      label.textContent = key;
      const host = document.createElement("div");
      host.className = "ic-code-editor";
      panel.append(label, host);
      const setup = () => {
        if (!window.ace) return;
        const editor = ace.edit(host);
        editor.session.setMode("ace/mode/" + mode);
        editor.setValue(this.doc[key] || "", -1);
        editor.setReadOnly(!!this.doc.builtin);
        editor.session.on("change", () => {
          this.doc[key] = editor.getValue();
          this.changed();
        });
      };
      if (window.ace) setup();
      else
        frappe.require(
          "/assets/frappe/node_modules/ace-builds/src-min-noconflict/ace.js",
          () => {
            ace.config.set(
              "basePath",
              "/assets/frappe/node_modules/ace-builds/src-min-noconflict/"
            );
            setup();
          }
        );
    }
  }
  async restore() {
    if (!this.doc.name) return;
    const rs = await this.call("list_revisions", { name: this.doc.name });
    if (!rs.length)
      return frappe.msgprint(__("No earlier published revisions."));
    frappe.prompt(
      [
        {
          fieldname: "revision",
          fieldtype: "Select",
          label: "Revision to restore as draft",
          options: rs.map((r) => String(r.revision)),
          reqd: 1,
        },
      ],
      async (v) => {
        this.doc = await this.call("restore_revision", {
          name: this.doc.name,
          revision: v.revision,
        });
        this.scenes = {
          front: JSON.parse(this.doc.front_layout || "[]"),
          back: JSON.parse(this.doc.back_layout || "[]"),
        };
        this.dirty = false;
        this.drawUI();
      }
    );
  }
}
