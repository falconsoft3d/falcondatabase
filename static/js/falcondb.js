/**
 * falcondb.js — JavaScript client for falcondatabase. No dependencies.
 *
 *   import { createClient } from "https://your-server/sdk/falcondb.js"
 *   const db = createClient("https://your-server", "PROJECT_REF", "ANON_KEY")
 *
 *   const { data, count, error } = await db.from("todos").select().eq("done", false).order("id", { desc: true })
 *   await db.from("todos").insert({ title: "Hola" })
 *   await db.auth.signIn({ email, password })
 *
 * Every call resolves to `{ data, error, ... }` and never throws on API errors.
 */

class QueryBuilder {
  constructor(client, table) {
    this.client = client;
    this.table = table;
    this.params = new URLSearchParams();
  }

  get path() {
    return `/tables/${encodeURIComponent(this.table)}`;
  }

  // --- reading -------------------------------------------------------------

  select(columns = "*") {
    if (columns && columns !== "*") this.params.set("select", columns);
    return this;
  }

  filter(column, operator, value) {
    this.params.append(column, `${operator}.${value}`);
    return this;
  }

  eq(column, value) { return this.filter(column, "eq", value); }
  neq(column, value) { return this.filter(column, "neq", value); }
  gt(column, value) { return this.filter(column, "gt", value); }
  gte(column, value) { return this.filter(column, "gte", value); }
  lt(column, value) { return this.filter(column, "lt", value); }
  lte(column, value) { return this.filter(column, "lte", value); }
  like(column, pattern) { return this.filter(column, "like", pattern); }
  ilike(column, pattern) { return this.filter(column, "ilike", pattern); }
  is(column, value) { return this.filter(column, "is", value); }
  in(column, values) { return this.filter(column, "in", `(${values.join(",")})`); }

  order(column, { desc = false } = {}) {
    const current = this.params.get("order");
    const part = `${column}.${desc ? "desc" : "asc"}`;
    this.params.set("order", current ? `${current},${part}` : part);
    return this;
  }

  limit(count) {
    this.params.set("limit", count);
    return this;
  }

  offset(count) {
    this.params.set("offset", count);
    return this;
  }

  range(from, to) {
    return this.offset(from).limit(to - from + 1);
  }

  // Makes the builder awaitable: `await db.from("t").select()`.
  then(resolve, reject) {
    const query = this.params.toString();
    return this.client.request("GET", this.path + (query ? `?${query}` : "")).then(resolve, reject);
  }

  get(id) {
    return this.client.request("GET", `${this.path}/${id}`);
  }

  // Returns the first matching row (or null).
  async single() {
    const result = await this.limit(1);
    return { ...result, data: result.data ? result.data[0] ?? null : null };
  }

  // --- writing -------------------------------------------------------------

  insert(values) {
    return this.client.request("POST", this.path, values);
  }

  update(id, values) {
    return this.client.request("PATCH", `${this.path}/${id}`, values);
  }

  delete(id) {
    return this.client.request("DELETE", `${this.path}/${id}`);
  }
}

class AuthClient {
  constructor(client) {
    this.client = client;
    this.storageKey = `falcondb.${client.ref}.session`;
    this.session = this._load();
    this.listeners = new Set();
  }

  _load() {
    try {
      return JSON.parse(localStorage.getItem(this.storageKey)) || null;
    } catch {
      return null;
    }
  }

  _save(session) {
    this.session = session;
    try {
      if (session) localStorage.setItem(this.storageKey, JSON.stringify(session));
      else localStorage.removeItem(this.storageKey);
    } catch {
      // Storage unavailable (private mode, server side): keep the session in memory.
    }
    this.listeners.forEach((callback) => callback(session ? session.user : null));
  }

  get token() {
    return this.session ? this.session.token : null;
  }

  get user() {
    return this.session ? this.session.user : null;
  }

  async signUp({ email, password, data } = {}) {
    const result = await this.client.request("POST", "/auth/signup", { email, password, data });
    if (!result.error) this._save({ token: result.data.token, user: result.data.user });
    return { user: result.data ? result.data.user : null, error: result.error };
  }

  async signIn({ email, password } = {}) {
    const result = await this.client.request("POST", "/auth/login", { email, password });
    if (!result.error) this._save({ token: result.data.token, user: result.data.user });
    return { user: result.data ? result.data.user : null, error: result.error };
  }

  async getUser() {
    if (!this.token) return { user: null, error: null };
    const result = await this.client.request("GET", "/auth/user");
    if (result.status === 401) this._save(null);
    return { user: result.data ? result.data.user : null, error: result.error };
  }

  async updateUser(data) {
    const result = await this.client.request("PATCH", "/auth/user", { data });
    if (!result.error) this._save({ ...this.session, user: result.data.user });
    return { user: result.data ? result.data.user : null, error: result.error };
  }

  signOut() {
    this._save(null);
  }

  // Calls `callback(user | null)` whenever the user signs in or out.
  onChange(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }
}

export class FalconClient {
  constructor(url, ref, apiKey) {
    if (!url || !ref || !apiKey) throw new Error("createClient(url, ref, apiKey): missing arguments");
    this.baseUrl = `${url.replace(/\/+$/, "")}/api/v1/${ref}`;
    this.ref = ref;
    this.apiKey = apiKey;
    this.auth = new AuthClient(this);
  }

  from(table) {
    return new QueryBuilder(this, table);
  }

  // Tables and columns visible with the current key.
  schema() {
    return this.request("GET", "");
  }

  async request(method, path, body) {
    const headers = { apikey: this.apiKey };
    if (this.auth && this.auth.token) headers.Authorization = `Bearer ${this.auth.token}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    try {
      const response = await fetch(this.baseUrl + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        return { data: null, error: { message: payload.error || response.statusText, status: response.status }, status: response.status };
      }
      const result = { data: "data" in payload ? payload.data : payload, error: null, status: response.status };
      if ("count" in payload) result.count = payload.count;
      return result;
    } catch (err) {
      return { data: null, error: { message: err.message, status: 0 }, status: 0 };
    }
  }
}

export function createClient(url, ref, apiKey) {
  return new FalconClient(url, ref, apiKey);
}

export default createClient;
