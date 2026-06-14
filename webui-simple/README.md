# SriniKai - simple web front end for llama.cpp

A single-file, dependency-free chat UI for a local [llama.cpp](../README.md) server.
It talks to `llama-server`'s OpenAI-compatible API and adds a login gate, saved
conversations, markdown + code rendering, and a messenger-style chat layout.

Everything lives in one file: [index.html](index.html). No build step, no npm install.

---

## What it does

- Chat with any GGUF model served by `llama-server`, with streaming replies.
- Messenger-style layout: your messages on the right, the assistant on the left.
- Markdown rendering with syntax-highlighted code blocks (language label + copy button).
- Local accounts (sign up / sign in) that gate access to the chat.
- A sidebar of saved conversations, stored per account.
- Copy / regenerate on replies, new / switch / delete chats, dark + light theme.

---

## Architecture

This is a thin browser client. It holds **no intelligence** - it just sends the
conversation to `llama-server` and renders what comes back.

```
   Browser (index.html: HTML + CSS + JS)
        |
        |  POST /v1/chat/completions   (streamed)
        |  GET  /health, /v1/models
        v
   llama-server  ---->  loads the GGUF model, generates the reply
        |
        v
     GGUF model file (on your machine)
```

Two ways to serve the page:

1. **Through llama-server (recommended).** `llama-server --path webui-simple` serves
   `index.html` *and* the API from the same origin (port 8080). One address, no CORS,
   and it is what makes link-sharing work.
2. **Dev mode with a static file server.** Serve the folder on another port (e.g.
   `python3 -m http.server 5173`) while `llama-server` runs separately on 8080. The UI
   auto-detects this case and calls `http://localhost:8080`.

The server URL logic (in `serverUrl()`):
- Settings field filled in   -> use that URL.
- Page served from port 5173 -> use `http://localhost:8080` (dev mode).
- Otherwise                   -> use the page's own origin (works for tunnels/sharing).

### How conversation context works

The model is stateless. Each conversation is kept as a `messages` array in the browser
and **re-sent in full on every request** (optionally prefixed with a system prompt).
That is the only reason the model "remembers" earlier turns. Long chats are bounded by
the server's context window (`-c`, default depends on the model); when exceeded, the
server truncates the oldest tokens.

---

## Requirements

- A built `llama-server` binary (see the main [build guide](../docs/build.md)).
- A GGUF model (downloaded automatically with `-hf`, or supplied with `-m`).
- A modern browser (Chrome, Firefox, Safari, Edge).
- For sharing only: a tunnel tool such as `ngrok` or `cloudflared`.

No other dependencies. The page loads `marked`, `DOMPurify`, and `highlight.js` from a
CDN at runtime for markdown/code rendering; with no internet it still works, just
without rich formatting.

---

## Usage

### Run it locally (recommended: one port)

```sh
# from the repo root
./build/bin/llama-server -hf ggml-org/gemma-3-1b-it-GGUF --path webui-simple
```

Open http://localhost:8080, click **Create account**, sign up, and start chatting.

### Run it in dev mode (two ports)

```sh
# terminal 1: the model server
./build/bin/llama-server -hf ggml-org/gemma-3-1b-it-GGUF

# terminal 2: the static file server
cd webui-simple && python3 -m http.server 5173
```

Open http://localhost:5173. (Serving over http rather than opening the file directly is
required: browsers block a `file://` page from calling `localhost`.)

### Share a link with a friend

```sh
# 1. serve UI + API from one port
./build/bin/llama-server -hf ggml-org/gemma-3-1b-it-GGUF --path webui-simple

# 2. expose that port publicly
ngrok http 8080
```

Send your friend the `https://....ngrok-free.app` URL ngrok prints. The model runs on
**your** machine; they only drive it through the browser, so keep `llama-server` running.

To require a key on a public link:

```sh
./build/bin/llama-server -hf ... --path webui-simple --api-key mysecret123
```

Then open Settings (gear icon) and paste the same key into the **API key** field. The UI
sends it as an `Authorization: Bearer` header on every request, so people without the key
get rejected by the server.

---

## Settings (gear icon)

- **Server URL** - override the API endpoint. Leave blank to use the page's origin.
- **Temperature** - sampling randomness (0 = deterministic, higher = more creative).
- **System prompt** - prepended to every request; read fresh on each send, not saved per chat.
- **API key** - if set, sent as an `Authorization: Bearer` header; match it to the server's
  `--api-key`. Stored in `localStorage` (`sk-settings`) in plaintext, like the other settings.

All of these settings persist across reloads (saved under `sk-settings`).

---

## Data storage and privacy

All data is stored in the browser's `localStorage` for the page's origin. Nothing is
sent to any server other than the chat content going to your `llama-server`.

| Key               | Contents                                            |
| ----------------- | --------------------------------------------------- |
| `sk-users`        | All accounts: `{ email: { name, hash } }` (SHA-256) |
| `sk-session`      | Email of the currently logged-in user               |
| `sk-chats:<email>`| That user's saved conversations                     |
| `sk-theme`        | light / dark preference                             |

**This is a local demo gate, not real security:**
- `localStorage` is shared by everyone using the same browser profile. Anyone with
  DevTools can read all accounts and chats directly; the login only controls what the UI
  displays.
- Passwords are SHA-256 hashed (raw password not stored) but unsalted - not strong.
- Data is per-browser and per-device. A different browser or computer sees no accounts
  and no history; nothing syncs.

For real multi-user privacy you need a backend (server-side accounts, salted password
hashing, authenticated sessions, a database).

---

## Troubleshooting

- **Red status dot / "no server".** `llama-server` is not running, or the Server URL is
  wrong. Start the server and confirm http://localhost:8080/health returns `OK`.
- **"failed to load model" / file not found.** The `-m` path does not exist. Use a real
  file, or use `-hf <repo>` to download one automatically.
- **Messages send but never reply.** Usually a CORS / wrong-origin issue. Serve the UI
  through `llama-server --path` so the page and API share one origin.
- **favicon.ico 404 in logs.** Harmless; an inline favicon is already included.
- **Friend's link does not respond.** Your `llama-server` must stay running and the
  tunnel must be active; sleeping the host kills both.

---

## Files

- [index.html](index.html) - the entire application (HTML, CSS, JS in one file).
