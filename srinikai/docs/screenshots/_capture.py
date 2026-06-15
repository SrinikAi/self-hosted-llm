"""Render the static SriniKai frontend in headless Chrome and capture screenshots.

Produces real UI images without a running backend by injecting sample DOM state
into the existing page using the page's own render functions.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parent.parent / "frontend" / "index.html"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CHAT_INJECT = r"""
<script>
window.addEventListener('load', () => setTimeout(() => {
  if (window.__theme) setTheme(window.__theme);
  // Force the authenticated app view.
  document.querySelector('#auth').style.display = 'none';
  document.querySelector('#app').classList.add('on');
  document.querySelector('#whoami').textContent = 'srini@example.com';

  // Sidebar conversations.
  const convos = [['Postgres vs SQLite for RAG', true],
                  ['Trip plan: Tokyo in spring', false],
                  ['Refactor the auth router', false],
                  ['Explain vector embeddings', false]];
  const el = document.querySelector('#convos'); el.innerHTML = '';
  convos.forEach(([title, active]) => {
    const d = document.createElement('div');
    d.className = 'convo' + (active ? ' active' : '');
    d.innerHTML = `<span>${title}</span><span class="del" title="Delete">&#128465;</span>`;
    el.append(d);
  });

  // Sample turns using the page's own renderer.
  document.querySelector('#messages').innerHTML = '';
  const u = addTurn('user');
  u.innerHTML = md('What is the difference between cosine distance and cosine similarity for memory search?');
  const a = addTurn('assistant');
  a.innerHTML = md(
    "Good question - they're two views of the same thing.\n\n" +
    "- **Cosine similarity** ranges from `-1` to `1`; higher means *more alike*.\n" +
    "- **Cosine distance** is `1 - similarity`; lower means *more alike*.\n\n" +
    "pgvector's `<=>` operator returns the **distance**, so you order ascending and " +
    "convert back to a score when you need a threshold:\n\n" +
    "```sql\nSELECT content, 1 - (embedding <=> :q) AS score\nFROM memories\nORDER BY embedding <=> :q\nLIMIT 4;\n```\n\n" +
    "That's exactly what SriniKai's memory retrieval does."
  );
  decorate(a);
}, 600));
</script>
"""


def build_variant(theme: str, inject: str = "") -> Path:
    html = FRONTEND.read_text()
    if theme == "dark":
        html = html.replace('data-theme="light"', 'data-theme="dark"', 1)
    if inject:
        inject = f"<script>window.__theme={theme!r};</script>" + inject
        html = html.replace("</body>", inject + "\n</body>", 1)
    tmp = Path(tempfile.mkdtemp()) / "page.html"
    tmp.write_text(html)
    return tmp


def shoot(src: Path, out: Path, w: int = 1280, h: int = 860):
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=2", f"--window-size={w},{h}",
        "--virtual-time-budget=4000", f"--screenshot={out}", f"file://{src}",
    ], check=True, capture_output=True)
    print("wrote", out)


if __name__ == "__main__":
    shoot(build_variant("light"), HERE / "login.png")
    shoot(build_variant("light", CHAT_INJECT), HERE / "chat-light.png")
    shoot(build_variant("dark", CHAT_INJECT), HERE / "chat-dark.png")
