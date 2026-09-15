/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const X = globalThis, tt = X.ShadowRoot && (X.ShadyCSS === void 0 || X.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, et = Symbol(), at = /* @__PURE__ */ new WeakMap();
let bt = class {
  constructor(t, i, e) {
    if (this._$cssResult$ = !0, e !== et) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t, this.t = i;
  }
  get styleSheet() {
    let t = this.o;
    const i = this.t;
    if (tt && t === void 0) {
      const e = i !== void 0 && i.length === 1;
      e && (t = at.get(i)), t === void 0 && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), e && at.set(i, t));
    }
    return t;
  }
  toString() {
    return this.cssText;
  }
};
const Ht = (o) => new bt(typeof o == "string" ? o : o + "", void 0, et), Mt = (o, ...t) => {
  const i = o.length === 1 ? o[0] : t.reduce((e, s, r) => e + ((n) => {
    if (n._$cssResult$ === !0) return n.cssText;
    if (typeof n == "number") return n;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + n + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s) + o[r + 1], o[0]);
  return new bt(i, o, et);
}, Ot = (o, t) => {
  if (tt) o.adoptedStyleSheets = t.map((i) => i instanceof CSSStyleSheet ? i : i.styleSheet);
  else for (const i of t) {
    const e = document.createElement("style"), s = X.litNonce;
    s !== void 0 && e.setAttribute("nonce", s), e.textContent = i.cssText, o.appendChild(e);
  }
}, lt = tt ? (o) => o : (o) => o instanceof CSSStyleSheet ? ((t) => {
  let i = "";
  for (const e of t.cssRules) i += e.cssText;
  return Ht(i);
})(o) : o;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const { is: Ut, defineProperty: Dt, getOwnPropertyDescriptor: Nt, getOwnPropertyNames: It, getOwnPropertySymbols: jt, getPrototypeOf: Lt } = Object, w = globalThis, dt = w.trustedTypes, Bt = dt ? dt.emptyScript : "", Z = w.reactiveElementPolyfillSupport, U = (o, t) => o, W = { toAttribute(o, t) {
  switch (t) {
    case Boolean:
      o = o ? Bt : null;
      break;
    case Object:
    case Array:
      o = o == null ? o : JSON.stringify(o);
  }
  return o;
}, fromAttribute(o, t) {
  let i = o;
  switch (t) {
    case Boolean:
      i = o !== null;
      break;
    case Number:
      i = o === null ? null : Number(o);
      break;
    case Object:
    case Array:
      try {
        i = JSON.parse(o);
      } catch {
        i = null;
      }
  }
  return i;
} }, it = (o, t) => !Ut(o, t), ct = { attribute: !0, type: String, converter: W, reflect: !1, useDefault: !1, hasChanged: it };
Symbol.metadata ?? (Symbol.metadata = Symbol("metadata")), w.litPropertyMetadata ?? (w.litPropertyMetadata = /* @__PURE__ */ new WeakMap());
let z = class extends HTMLElement {
  static addInitializer(t) {
    this._$Ei(), (this.l ?? (this.l = [])).push(t);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t, i = ct) {
    if (i.state && (i.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((i = Object.create(i)).wrapped = !0), this.elementProperties.set(t, i), !i.noAccessor) {
      const e = Symbol(), s = this.getPropertyDescriptor(t, e, i);
      s !== void 0 && Dt(this.prototype, t, s);
    }
  }
  static getPropertyDescriptor(t, i, e) {
    const { get: s, set: r } = Nt(this.prototype, t) ?? { get() {
      return this[i];
    }, set(n) {
      this[i] = n;
    } };
    return { get: s, set(n) {
      const l = s == null ? void 0 : s.call(this);
      r == null || r.call(this, n), this.requestUpdate(t, l, e);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(t) {
    return this.elementProperties.get(t) ?? ct;
  }
  static _$Ei() {
    if (this.hasOwnProperty(U("elementProperties"))) return;
    const t = Lt(this);
    t.finalize(), t.l !== void 0 && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(U("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(U("properties"))) {
      const i = this.properties, e = [...It(i), ...jt(i)];
      for (const s of e) this.createProperty(s, i[s]);
    }
    const t = this[Symbol.metadata];
    if (t !== null) {
      const i = litPropertyMetadata.get(t);
      if (i !== void 0) for (const [e, s] of i) this.elementProperties.set(e, s);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [i, e] of this.elementProperties) {
      const s = this._$Eu(i, e);
      s !== void 0 && this._$Eh.set(s, i);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t) {
    const i = [];
    if (Array.isArray(t)) {
      const e = new Set(t.flat(1 / 0).reverse());
      for (const s of e) i.unshift(lt(s));
    } else t !== void 0 && i.push(lt(t));
    return i;
  }
  static _$Eu(t, i) {
    const e = i.attribute;
    return e === !1 ? void 0 : typeof e == "string" ? e : typeof t == "string" ? t.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    var t;
    this._$ES = new Promise((i) => this.enableUpdating = i), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), (t = this.constructor.l) == null || t.forEach((i) => i(this));
  }
  addController(t) {
    var i;
    (this._$EO ?? (this._$EO = /* @__PURE__ */ new Set())).add(t), this.renderRoot !== void 0 && this.isConnected && ((i = t.hostConnected) == null || i.call(t));
  }
  removeController(t) {
    var i;
    (i = this._$EO) == null || i.delete(t);
  }
  _$E_() {
    const t = /* @__PURE__ */ new Map(), i = this.constructor.elementProperties;
    for (const e of i.keys()) this.hasOwnProperty(e) && (t.set(e, this[e]), delete this[e]);
    t.size > 0 && (this._$Ep = t);
  }
  createRenderRoot() {
    const t = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return Ot(t, this.constructor.elementStyles), t;
  }
  connectedCallback() {
    var t;
    this.renderRoot ?? (this.renderRoot = this.createRenderRoot()), this.enableUpdating(!0), (t = this._$EO) == null || t.forEach((i) => {
      var e;
      return (e = i.hostConnected) == null ? void 0 : e.call(i);
    });
  }
  enableUpdating(t) {
  }
  disconnectedCallback() {
    var t;
    (t = this._$EO) == null || t.forEach((i) => {
      var e;
      return (e = i.hostDisconnected) == null ? void 0 : e.call(i);
    });
  }
  attributeChangedCallback(t, i, e) {
    this._$AK(t, e);
  }
  _$ET(t, i) {
    var r;
    const e = this.constructor.elementProperties.get(t), s = this.constructor._$Eu(t, e);
    if (s !== void 0 && e.reflect === !0) {
      const n = (((r = e.converter) == null ? void 0 : r.toAttribute) !== void 0 ? e.converter : W).toAttribute(i, e.type);
      this._$Em = t, n == null ? this.removeAttribute(s) : this.setAttribute(s, n), this._$Em = null;
    }
  }
  _$AK(t, i) {
    var r, n;
    const e = this.constructor, s = e._$Eh.get(t);
    if (s !== void 0 && this._$Em !== s) {
      const l = e.getPropertyOptions(s), a = typeof l.converter == "function" ? { fromAttribute: l.converter } : ((r = l.converter) == null ? void 0 : r.fromAttribute) !== void 0 ? l.converter : W;
      this._$Em = s;
      const c = a.fromAttribute(i, l.type);
      this[s] = c ?? ((n = this._$Ej) == null ? void 0 : n.get(s)) ?? c, this._$Em = null;
    }
  }
  requestUpdate(t, i, e, s = !1, r) {
    var n;
    if (t !== void 0) {
      const l = this.constructor;
      if (s === !1 && (r = this[t]), e ?? (e = l.getPropertyOptions(t)), !((e.hasChanged ?? it)(r, i) || e.useDefault && e.reflect && r === ((n = this._$Ej) == null ? void 0 : n.get(t)) && !this.hasAttribute(l._$Eu(t, e)))) return;
      this.C(t, i, e);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(t, i, { useDefault: e, reflect: s, wrapped: r }, n) {
    e && !(this._$Ej ?? (this._$Ej = /* @__PURE__ */ new Map())).has(t) && (this._$Ej.set(t, n ?? i ?? this[t]), r !== !0 || n !== void 0) || (this._$AL.has(t) || (this.hasUpdated || e || (i = void 0), this._$AL.set(t, i)), s === !0 && this._$Em !== t && (this._$Eq ?? (this._$Eq = /* @__PURE__ */ new Set())).add(t));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (i) {
      Promise.reject(i);
    }
    const t = this.scheduleUpdate();
    return t != null && await t, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    var e;
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ?? (this.renderRoot = this.createRenderRoot()), this._$Ep) {
        for (const [r, n] of this._$Ep) this[r] = n;
        this._$Ep = void 0;
      }
      const s = this.constructor.elementProperties;
      if (s.size > 0) for (const [r, n] of s) {
        const { wrapped: l } = n, a = this[r];
        l !== !0 || this._$AL.has(r) || a === void 0 || this.C(r, void 0, n, a);
      }
    }
    let t = !1;
    const i = this._$AL;
    try {
      t = this.shouldUpdate(i), t ? (this.willUpdate(i), (e = this._$EO) == null || e.forEach((s) => {
        var r;
        return (r = s.hostUpdate) == null ? void 0 : r.call(s);
      }), this.update(i)) : this._$EM();
    } catch (s) {
      throw t = !1, this._$EM(), s;
    }
    t && this._$AE(i);
  }
  willUpdate(t) {
  }
  _$AE(t) {
    var i;
    (i = this._$EO) == null || i.forEach((e) => {
      var s;
      return (s = e.hostUpdated) == null ? void 0 : s.call(e);
    }), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(t)), this.updated(t);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(t) {
    return !0;
  }
  update(t) {
    this._$Eq && (this._$Eq = this._$Eq.forEach((i) => this._$ET(i, this[i]))), this._$EM();
  }
  updated(t) {
  }
  firstUpdated(t) {
  }
};
z.elementStyles = [], z.shadowRootOptions = { mode: "open" }, z[U("elementProperties")] = /* @__PURE__ */ new Map(), z[U("finalized")] = /* @__PURE__ */ new Map(), Z == null || Z({ ReactiveElement: z }), (w.reactiveElementVersions ?? (w.reactiveElementVersions = [])).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const D = globalThis, ht = (o) => o, q = D.trustedTypes, pt = q ? q.createPolicy("lit-html", { createHTML: (o) => o }) : void 0, xt = "$lit$", y = `lit$${Math.random().toFixed(9).slice(2)}$`, vt = "?" + y, Vt = `<${vt}>`, P = document, I = () => P.createComment(""), j = (o) => o === null || typeof o != "object" && typeof o != "function", st = Array.isArray, Xt = (o) => st(o) || typeof (o == null ? void 0 : o[Symbol.iterator]) == "function", J = `[ 	
\f\r]`, O = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, ut = /-->/g, ft = />/g, E = RegExp(`>|${J}(?:([^\\s"'>=/]+)(${J}*=${J}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), gt = /'/g, mt = /"/g, yt = /^(?:script|style|textarea|title)$/i, wt = (o) => (t, ...i) => ({ _$litType$: o, strings: t, values: i }), _ = wt(1), R = wt(2), H = Symbol.for("lit-noChange"), f = Symbol.for("lit-nothing"), _t = /* @__PURE__ */ new WeakMap(), C = P.createTreeWalker(P, 129);
function At(o, t) {
  if (!st(o) || !o.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return pt !== void 0 ? pt.createHTML(t) : t;
}
const Wt = (o, t) => {
  const i = o.length - 1, e = [];
  let s, r = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", n = O;
  for (let l = 0; l < i; l++) {
    const a = o[l];
    let c, h, d = -1, u = 0;
    for (; u < a.length && (n.lastIndex = u, h = n.exec(a), h !== null); ) u = n.lastIndex, n === O ? h[1] === "!--" ? n = ut : h[1] !== void 0 ? n = ft : h[2] !== void 0 ? (yt.test(h[2]) && (s = RegExp("</" + h[2], "g")), n = E) : h[3] !== void 0 && (n = E) : n === E ? h[0] === ">" ? (n = s ?? O, d = -1) : h[1] === void 0 ? d = -2 : (d = n.lastIndex - h[2].length, c = h[1], n = h[3] === void 0 ? E : h[3] === '"' ? mt : gt) : n === mt || n === gt ? n = E : n === ut || n === ft ? n = O : (n = E, s = void 0);
    const p = n === E && o[l + 1].startsWith("/>") ? " " : "";
    r += n === O ? a + Vt : d >= 0 ? (e.push(c), a.slice(0, d) + xt + a.slice(d) + y + p) : a + y + (d === -2 ? l : p);
  }
  return [At(o, r + (o[i] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), e];
};
class L {
  constructor({ strings: t, _$litType$: i }, e) {
    let s;
    this.parts = [];
    let r = 0, n = 0;
    const l = t.length - 1, a = this.parts, [c, h] = Wt(t, i);
    if (this.el = L.createElement(c, e), C.currentNode = this.el.content, i === 2 || i === 3) {
      const d = this.el.content.firstChild;
      d.replaceWith(...d.childNodes);
    }
    for (; (s = C.nextNode()) !== null && a.length < l; ) {
      if (s.nodeType === 1) {
        if (s.hasAttributes()) for (const d of s.getAttributeNames()) if (d.endsWith(xt)) {
          const u = h[n++], p = s.getAttribute(d).split(y), g = /([.?@])?(.*)/.exec(u);
          a.push({ type: 1, index: r, name: g[2], strings: p, ctor: g[1] === "." ? Gt : g[1] === "?" ? Yt : g[1] === "@" ? Zt : G }), s.removeAttribute(d);
        } else d.startsWith(y) && (a.push({ type: 6, index: r }), s.removeAttribute(d));
        if (yt.test(s.tagName)) {
          const d = s.textContent.split(y), u = d.length - 1;
          if (u > 0) {
            s.textContent = q ? q.emptyScript : "";
            for (let p = 0; p < u; p++) s.append(d[p], I()), C.nextNode(), a.push({ type: 2, index: ++r });
            s.append(d[u], I());
          }
        }
      } else if (s.nodeType === 8) if (s.data === vt) a.push({ type: 2, index: r });
      else {
        let d = -1;
        for (; (d = s.data.indexOf(y, d + 1)) !== -1; ) a.push({ type: 7, index: r }), d += y.length - 1;
      }
      r++;
    }
  }
  static createElement(t, i) {
    const e = P.createElement("template");
    return e.innerHTML = t, e;
  }
}
function M(o, t, i = o, e) {
  var n, l;
  if (t === H) return t;
  let s = e !== void 0 ? (n = i._$Co) == null ? void 0 : n[e] : i._$Cl;
  const r = j(t) ? void 0 : t._$litDirective$;
  return (s == null ? void 0 : s.constructor) !== r && ((l = s == null ? void 0 : s._$AO) == null || l.call(s, !1), r === void 0 ? s = void 0 : (s = new r(o), s._$AT(o, i, e)), e !== void 0 ? (i._$Co ?? (i._$Co = []))[e] = s : i._$Cl = s), s !== void 0 && (t = M(o, s._$AS(o, t.values), s, e)), t;
}
class qt {
  constructor(t, i) {
    this._$AV = [], this._$AN = void 0, this._$AD = t, this._$AM = i;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(t) {
    const { el: { content: i }, parts: e } = this._$AD, s = ((t == null ? void 0 : t.creationScope) ?? P).importNode(i, !0);
    C.currentNode = s;
    let r = C.nextNode(), n = 0, l = 0, a = e[0];
    for (; a !== void 0; ) {
      if (n === a.index) {
        let c;
        a.type === 2 ? c = new B(r, r.nextSibling, this, t) : a.type === 1 ? c = new a.ctor(r, a.name, a.strings, this, t) : a.type === 6 && (c = new Jt(r, this, t)), this._$AV.push(c), a = e[++l];
      }
      n !== (a == null ? void 0 : a.index) && (r = C.nextNode(), n++);
    }
    return C.currentNode = P, s;
  }
  p(t) {
    let i = 0;
    for (const e of this._$AV) e !== void 0 && (e.strings !== void 0 ? (e._$AI(t, e, i), i += e.strings.length - 2) : e._$AI(t[i])), i++;
  }
}
class B {
  get _$AU() {
    var t;
    return ((t = this._$AM) == null ? void 0 : t._$AU) ?? this._$Cv;
  }
  constructor(t, i, e, s) {
    this.type = 2, this._$AH = f, this._$AN = void 0, this._$AA = t, this._$AB = i, this._$AM = e, this.options = s, this._$Cv = (s == null ? void 0 : s.isConnected) ?? !0;
  }
  get parentNode() {
    let t = this._$AA.parentNode;
    const i = this._$AM;
    return i !== void 0 && (t == null ? void 0 : t.nodeType) === 11 && (t = i.parentNode), t;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(t, i = this) {
    t = M(this, t, i), j(t) ? t === f || t == null || t === "" ? (this._$AH !== f && this._$AR(), this._$AH = f) : t !== this._$AH && t !== H && this._(t) : t._$litType$ !== void 0 ? this.$(t) : t.nodeType !== void 0 ? this.T(t) : Xt(t) ? this.k(t) : this._(t);
  }
  O(t) {
    return this._$AA.parentNode.insertBefore(t, this._$AB);
  }
  T(t) {
    this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
  }
  _(t) {
    this._$AH !== f && j(this._$AH) ? this._$AA.nextSibling.data = t : this.T(P.createTextNode(t)), this._$AH = t;
  }
  $(t) {
    var r;
    const { values: i, _$litType$: e } = t, s = typeof e == "number" ? this._$AC(t) : (e.el === void 0 && (e.el = L.createElement(At(e.h, e.h[0]), this.options)), e);
    if (((r = this._$AH) == null ? void 0 : r._$AD) === s) this._$AH.p(i);
    else {
      const n = new qt(s, this), l = n.u(this.options);
      n.p(i), this.T(l), this._$AH = n;
    }
  }
  _$AC(t) {
    let i = _t.get(t.strings);
    return i === void 0 && _t.set(t.strings, i = new L(t)), i;
  }
  k(t) {
    st(this._$AH) || (this._$AH = [], this._$AR());
    const i = this._$AH;
    let e, s = 0;
    for (const r of t) s === i.length ? i.push(e = new B(this.O(I()), this.O(I()), this, this.options)) : e = i[s], e._$AI(r), s++;
    s < i.length && (this._$AR(e && e._$AB.nextSibling, s), i.length = s);
  }
  _$AR(t = this._$AA.nextSibling, i) {
    var e;
    for ((e = this._$AP) == null ? void 0 : e.call(this, !1, !0, i); t !== this._$AB; ) {
      const s = ht(t).nextSibling;
      ht(t).remove(), t = s;
    }
  }
  setConnected(t) {
    var i;
    this._$AM === void 0 && (this._$Cv = t, (i = this._$AP) == null || i.call(this, t));
  }
}
class G {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t, i, e, s, r) {
    this.type = 1, this._$AH = f, this._$AN = void 0, this.element = t, this.name = i, this._$AM = s, this.options = r, e.length > 2 || e[0] !== "" || e[1] !== "" ? (this._$AH = Array(e.length - 1).fill(new String()), this.strings = e) : this._$AH = f;
  }
  _$AI(t, i = this, e, s) {
    const r = this.strings;
    let n = !1;
    if (r === void 0) t = M(this, t, i, 0), n = !j(t) || t !== this._$AH && t !== H, n && (this._$AH = t);
    else {
      const l = t;
      let a, c;
      for (t = r[0], a = 0; a < r.length - 1; a++) c = M(this, l[e + a], i, a), c === H && (c = this._$AH[a]), n || (n = !j(c) || c !== this._$AH[a]), c === f ? t = f : t !== f && (t += (c ?? "") + r[a + 1]), this._$AH[a] = c;
    }
    n && !s && this.j(t);
  }
  j(t) {
    t === f ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
  }
}
class Gt extends G {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t) {
    this.element[this.name] = t === f ? void 0 : t;
  }
}
class Yt extends G {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t) {
    this.element.toggleAttribute(this.name, !!t && t !== f);
  }
}
class Zt extends G {
  constructor(t, i, e, s, r) {
    super(t, i, e, s, r), this.type = 5;
  }
  _$AI(t, i = this) {
    if ((t = M(this, t, i, 0) ?? f) === H) return;
    const e = this._$AH, s = t === f && e !== f || t.capture !== e.capture || t.once !== e.once || t.passive !== e.passive, r = t !== f && (e === f || s);
    s && this.element.removeEventListener(this.name, this, e), r && this.element.addEventListener(this.name, this, t), this._$AH = t;
  }
  handleEvent(t) {
    var i;
    typeof this._$AH == "function" ? this._$AH.call(((i = this.options) == null ? void 0 : i.host) ?? this.element, t) : this._$AH.handleEvent(t);
  }
}
class Jt {
  constructor(t, i, e) {
    this.element = t, this.type = 6, this._$AN = void 0, this._$AM = i, this.options = e;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t) {
    M(this, t);
  }
}
const K = D.litHtmlPolyfillSupport;
K == null || K(L, B), (D.litHtmlVersions ?? (D.litHtmlVersions = [])).push("3.3.3");
const Kt = (o, t, i) => {
  const e = (i == null ? void 0 : i.renderBefore) ?? t;
  let s = e._$litPart$;
  if (s === void 0) {
    const r = (i == null ? void 0 : i.renderBefore) ?? null;
    e._$litPart$ = s = new B(t.insertBefore(I(), r), r, void 0, i ?? {});
  }
  return s._$AI(o), s;
};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const k = globalThis;
class N extends z {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    var i;
    const t = super.createRenderRoot();
    return (i = this.renderOptions).renderBefore ?? (i.renderBefore = t.firstChild), t;
  }
  update(t) {
    const i = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = Kt(i, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    var t;
    super.connectedCallback(), (t = this._$Do) == null || t.setConnected(!0);
  }
  disconnectedCallback() {
    var t;
    super.disconnectedCallback(), (t = this._$Do) == null || t.setConnected(!1);
  }
  render() {
    return H;
  }
}
var $t;
N._$litElement$ = !0, N.finalized = !0, ($t = k.litElementHydrateSupport) == null || $t.call(k, { LitElement: N });
const Q = k.litElementPolyfillSupport;
Q == null || Q({ LitElement: N });
(k.litElementVersions ?? (k.litElementVersions = [])).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const Qt = (o) => (t, i) => {
  i !== void 0 ? i.addInitializer(() => {
    customElements.define(o, t);
  }) : customElements.define(o, t);
};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const te = { attribute: !0, type: String, converter: W, reflect: !1, hasChanged: it }, ee = (o = te, t, i) => {
  const { kind: e, metadata: s } = i;
  let r = globalThis.litPropertyMetadata.get(s);
  if (r === void 0 && globalThis.litPropertyMetadata.set(s, r = /* @__PURE__ */ new Map()), e === "setter" && ((o = Object.create(o)).wrapped = !0), r.set(i.name, o), e === "accessor") {
    const { name: n } = i;
    return { set(l) {
      const a = t.get.call(this);
      t.set.call(this, l), this.requestUpdate(n, a, o, !0, l);
    }, init(l) {
      return l !== void 0 && this.C(n, void 0, o, l), l;
    } };
  }
  if (e === "setter") {
    const { name: n } = i;
    return function(l) {
      const a = this[n];
      t.call(this, l), this.requestUpdate(n, a, o, !0, l);
    };
  }
  throw Error("Unsupported decorator location: " + e);
};
function St(o) {
  return (t, i) => typeof i == "object" ? ee(o, t, i) : ((e, s, r) => {
    const n = s.hasOwnProperty(r);
    return s.constructor.createProperty(r, e), n ? Object.getOwnPropertyDescriptor(s, r) : void 0;
  })(o, t, i);
}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
function ot(o) {
  return St({ ...o, state: !0, attribute: !1 });
}
var ie = Object.defineProperty, se = Object.getOwnPropertyDescriptor, V = (o, t, i, e) => {
  for (var s = e > 1 ? void 0 : e ? se(t, i) : t, r = o.length - 1, n; r >= 0; r--)
    (n = o[r]) && (s = (e ? n(t, i, s) : n(s)) || s);
  return e && s && ie(t, i, s), s;
};
const oe = "M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h12v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-4-4-8-4zm0 2c3.5 0 6 .5 6 2.5V8H6V6.5C6 4.5 8.5 4 12 4zm-5 12c-.83 0-1.5-.67-1.5-1.5S6.17 13 7 13s1.5.67 1.5 1.5S7.83 16 7 16zm10 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1-5H6v-2h12v2z", re = "M4 16c0 .88.39 1.67 1 2.22V20c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h8v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1.78c.61-.55 1-1.34 1-2.22V6c0-3.5-3.58-4-8-4s-8 .5-8 4v10zm3.5 1c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm9 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H6V6h12v5z";
let T = class extends N {
  constructor() {
    super(...arguments), this._mainHeight = 360;
  }
  setConfig(o) {
    if (!o || !o.entity)
      throw new Error("Please define an entity in your card configuration.");
    this._config = o;
  }
  getCardSize() {
    return 4;
  }
  render() {
    if (!this._config || !this.hass)
      return _`
        <div class="card-container warning-card">
          Entity configuration missing or Home Assistant not connected.
        </div>
      `;
    const o = this.hass.states[this._config.entity];
    if (!o)
      return _`
        <div class="card-container warning-card">
          Entity not found: <code>${this._config.entity}</code>
        </div>
      `;
    if (this._selectedRouteId)
      return this._renderDetailsView(o, this._selectedRouteId);
    const t = o.attributes || {}, i = t.person_picture || "", e = this._config.title || t.commute_title || t.friendly_name || "Commute", s = t.pill_label || (o.state === "standby" ? "Standby" : "Active"), r = t.pill_color || "#8E8E93", n = t.pill_bg || "rgba(142, 142, 147, 0.2)", l = t.pill_border || "#8E8E93", a = t.active_option || "", c = t.child_entities || [], h = t.is_relevant === !0 || t.is_relevant === "true" || t.is_relevant === void 0 && o.state !== "standby" && o.state !== "idle" && o.state !== "unavailable" && o.state !== "unknown", d = [...c].sort((u, p) => {
      var F, x, v, A;
      const g = (F = this.hass) == null ? void 0 : F.states[u], m = (x = this.hass) == null ? void 0 : x.states[p], b = ((v = g == null ? void 0 : g.attributes) == null ? void 0 : v.route_id) || u, $ = ((A = m == null ? void 0 : m.attributes) == null ? void 0 : A.route_id) || p;
      return b === a || u === a ? -1 : $ === a || p === a ? 1 : 0;
    });
    return _`
      <div class="card-container" role="region" aria-label="${e}">
        <div class="card-layout">
          <!-- Row 1: Unified Header -->
          <div class="header-row">
            <div class="header-left">
              ${i ? _`<img
                    src="${i}"
                    alt="${e}"
                    class="person-avatar"
                  />` : ""}
              <div class="header-title">${e}</div>
            </div>
            <div class="header-right">
              <span
                class="header-pill"
                style="background: ${n}; border-color: ${l}; color: ${r};"
              >
                ${s}
              </span>
            </div>
          </div>

          <!-- Transit Modules (Only displayed when commute is relevant) -->
          ${h ? d.map(
      (u, p) => this._renderTransitModule(u, p === 0)
    ) : ""}
        </div>
      </div>
    `;
  }
  updated(o) {
    var t;
    if (super.updated(o), !this._selectedRouteId) {
      const i = (t = this.shadowRoot) == null ? void 0 : t.querySelector(".card-layout");
      i && i.offsetHeight > 0 && i.offsetHeight !== this._mainHeight && (this._mainHeight = i.offsetHeight);
    }
  }
  _openDetails(o, t) {
    var e;
    o.preventDefault(), o.stopPropagation();
    const i = (e = this.shadowRoot) == null ? void 0 : e.querySelector(".card-layout");
    i && i.offsetHeight > 0 && (this._mainHeight = i.offsetHeight), this._selectedRouteId = t;
  }
  _closeDetails() {
    this._selectedRouteId = void 0;
  }
  _renderDetailsView(o, t) {
    var v, A;
    const i = (v = this.hass) == null ? void 0 : v.states[t];
    if (!i)
      return this._selectedRouteId = void 0, _``;
    const e = i.attributes || {}, s = e.route_label || e.line || "Transit", r = e.route_destination || e.destination || "", n = e.corridor_color || e.route_color || "#8E8E93", l = e.line_status || e.line_status_label || "Good Service", a = e.line_status_color || "#4CAF50", c = e.line_status_icon || "✓", h = e.line_status_detail || "No operational disruptions or delays reported. Regular service operating across the corridor.", d = e.provider ? e.provider.toUpperCase() : "TfL", u = e.corridor_location || "Awaiting Service", p = e.leave_by_time || "--:--", g = e.expected_time || e.expected_boarding_time || "--:--", m = e.expected_alighting_time || e.estimated_transit_arrival || "--:--", b = e.expected_destination_time || e.estimated_destination_arrival || "--:--", $ = e.target_slack_minutes, F = $ !== void 0 ? $ >= 0 ? `+${$}m buffer (On Time)` : `${$}m late` : "N/A", x = e.seconds_to_leave !== null && e.seconds_to_leave !== void 0 ? `in ${Math.round(e.seconds_to_leave / 60)}m` : "--";
    return _`
      <div class="card-container" role="region" aria-label="${s} Details">
        <div class="details-view" style="min-height: ${this._mainHeight}px;">
          <!-- Header with Route Title and Close Button -->
          <div class="details-nav-header">
            <div class="details-route-title">
              <span class="route-badge" style="background: ${n};">${s}</span>
              <span class="destination-label">${r}</span>
            </div>
            <button
              class="close-btn"
              @click=${() => this._closeDetails()}
              aria-label="Close details"
            >
              ✕
            </button>
          </div>

          <!-- PRIMARY SECTION: Line Status Details -->
          <div class="line-status-box" style="border-left-color: ${a};">
            <div class="line-status-feed-badge">Transit Provider Feed · ${d}</div>
            <div class="line-status-headline" style="color: ${a};">
              <span>${c}</span>
              <span>${l}</span>
            </div>
            <p class="line-status-desc">${h}</p>
          </div>

          <!-- ADVANCED DETAILS ACCORDION -->
          <details class="advanced-accordion">
            <summary>
              <span><span class="emoji-icon">⚙️</span> Advanced Details (Route & Technical Info)</span>
              <span style="font-size: 11px; opacity: 0.7;">▼</span>
            </summary>
            <div class="accordion-body">
              <!-- Group 1: Route Information -->
              <div>
                <div class="accordion-section-header">
                  <span class="emoji-icon">🗺️</span>
                  <span>Route Information</span>
                </div>
                <table class="details-table">
                  <tbody>
                    <tr>
                      <td>Route / Direction</td>
                      <td>${s} to ${r} (${e.direction || "from_home"})</td>
                    </tr>
                    <tr>
                      <td>Boarding Location</td>
                      <td>${u}</td>
                    </tr>
                    <tr>
                      <td>Doorstep Departure</td>
                      <td><strong>${p}</strong> (${x})</td>
                    </tr>
                    <tr>
                      <td>Boarding Departure</td>
                      <td>${g}</td>
                    </tr>
                    <tr>
                      <td>Transit Arrival</td>
                      <td>${m}</td>
                    </tr>
                    <tr>
                      <td>Destination Arrival</td>
                      <td>${b}</td>
                    </tr>
                    <tr>
                      <td>Target Margin / Slack</td>
                      <td>${F}</td>
                    </tr>
                    <tr>
                      <td>Timeliness State</td>
                      <td><code>${e.timeliness || "on_time"}</code></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Group 2: Debugging & Technical Info -->
              <div>
                <div class="accordion-section-header">
                  <span class="emoji-icon">🔧</span>
                  <span>Debugging & Technical Info</span>
                </div>
                <table class="details-table">
                  <tbody>
                    <tr>
                      <td>Master Entity</td>
                      <td><code>${o.entity_id}</code></td>
                    </tr>
                    <tr>
                      <td>Child Route Entity</td>
                      <td><code>${t}</code></td>
                    </tr>
                    <tr>
                      <td>Tracked Vehicle ID</td>
                      <td><code>${e.vehicle_id || "Scheduled / None"}</code></td>
                    </tr>
                    <tr>
                      <td>Corridor Progress Index</td>
                      <td><code>${e.corridor_progress !== void 0 ? e.corridor_progress : "N/A"}</code></td>
                    </tr>
                    <tr>
                      <td>Target Destination Time</td>
                      <td><code>09:00</code></td>
                    </tr>
                    <tr>
                      <td>Arbitration Strategy</td>
                      <td><code>${((A = o.attributes) == null ? void 0 : A.strategy) || "late_with_buffer"}</code></td>
                    </tr>
                    <tr>
                      <td>Raw Seconds to Board</td>
                      <td><code>${e.seconds_to_board !== null && e.seconds_to_board !== void 0 ? e.seconds_to_board + "s" : "null"}</code></td>
                    </tr>
                    <tr>
                      <td>Raw Seconds to Leave</td>
                      <td><code>${e.seconds_to_leave !== null && e.seconds_to_leave !== void 0 ? e.seconds_to_leave + "s" : "null"}</code></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        </div>
      </div>
    `;
  }
  _renderTransitModule(o, t) {
    var nt;
    const i = (nt = this.hass) == null ? void 0 : nt.states[o];
    if (!i) return _``;
    const e = i.attributes || {}, s = e.route_label || e.line || "", r = e.route_destination || e.destination || "", n = e.corridor_color || e.route_color || "#8E8E93", l = e.line_status || e.line_status_label || "Good Service", a = e.line_status_color || "#4CAF50", c = e.line_status_icon || "✓", h = e.corridor_location || "Awaiting Service", d = e.corridor_stops || [], u = parseFloat(
      e.corridor_progress !== void 0 ? String(e.corridor_progress) : "-1"
    ), p = e.leave_by_time, g = p && p !== "none" ? p : "--:--", m = e.expected_time || e.expected_boarding_time, b = m && m !== "none" ? m : "--:--", $ = e.estimated_transit_arrival || e.estimated_balham_arrival || e.expected_alighting_time, F = $ && $ !== "none" ? $ : "--:--", x = e.estimated_destination_arrival || e.expected_destination_time, v = x && x !== "none" ? x : "--:--", A = e.destination_icon || "🏫", S = e.target_slack_minutes !== void 0 ? e.target_slack_minutes : e.expected_destination_margin_seconds !== void 0 ? Math.round(e.expected_destination_margin_seconds / 60) : void 0, Et = e.will_arrive_in_time === !0 || e.will_arrive_in_time === "true" || e.will_arrive_on_time === !0 || e.will_arrive_on_time === "true" || S != null && S !== "none" && parseFloat(String(S)) >= 0, Y = S != null && S !== "none" && !Et, Ct = Y ? "#FF5252" : "rgba(255, 255, 255, 0.08)", kt = Y ? "rgba(255, 82, 82, 0.15)" : "rgba(255, 255, 255, 0.05)", Pt = Y ? "#FF8A80" : "#FFFFFF", Tt = e.pill_color || "#8E8E93", Ft = e.pill_bg || "rgba(142, 142, 147, 0.2)", Rt = e.pill_border || "#8E8E93", rt = e.vehicle_type === "train" || e.mode === "train" || e.mode === "tube";
    return _`
      <div
        class="transit-module"
        @click=${(zt) => this._openDetails(zt, o)}
        role="button"
        tabindex="0"
        aria-label="View details for ${s} to ${r}"
      >
        <!-- Row 2: Transport Mode & Line Health -->
        <div class="module-header">
          <div class="mode-label-group">
            <span class="route-badge" style="background: ${n};">
              ${s}
            </span>
            <span class="destination-label">${r}</span>
          </div>
          <div class="line-health" style="color: ${a};">
            <span>${c}</span>
            <span>${l}</span>
          </div>
        </div>

        <!-- Row 3: Corridor Schematic -->
        ${d.length >= 1 ? _`
              <div class="schematic-wrapper">
                ${this._renderSchematicSvg(o, d, u, n, rt)}
              </div>
            ` : ""}

        <!-- Row 4: Live Corridor Location & Timings -->
        <div class="timings-wrapper">
          <div class="location-row">
            <span class="emoji-icon" style="color: #64B5F6;">📍</span>
            <span class="location-text">${h}</span>
          </div>

          ${b !== "--:--" || g !== "--:--" ? _`
                <div class="metrics-grid">
                  <!-- Left: Doorstep Leave-by Pill -->
                  <div class="metric-left">
                    <span
                      class="leave-pill"
                      style="background: ${Ft}; border-color: ${Rt}; color: ${Tt};"
                    >
                      <span class="emoji-icon">👟</span>
                      <span>${g}</span>
                    </span>
                  </div>

                  <!-- Centre: Transit Leg (Departure + Icon + Transit Arrival) -->
                  <div class="metric-centre">
                    <span class="transit-pill">
                      <span class="transit-time">${b}</span>
                      <span class="emoji-icon">${rt ? "🚆" : "🚌"}</span>
                      <span class="transit-time">${F}</span>
                    </span>
                  </div>

                  <!-- Right: Final Destination Arrival -->
                  <div class="metric-right">
                    ${v !== "--:--" ? _`
                          <span
                            class="destination-pill"
                            style="background: ${kt}; border-color: ${Ct}; color: ${Pt};"
                          >
                            <span class="emoji-icon">${A}</span>
                            <span class="destination-time">${v}</span>
                          </span>
                        ` : ""}
                  </div>
                </div>
              ` : ""}
        </div>
      </div>
    `;
  }
  _renderSchematicSvg(o, t, i, e, s) {
    const l = t.length === 1, a = s ? oe : re, c = `terminus-grad-${o.replace(/[^a-zA-Z0-9]/g, "-")}`;
    if (l) {
      const p = t[0], g = i >= 0, b = 40 + Math.min(Math.max(i, 0), 1) * 380;
      return R`
        <svg viewBox="0 0 460 60" class="schematic-svg">
          <defs>
            <linearGradient
              id="${c}"
              gradientUnits="userSpaceOnUse"
              x1="${40}"
              y1="22"
              x2="${420}"
              y2="22"
            >
              <stop offset="0%" stop-color="${e}" stop-opacity="0" />
              <stop offset="100%" stop-color="${e}" stop-opacity="1" />
            </linearGradient>
          </defs>

          <!-- Virtual Approach Line (Brand Colour with 0 Alpha on Left Fading to Solid on Right) -->
          <line
            x1="${40}"
            y1="22"
            x2="${420}"
            y2="22"
            stroke="url(#${c})"
            stroke-width="6"
            stroke-linecap="round"
          />

          <!-- Highlighted Boarding Stop (at the Right) -->
          <circle cx="${420}" cy="22" r="9" fill="#2B2D3A" stroke="${e}" stroke-width="3.5" />
          <circle cx="${420}" cy="22" r="4" fill="#FFFFFF" />
          <text
            x="${420}"
            y="46"
            text-anchor="middle"
            fill="#FFFFFF"
            font-size="10.5"
            font-family="system-ui"
            font-weight="700"
          >
            ${p.short_name}
          </text>

          <!-- Vehicle Marker (Clean White Circle, No Outer Halo) -->
          ${g ? R`
                  <g
                    transform="translate(${b}, 22)"
                    style="filter: drop-shadow(0px 2px 4px rgba(0, 0, 0, 0.7)); transition: transform 0.6s ease;"
                  >
                    <circle
                      cx="0"
                      cy="0"
                      r="11"
                      fill="${e}"
                      stroke="#FFFFFF"
                      stroke-width="2.5"
                    />
                    <g transform="translate(-6, -6) scale(0.5)">
                      <path d="${a}" fill="#FFFFFF" />
                    </g>
                  </g>
                ` : ""}
        </svg>
      `;
    }
    const h = t.length - 1, d = i >= 0 && t.length > 1;
    let u = 40;
    return d && (u = i > h ? 440 : 40 + i * (380 / h)), R`
      <svg viewBox="0 0 460 60" class="schematic-svg">
        <!-- Background Track -->
        <line
          x1="${40}"
          y1="22"
          x2="${420}"
          y2="22"
          stroke="rgba(255, 255, 255, 0.12)"
          stroke-width="8"
          stroke-linecap="round"
        />
        <!-- Colored Route Track -->
        <line
          x1="${40}"
          y1="22"
          x2="${420}"
          y2="22"
          stroke="${e}"
          stroke-width="6"
          stroke-linecap="round"
        />

        <!-- Stops Nodes -->
        ${t.map((p, g) => {
      const m = 40 + g * (380 / h);
      return p.is_target ? R`
              <circle cx="${m}" cy="22" r="9" fill="#2B2D3A" stroke="${e}" stroke-width="3.5" />
              <circle cx="${m}" cy="22" r="4" fill="#FFFFFF" />
              <text x="${m}" y="46" text-anchor="middle" fill="#FFFFFF" font-size="10.5" font-family="system-ui" font-weight="700">
                ${p.short_name}
              </text>
            ` : R`
            <circle cx="${m}" cy="22" r="6" fill="#2B2D3A" stroke="#FFFFFF" stroke-width="3" />
            <text x="${m}" y="46" text-anchor="middle" fill="#A0A5B5" font-size="9.5" font-family="system-ui" font-weight="500">
              ${p.short_name}
            </text>
          `;
    })}

        <!-- Vehicle Marker (Clean White Circle, No Outer Halo) -->
        ${d ? R`
                <g
                  transform="translate(${u}, 22)"
                  style="filter: drop-shadow(0px 2px 4px rgba(0, 0, 0, 0.7)); transition: transform 0.6s ease;"
                >
                  <circle
                    cx="0"
                    cy="0"
                    r="11"
                    fill="${e}"
                    stroke="#FFFFFF"
                    stroke-width="2.5"
                  />
                  <g transform="translate(-6, -6) scale(0.5)">
                    <path d="${a}" fill="#FFFFFF" />
                  </g>
                </g>
              ` : ""}
      </svg>
    `;
  }
};
T.styles = Mt`
    :host {
      display: block;
      width: 100%;
      box-sizing: border-box;
      font-family: var(
        --ha-card-font-family,
        'Inter',
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        Roboto,
        'Noto Color Emoji',
        'Apple Color Emoji',
        'Segoe UI Emoji',
        sans-serif
      );
    }

    ha-card,
    .card-container {
      display: block;
      background: #2b2d3a;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 16px;
      box-sizing: border-box;
      width: 100%;
      cursor: default;
      color: #ffffff;
      transition: all 0.25s ease;
    }

    .card-layout {
      display: flex;
      flex-direction: column;
      gap: 12px;
      text-align: left;
      width: 100%;
      box-sizing: border-box;
      min-width: 0;
    }

    /* Row 1: Unified Header */
    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      box-sizing: border-box;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .person-avatar {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid rgba(255, 255, 255, 0.15);
      flex-shrink: 0;
    }

    .header-title {
      font-size: 16px;
      font-weight: 600;
      color: #ffffff;
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .header-right {
      text-align: right;
      flex-shrink: 0;
    }

    .header-pill {
      font-weight: 700;
      font-size: 13px;
      padding: 5px 12px;
      border-radius: 20px;
      display: inline-block;
      white-space: nowrap;
      border-width: 1px;
      border-style: solid;
      box-sizing: border-box;
    }

    /* Child Route Modules */
    .transit-module {
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      width: 100%;
      box-sizing: border-box;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      overflow: hidden;
      cursor: pointer;
      transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
    }

    .transit-module:hover {
      background: rgba(255, 255, 255, 0.04);
      border-color: rgba(255, 255, 255, 0.12);
      transform: translateY(-1px);
    }

    /* Row 2: Transport Mode & Line Health */
    .module-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px 6px 12px;
      width: 100%;
      box-sizing: border-box;
    }

    .mode-label-group {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .route-badge {
      color: #ffffff;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      letter-spacing: 0.5px;
    }

    .destination-label {
      font-size: 13px;
      font-weight: 500;
      color: #ffffff;
    }

    .line-health {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
    }

    /* Row 3: Corridor Schematic */
    .schematic-wrapper {
      padding: 6px 10px 4px 10px;
      width: 100%;
      box-sizing: border-box;
    }

    .schematic-svg {
      display: block;
      width: 100%;
      max-width: 100%;
      overflow: visible;
    }

    /* Row 4: Live Location & Timings */
    .timings-wrapper {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 4px 12px 11px 12px;
      width: 100%;
      box-sizing: border-box;
    }

    .location-row {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #c4c6ca;
    }

    .location-text {
      font-weight: 500;
    }

    .metrics-grid {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      width: 100%;
      box-sizing: border-box;
      padding-top: 2px;
    }

    .metric-left {
      justify-self: start;
      display: flex;
      align-items: center;
    }

    .metric-centre {
      justify-self: center;
      display: flex;
      align-items: center;
    }

    .metric-right {
      justify-self: end;
      display: flex;
      align-items: center;
    }

    .leave-pill {
      font-weight: 700;
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      border-width: 1px;
      border-style: solid;
      box-sizing: border-box;
    }

    .transit-pill {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
      color: #ffffff;
      box-sizing: border-box;
    }

    .transit-time {
      font-weight: 600;
    }

    .destination-pill {
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      border-width: 1px;
      border-style: solid;
      box-sizing: border-box;
    }

    .destination-time {
      font-weight: 600;
    }

    .emoji-icon {
      font-family: 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif;
      font-size: 13px;
      line-height: 1;
      display: inline-block;
      transform: translateY(-2px);
    }

    /* DETAILS VIEW (OPENS ON TOP OF MAIN CARD) */
    .details-view {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
      box-sizing: border-box;
      min-height: 360px;
      animation: fadeIn 0.2s ease-in-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .details-nav-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 10px;
    }



    .details-route-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .close-btn {
      background: rgba(255, 255, 255, 0.08);
      border: none;
      color: #ffffff;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      transition: background 0.15s ease;
    }

    .close-btn:hover {
      background: rgba(255, 255, 255, 0.16);
    }

    .line-status-box {
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      padding: 14px 16px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-left-width: 5px;
      box-sizing: border-box;
    }

    .line-status-feed-badge {
      font-size: 10.5px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #a0a5b5;
      margin-bottom: 6px;
    }

    .line-status-headline {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 6px;
    }

    .line-status-desc {
      font-size: 13px;
      line-height: 1.5;
      color: #e0e2ec;
      margin: 0;
    }

    details.advanced-accordion {
      background: rgba(0, 0, 0, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      overflow: hidden;
      margin-top: 4px;
    }

    details.advanced-accordion summary {
      padding: 10px 14px;
      cursor: pointer;
      font-size: 12.5px;
      font-weight: 600;
      color: #a0a5b5;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
      list-style: none;
      transition: background 0.15s ease, color 0.15s ease;
    }

    details.advanced-accordion summary::-webkit-details-marker {
      display: none;
    }

    details.advanced-accordion summary:hover {
      background: rgba(255, 255, 255, 0.03);
      color: #ffffff;
    }

    .accordion-body {
      padding: 12px 14px;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .accordion-section-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #64b5f6;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .details-table {
      width: 100%;
      font-size: 12px;
      border-collapse: collapse;
    }

    .details-table td {
      padding: 5px 2px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      vertical-align: top;
    }

    .details-table td:first-child {
      color: #a0a5b5;
      width: 44%;
      font-weight: 500;
    }

    .warning-card {
      padding: 16px;
      color: #ffb74d;
      background: rgba(255, 183, 77, 0.1);
      border-radius: 12px;
      border: 1px solid rgba(255, 183, 77, 0.3);
      font-size: 13px;
    }
  `;
V([
  St({ attribute: !1 })
], T.prototype, "hass", 2);
V([
  ot()
], T.prototype, "_config", 2);
V([
  ot()
], T.prototype, "_selectedRouteId", 2);
V([
  ot()
], T.prototype, "_mainHeight", 2);
T = V([
  Qt("commute-tracker-card")
], T);
export {
  T as CommuteTrackerCard
};
