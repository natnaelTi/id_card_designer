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
    this.selection=[];
    this.dirty = false;
    this.root = document.createElement("div");
    this.root.style.paddingTop = "var(--page-head-height,60px)";
    page.main.append(this.root);
    this.root.innerHTML = `<style>
        @font-face{font-family:FreeSerif;src:url(/assets/id_card_designer/fonts/FreeSerif.ttf)}.ic-toolbar{position:sticky;top:calc(var(--navbar-height,48px) + var(--page-head-height,60px));z-index:5;background:var(--card-bg);padding:8px 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:16px}.ic-layout{display:grid;align-items:start;grid-template-columns:180px minmax(360px,1fr) 230px;gap:16px}.ic-panel{max-height:75vh;overflow:auto;padding:12px;background:var(--card-bg);border:1px solid var(--border-color);border-radius:8px}.ic-panel button{margin:3px}.ic-panel label{display:block;margin:10px 0 3px;font-size:12px}.ic-panel input,.ic-panel select,.ic-panel textarea{width:100%;border:1px solid var(--border-color);border-radius:4px;padding:5px;background:var(--control-bg);color:var(--text-color)}.ic-stage{max-height:75vh;overflow:auto;min-height:420px;padding:28px;background:var(--subtle-fg)}.ic-canvas{position:relative;background:#f5f3e7;box-shadow:0 6px 24px #0002;overflow:hidden;transform-origin:top left;color:#244b47;font-family:FreeSerif,serif;line-height:1.2}.ic-element{position:absolute;box-sizing:border-box;overflow:hidden;overflow-wrap:anywhere;cursor:move;touch-action:none}.ic-element.selected{outline:2px solid #2490ef}.ic-handle{position:absolute;right:0;bottom:0;width:10px;height:10px;background:#2490ef;cursor:se-resize}.ic-safe{position:absolute;inset:3mm;border:1px dashed #b69555;pointer-events:none}.ic-layer{display:block;width:100%;text-align:left}.ic-toolbar button:focus-visible,.ic-panel button:focus-visible,.ic-canvas:focus-visible{outline:3px solid #2490ef;outline-offset:2px}.ic-status{font-size:12px;color:var(--text-muted)}.ic-code{display:none;grid-column:1/-1}.ic-code textarea{width:100%;min-height:180px;font-family:monospace}.ic-code-editor{height:240px;border:1px solid var(--border-color)}@media(max-width:1000px){.ic-layout{grid-template-columns:1fr}.ic-stage{min-height:300px}}
        </style><div class="ic-toolbar"></div><div class="ic-status" role="status"></div><div class="ic-layout"><aside class="ic-panel ic-tools"></aside><main class="ic-stage"><div class="ic-canvas" tabindex="0" aria-label="Card design canvas"></div></main><aside class="ic-panel ic-properties"></aside><section class="ic-code ic-panel"></section></div>`;
    this.toolbar = this.root.querySelector(".ic-toolbar");
    this.canvas = this.root.querySelector(".ic-canvas");
    this.props = this.root.querySelector(".ic-properties");
    this.tools = this.root.querySelector(".ic-tools");
    this.canvas.addEventListener("keydown", (e) => this.key(e));
    this.canvas.addEventListener("click", (e) => {
      if (e.target === this.canvas) {
        this.selected = -1;
        this.selection=[];
        this.render();
      }
    });
    this.root.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        e.stopPropagation();
        this.save().catch(()=>{});
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
    return (await frappe.call({method:"id_card_designer.api." + method,args,silent:method==='save_draft'})).message;
  }
  async load() {
    const name = frappe.get_route()[1];
    if(this.doc && this.doc.name!==name && this.dirty){try{await this.save();}catch{return frappe.set_route('id-card-builder',this.doc.name);}}
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
    await this.setupAutosave();
    this.drawUI();
  }
  button(parent, label, action) {
    const b = document.createElement("button");
    b.className = "btn btn-default btn-sm";
    b.textContent = __(label);
    b.onclick = event => {try{Promise.resolve(action(event)).catch(()=>this.status());}catch(error){frappe.msgprint(error.message);}};
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
    let previous=String(i.value);
    const apply=()=>{if(i.value===previous||type==='number'&&i.value==='')return;previous=i.value;this.editingInput=true;try{fn(type==='number'?Number(i.value):i.value);}finally{this.editingInput=false;}};
    i.oninput=apply;i.onchange=apply;
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
    this.button(this.toolbar,"Back",async()=>{if(!this.doc.builtin)await this.save();frappe.set_route("List","ID Card Template");});
    this.input(this.toolbar, "Title", this.doc.title, (v) => {
      this.doc.title = v;
      this.changed();
    }).disabled = !!this.doc.builtin;
    this.button(this.toolbar,'Retry save',()=>this.save().catch(()=>{}));
    this.button(this.toolbar,'Compare / recover',()=>this.resolveConflict());
    this.button(this.toolbar,'Group',()=>this.group());this.button(this.toolbar,'Ungroup',()=>this.ungroup());
    this.button(this.toolbar,'Lock / unlock',()=>this.toggleLock());
    for(const action of ['left','right','top','bottom','center','middle'])this.button(this.toolbar,'Align '+action,()=>this.align(action));
    this.button(this.toolbar,'Distribute horizontal',()=>this.distribute('x'));this.button(this.toolbar,'Distribute vertical',()=>this.distribute('y'));
    for (const side of ["front", "back"])
      this.button(this.toolbar, side, () => {
        this.side = side;
        this.selected = -1;
        this.selection=[];
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
      this.preflightIssues=p.issues;this.render();
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
            modified:this.doc.modified,
          });
          this.engine.modified=this.doc.modified;
          this.render();
        }
      });
      this.button(this.toolbar, "Set default", async () => {
        if(!this.doc.builtin)await this.save();
        await this.call("set_default_template", { name: this.doc.name });
        this.doc.modified=(await this.call("get_template_for_builder",{name:this.doc.name})).modified;this.engine.modified=this.doc.modified;
        frappe.show_alert(__("Default template updated"));
      });
      this.button(this.toolbar, "Restore revision", () => this.restore());
    }
    this.button(this.toolbar, "Duplicate", async () => {
      if (!this.doc.name) return;
      if(!this.doc.builtin)await this.save();
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
    for (const type of ["text", "richtext", "image", "shape", "line", "qr"])
      this.button(this.tools, "Add " + type, () => this.add(type));
    this.button(this.tools, "Upload image", async () => {
      if (this.doc.builtin)
        return frappe.msgprint(__("Duplicate the protected sample first."));
      if (!this.doc.name && !(await this.save())) return;
      new frappe.ui.FileUploader({
        method:"id_card_designer.api.upload_asset",
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
        this.render();
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
    this.input(this.tools,'Safe margin mm',this.doc.safe_margin_mm??3,v=>{this.doc.safe_margin_mm=v;this.changed();this.render();},'number');
    this.select(this.tools,'Severe preflight errors',this.doc.block_severe?'block':'warn',[['warn','Warn'],['block','Block publish / print']],v=>{this.doc.block_severe=Number(v==='block');this.changed();});
    this.select(this.tools,'Crop marks',this.doc.crop_marks?'yes':'no',[['no','None'],['yes','Outside trim in bleed']],v=>{this.doc.crop_marks=Number(v==='yes');this.changed();});
    this.button(this.tools,'Shared asset library',async()=>{const files=await this.call('list_global_assets');if(!files.length)return frappe.msgprint(__('A manager can add approved images in ID Card Asset.'));frappe.prompt([{fieldname:'image',label:'Institutional image',fieldtype:'Select',options:files.map(x=>({label:x.title,value:x.image})),reqd:1}],v=>{this.add('image');this.items()[this.selected].src=v.image;this.changed();this.render();});});
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
    if(this.doc.builtin)return;
    this.dirty=true;
    this.engine?.mark(this.payload());
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
        ? (this.engine?.state||"Unsaved")
        : (this.engine?.state||"Saved")
    } · ${this.doc.width_mm} × ${this.doc.height_mm} mm · Grid ${
      this.grid ? "on" : "off"
    }, snap ${this.snap ? "on" : "off"}`;
  }
  undo() {
    if (!this.history.length) return;
    this.future.push(JSON.stringify(this.scenes));
    this.scenes = JSON.parse(this.history.pop());
    this.selected = -1;
    this.selection=[];
    this.changed();
    this.render();
  }
  redo() {
    if (!this.future.length) return;
    this.history.push(JSON.stringify(this.scenes));
    this.scenes = JSON.parse(this.future.pop());
    this.selected = -1;
    this.selection=[];
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
    this.selection=[this.selected];
    if(type==='qr')Object.assign(this.items()[this.selected],{width:25,height:25,text:'INSTITUTION-DEMO-0001',qr_error:'M',qr_quiet:4,qr_dark:'#173b35',qr_light:'#ffffff'});
    if(type==='richtext')this.items()[this.selected].text='<p>Rich <b>text</b> · {{ full_name }}</p>';
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
      ((this.doc.safe_margin_mm??3) + bleed) * scale + "px";
    this.items().forEach((e,index)=>{
      const el=this.renderObject(e,index);
      if(this.selection.includes(index)||index===this.selected)el.classList.add('selected');
      el.onpointerdown=event=>this.drag(event,index,el,false);
      if(index===this.selected&&!e.locked){const handle=document.createElement('button');handle.className='ic-handle';handle.setAttribute('aria-label','Resize selected element');handle.onpointerdown=event=>{event.stopPropagation();this.drag(event,index,el,true);};el.append(handle);}
      this.canvas.append(el);
    });
    this.layerList.innerHTML = "<hr><strong>Layers (top first)</strong>";
    [...this.items()].reverse().forEach((e, i) => {
      const index = this.items().length - 1 - i;
      const b = this.button(
        this.layerList,
        `${index + 1}. ${e.field || e.text || e.type}`,
        (event) => {
          this.selectIndex(index,!!event?.shiftKey);
          this.render();
        }
      );
      b.classList.add("ic-layer");
    });
    this.properties();
  }
  drag(event, index, el, resize) {
    if(this.doc.builtin)return;
    if(event.shiftKey||event.metaKey||event.ctrlKey){this.selectIndex(index,true);this.render();return;}
    if(!this.selection.includes(index))this.selection=[index];
    this.selected=index;
    if(this.items()[index].locked){this.render();return;}
    if(this.selection.length>1&&!resize)return this.dragSelection(event);
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
      Object.assign(el.style,{transform:this.objectMatrix(e),width:e.width*this.scale+'px',height:e.height*this.scale+'px'});
      const inner=el.querySelector('.ic-group-content');if(inner)inner.style.transform=`scale(${e.width/e.base_width},${e.height/e.base_height})`;
      this.showGuides(e);
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
    if(this.editingInput)return;
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
      if (this.doc.builtin||e.locked) return;
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
    if(e.type==='qr'){
      this.select(this.props,'QR error correction',e.qr_error||'M',[['L','L'],['M','M'],['Q','Q'],['H','H']],v=>change('qr_error',v));
      this.input(this.props,'QR quiet zone (modules)',e.qr_quiet||4,v=>change('qr_quiet',v),'number');
      this.input(this.props,'QR dark color',e.qr_dark||'#173b35',v=>change('qr_dark',v));this.input(this.props,'QR light color',e.qr_light||'#ffffff',v=>change('qr_light',v));
    }
    if(e.type==='richtext')for(const tag of ['b','em','p'])this.button(this.props,'Insert '+tag,()=>change('text',`<${tag}>${e.text||''}</${tag}>`));
    this.select(this.props,'Intentional bleed',e.allow_bleed?'yes':'no',[['no','No'],['yes','Background/artwork may use bleed']],v=>change('allow_bleed',v==='yes'));
    this.select(this.props,'Intentional clipping',e.allow_clip?'yes':'no',[['no','No'],['yes','Allow intentional mask/clipping']],v=>change('allow_clip',v==='yes'));
    if(e.type==='group')this.select(this.props,'Clip children',e.clip?'yes':'no',[['no','No'],['yes','Mask to group bounds']],v=>change('clip',v==='yes'));
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
    this.button(this.props,"Duplicate element",()=>this.duplicateSelection());
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
    if (this.doc.builtin||e.locked)
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
  remove(){if(this.doc.builtin)return;const indices=this.selectedIndices().filter(i=>!this.items()[i].locked);this.checkpoint();this.scenes[this.side]=this.items().filter((_,i)=>!indices.includes(i));this.selected=-1;this.selection=[];this.changed();this.render();}
  duplicateSelection(){if(this.doc.builtin)return;this.checkpoint();const copies=this.selectedIndices().map(i=>({...structuredClone(this.items()[i]),locked:false,x:this.items()[i].x+1,y:this.items()[i].y+1}));const first=this.items().length;this.items().push(...copies);this.selection=copies.map((_,i)=>first+i);this.selected=first;this.changed();this.render();}
  key(e) {
    if (e.target !== this.canvas) return;
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='g'){e.preventDefault();e.shiftKey?this.ungroup():this.group();return;}
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='d'){e.preventDefault();this.duplicateSelection();return;}
    if((e.key==='PageDown'||e.key==='PageUp')&&this.items().length){e.preventDefault();const index=(this.selected+(e.key==='PageUp'?-1:1)+this.items().length)%this.items().length;this.selectIndex(index, false);this.render();this.canvas.focus();return;}

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
    if (!el || this.doc.builtin || el.locked) return;
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
    if(this.doc.builtin){frappe.msgprint(__('Duplicate the protected sample first.'));return false;}
    if(!this.doc.name&&!this.dirty)this.changed();
    await this.engine.flush();
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
  changeMode(value){
    if(value===this.doc.editor_mode)return;
    if(value!=='Code'){frappe.msgprint(__('Arbitrary HTML cannot be converted to visual layers. Open the preserved visual source or duplicate a visual template.'));return this.drawUI();}
    frappe.confirm(__('Create a separate Code draft? Advanced HTML edits do not convert back to layers.'),async()=>{
      if(!this.doc.builtin)await this.save();
      const doc=await this.call('convert_to_code',{name:this.doc.name});
      this.dirty=false;this.engine?.dispose();frappe.set_route('id-card-builder',doc.name);
    },()=>this.drawUI());
  }
  renderCode() {
    const panel = this.root.querySelector(".ic-code");
    for(const editor of this.codeEditors||[])editor.destroy();this.codeEditors=[];
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
        if (!window.ace||!host.isConnected) return;
        const editor = ace.edit(host);
        this.codeEditors.push(editor);
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
    if(!this.doc.builtin)await this.save();
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
        this.engine.reset(this.doc);
        this.drawUI();
      }
    );
  }  payload(){return {...this.doc,front_layout:JSON.stringify(this.scenes.front),back_layout:JSON.stringify(this.scenes.back)};}
  async setupAutosave(){
    this.engine?.dispose();
    let journal=null;
    if(!this.doc.builtin&&window.crypto?.subtle){const key=await this.call('draft_key');journal=new IDCardAutosave.Journal(sessionStorage,'id-card-draft:'+frappe.session.user+':'+(this.doc.name||'new'),key);}
    this.journal=journal;
    this.engine=new IDCardAutosave.Queue({
      save:payload=>this.call('save_draft',{payload:JSON.stringify(payload)}),journal,online:()=>navigator.onLine,
      onState:()=>{this.dirty=this.engine.saved<this.engine.version;this.status();},
      onSaved:async(result,latest)=>{
        for(const field of ['name','modified','revision','status','draft_unpublished'])this.doc[field]=result[field];
        this.dirty=!latest;
        if(frappe.get_route()[0]==='id-card-builder'&&frappe.get_route()[1]!==this.doc.name)frappe.set_route('id-card-builder',this.doc.name);
      }
    });this.engine.modified=this.doc.modified;
    if(!this.navigationBound){
      this.navigationBound=true;
      window.addEventListener('online',()=>this.engine.flush().catch(()=>{}));
      window.addEventListener('offline',()=>{if(this.dirty)this.engine.setState('Offline/Disconnected');});
      document.addEventListener('click',async event=>{
        const link=event.target.closest('a[href]');
        if(!link||!this.dirty||this.navigationPass||!this.root.offsetParent)return;
        event.preventDefault();event.stopImmediatePropagation();
        try{await this.save();this.navigationPass=true;link.click();queueMicrotask(()=>this.navigationPass=false);}catch{frappe.msgprint(__('Draft not saved. Retry or compare before leaving.'));}
      },true);
      frappe.router.on('change',()=>{if(this.dirty&&frappe.get_route()[0]!=='id-card-builder')this.save().catch(()=>{frappe.set_route('id-card-builder',this.doc.name);frappe.msgprint(__('Navigation stopped: unsaved draft. Retry or compare.'));});});
    }
    const recovered=await journal?.read();
    if(recovered)setTimeout(()=>this.compareDraft(recovered),100);
  }
  async resolveConflict(){if(!this.doc.name)return;const remote=await this.call('get_template_for_builder',{name:this.doc.name});this.compareDraft(this.payload(),remote);}
  compareDraft(local,remote=this.doc){
    const d=new frappe.ui.Dialog({title:__('Draft recovery / conflict comparison'),fields:[{fieldname:'comparison',fieldtype:'HTML'}],primary_action_label:__('Save conflict copy'),primary_action:async()=>{
      const copy={...local,title:(local.title||'Design')+' (recovered copy)'};delete copy.name;delete copy.modified;
      this.doc=copy;this.scenes={front:JSON.parse(copy.front_layout||'[]'),back:JSON.parse(copy.back_layout||'[]')};this.engine.reset({});this.changed();await this.save();d.hide();this.drawUI();
    }});
    const host=d.fields_dict.comparison.$wrapper[0];
    for(const [label,value] of [['Latest saved draft',remote],['Encrypted/local unsaved draft',local]]){const p=document.createElement('p');p.textContent=label;const area=document.createElement('textarea');area.setAttribute('aria-label',label);area.readOnly=true;area.style.cssText='width:100%;height:150px;font-family:monospace';area.value=JSON.stringify(value,null,2);host.append(p,area);}
    d.set_secondary_action_label(__('Reload saved draft'));
    d.set_secondary_action(async()=>{await this.journal?.clear();this.doc=remote;this.scenes={front:JSON.parse(remote.front_layout||'[]'),back:JSON.parse(remote.back_layout||'[]')};this.engine.reset(remote);this.dirty=false;this.selection=[];d.hide();this.drawUI();});d.show();
  }
  selectIndex(index,toggle=false){if(toggle){this.selection=this.selection.includes(index)?this.selection.filter(i=>i!==index):[...this.selection,index];}else this.selection=[index];this.selected=this.selection.at(-1)??-1;}
  selectedIndices(){return (this.selection.length?this.selection:[this.selected]).filter(i=>i>=0&&i<this.items().length);}
  group(){if(this.doc.builtin)return;this.checkpoint();try{this.selected=IDCardScene.group(this.items(),this.selectedIndices());this.selection=[this.selected];this.changed();this.render();}catch(e){frappe.msgprint(e.message);}}
  ungroup(){if(this.doc.builtin)return;this.checkpoint();try{this.selection=IDCardScene.ungroup(this.items(),this.selected);this.selected=this.selection[0];this.changed();this.render();}catch(e){frappe.msgprint(e.message);}}
  toggleLock(){if(this.doc.builtin)return;this.checkpoint();const indices=this.selectedIndices(),lock=indices.some(i=>!this.items()[i].locked);indices.forEach(i=>this.items()[i].locked=lock);this.changed();this.render();}
  align(mode){if(this.doc.builtin)return;this.checkpoint();IDCardScene.align(this.items(),this.selectedIndices(),mode);this.changed();this.render();}
  distribute(axis){if(this.doc.builtin)return;this.checkpoint();IDCardScene.distribute(this.items(),this.selectedIndices(),axis);this.changed();this.render();}
  dragSelection(event){event.preventDefault();this.checkpoint();const indices=this.selectedIndices().filter(i=>!this.items()[i].locked),original=indices.map(i=>({x:this.items()[i].x,y:this.items()[i].y}));const x=event.clientX,y=event.clientY;const move=ev=>{indices.forEach((i,k)=>{this.items()[i].x=original[k].x+(ev.clientX-x)/this.scale;this.items()[i].y=original[k].y+(ev.clientY-y)/this.scale;});this.changed();this.render();};const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);this.canvas.focus();};window.addEventListener('pointermove',move);window.addEventListener('pointerup',up);}
  objectMatrix(e,top=true){const m=IDCardScene.matrix(e);if(top){m[4]+=this.bleed||0;m[5]+=this.bleed||0;}return `matrix(${m.map((v,i)=>i>3?v*this.scale:v).join(',')})`;}
  renderObject(e,index,top=true,path=String(index)){
    const el=document.createElement('div');el.className='ic-element';el.dataset.icPath=path;el.setAttribute('aria-label',(e.locked?'Locked ':'')+e.type+' element '+path);
    Object.assign(el.style,{left:0,top:0,width:e.width*this.scale+'px',height:e.height*this.scale+'px',fontSize:`calc(9pt * ${this.zoom})`,transformOrigin:'0 0',transform:this.objectMatrix(e,top),overflow:e.type==='group'&&!e.clip?'visible':'hidden'});
    for(const [key,value] of Object.entries(e.style||{}))el.style.setProperty(key,String(value).replace(/([0-9.]+)(pt|px|mm|cm)/g,(_,n,u)=>`calc(${n}${u} * ${this.zoom})`));
    if(this.preflightIssues?.some(x=>x.severity==='error'&&(x.path===path||x.path?.startsWith(path+'.'))))el.style.outline='2px solid #b42318';
    if(e.type==='group'){
      const inner=document.createElement('div');inner.className='ic-group-content';Object.assign(inner.style,{position:'absolute',width:(e.base_width||e.width)*this.scale+'px',height:(e.base_height||e.height)*this.scale+'px',transformOrigin:'0 0',transform:`scale(${e.width/(e.base_width||e.width)},${e.height/(e.base_height||e.height)})`});
      e.children.forEach((c,i)=>inner.append(this.renderObject(c,i,false,path+'.'+i)));el.append(inner);
    }else if(e.type==='image'){
      const src=this.data[e.field]||e.src;
      if(src&&/^\/(private\/)?files\//.test(src)){const img=document.createElement('img');img.src=src;img.alt=e.fallback||'Portrait';Object.assign(img.style,{width:'100%',height:'100%',objectFit:e.style?.['object-fit']||'cover',pointerEvents:'none'});el.append(img);}else el.textContent=e.fallback||'No photo';
    }else if(e.type==='qr'){
      el.textContent='QR preview…';this.qrCache=this.qrCache||new Map();const key=JSON.stringify([e,this.previewUser]);
      if(!this.qrCache.has(key))this.qrCache.set(key,this.call('qr_preview',{element:JSON.stringify(e),user:this.previewUser||null}));
      this.qrCache.get(key).then(src=>{if(!el.isConnected)return;el.textContent='';const img=document.createElement('img');img.src=src;img.alt='Organizational QR';img.style.cssText='width:100%;height:100%;object-fit:contain;pointer-events:none';el.append(img);}).catch(()=>{el.textContent='Invalid QR — check preflight';});
    }else if(e.type==='richtext'){
      const parsed=new DOMParser().parseFromString(e.text||'','text/html');const allowed=new Set(['DIV','SPAN','P','B','STRONG','EM','I','BR','H1','H2','H3','SMALL']);
      const copy=(source,target)=>{for(const n of source.childNodes){if(n.nodeType===3)target.append(document.createTextNode(n.textContent.replace(/{{\s*([a-z_]+)\s*}}/g,(_,field)=>this.data[field]||'')));else if(n.nodeType===1&&allowed.has(n.tagName)){const child=document.createElement(n.tagName.toLowerCase());for(const property of ['color','font-size','font-weight','text-align']){const value=n.style.getPropertyValue(property);if(value&&!/url|\\|@|[<>]/i.test(value))child.style.setProperty(property,value);}copy(n,child);target.append(child);}}};copy(parsed.body,el);
    }else{
      let value=this.data[e.field]||e.fallback||e.text||'';
      if(e.date_format&&/^\d{4}-\d{2}-\d{2}$/.test(value)){const [y,m,d]=value.split('-');if(e.date_format==='%d/%m/%Y')value=`${d}/${m}/${y}`;if(e.date_format==='%d %b %Y')value=`${d} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m)-1]} ${y}`;}
      el.textContent=value;
    }
    if(e.visible_if&&!this.data[e.visible_if])el.style.opacity='.25';
    return el;
  }
  showGuides(e){
    this.canvas.querySelectorAll('.ic-guide').forEach(x=>x.remove());if(!this.snap)return;
    for(const [axis,size] of [['x','width'],['y','height']]){
      const dimension=axis==='x'?this.doc.width_mm:this.doc.height_mm;
      const targets=[0,dimension/2,dimension,...this.items().filter(x=>x!==e).flatMap(x=>[x[axis],x[axis]+x[size]/2,x[axis]+x[size]])];
      const edges=[0,e[size]/2,e[size]];
      let found=null;for(const offset of edges)for(const target of targets)if(Math.abs(e[axis]+offset-target)<.5){e[axis]=target-offset;found=target;}
      if(found!==null){const guide=document.createElement('div');guide.className='ic-guide';guide.style.cssText=axis==='x'?`position:absolute;pointer-events:none;left:${(found+this.bleed)*this.scale}px;top:0;height:100%;border-left:1px solid #2490ef`:`position:absolute;pointer-events:none;top:${(found+this.bleed)*this.scale}px;left:0;width:100%;border-top:1px solid #2490ef`;this.canvas.append(guide);}
    }
    const el=this.canvas.querySelector(`[data-ic-path="${this.selected}"]`);if(el)el.style.transform=this.objectMatrix(e);
  }

}
