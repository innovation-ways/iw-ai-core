# R-00063 — Browser Demo Video Auto-Generation (Local, OSS, WSL)

**ID**: R-00063
**Date**: 2026-04-22
**Mode**: deep
**Editorial Category**: functional
**Status**: draft

**Primary Question**: What is the best locally-runnable, open-source stack on WSL to turn a narrative demo script into a polished 30–60s screen-capture video of a deployed web frontend — with a visible mouse cursor and editable clips for DaVinci Resolve finishing — without paying for any SaaS?

---

## Executive Summary

The landscape pivoted sharply in early 2026 when Microsoft shipped **Playwright 1.59 — the "agentic release"** — which introduced a first-class [`page.screencast` API](https://playwright.dev/docs/api/class-screencast) designed explicitly for AI agents to record annotated demo videos, and a companion [`@playwright/cli`](https://www.npmjs.com/package/@playwright/cli) built for coding agents ([bug0.com](https://bug0.com/blog/whats-new-playwright-1-59)). This solves roughly 80% of the user's problem out of the box: programmatic video recording with chapter markers, action annotations, custom HTML overlays, arbitrary resolution, and WebM output — all via the Chrome DevTools Protocol inside the browser process, so it works identically on WSL, Linux, and macOS with no screen-capture layer required.

The remaining gap — a visible mouse cursor — is filled by injecting [`cenfun/mouse-helper`](https://github.com/cenfun/mouse-helper) as an init script (MIT, Puppeteer+Playwright compatible); alternatively, Playwright's own `showActions()` annotation highlights clicked elements with titles, which is arguably *better* than a cursor for a landing-page demo. The narrative-to-script translation is a well-trodden pattern using Claude Code + [Playwright MCP](https://github.com/microsoft/playwright-mcp). For polish (auto-zoom, motion blur, cursor effects), chain with [OpenScreen](https://github.com/siddharthvaddem/openscreen) or [open-recorder](https://github.com/imbhargav5/open-recorder) as a purely optional post-processing stage — but given the user already has DaVinci Resolve, these are not strictly needed.

**Recommended primary stack**: `@playwright/cli` + `page.screencast` + `mouse-helper` + Claude Code (with Playwright MCP) for narrative→script translation. Runs entirely on WSL, no SaaS, no paid subscriptions, only per-call Claude API costs for the script-generation step (which is a one-time operation).

---

## Findings

### Finding 1 — Playwright 1.59's `page.screencast` is purpose-built for this exact use case [HIGH]

Playwright 1.59 (shipped early 2026, titled internally "the agentic release") introduced the [`page.screencast` class](https://playwright.dev/docs/api/class-screencast) as a programmatic demo-video API distinct from the older `context.recordVideo` test-artifact mechanism ([Playwright release notes](https://playwright.dev/docs/release-notes); [bug0.com](https://bug0.com/blog/whats-new-playwright-1-59)). The API exposes:

| Method | Purpose |
|---|---|
| `start({ path, size, onFrame, quality })` | Begin recording to a WebM file or stream JPEG frames |
| `stop()` | Finalize the file |
| `showActions({ duration, fontSize, position })` | Auto-annotate clicks/fills/navigations with titles overlaid on the video |
| `showChapter(title, { description, duration })` | Full-screen centered chapter card with blurred backdrop |
| `showOverlay(html, { duration })` | Arbitrary HTML overlay for callouts/highlights |
| `onFrame(cb)` | Stream JPEG-encoded frames in real time |

Overlays use `pointer-events: none`, so they do not interfere with page interactions ([knightli.com deep-dive](https://www.knightli.com/en/2026/04/15/playwright-cli-video-recording/)). Output is **WebM (VP8/VP9)**. Default size auto-fits to 800×800 preserving aspect ratio; configurable to 1280×800, 1920×1080, etc.

Critically, the bug0.com release analysis explicitly frames this as a "workflow pattern" where *"Screencast records entire session with annotations"* for AI agents to produce walkthrough videos with chapter titles and action annotations — i.e. Microsoft built this for the exact use case the user described. The blog captures the shift: *"This replaces Playwright 1.58's 'config-level, set-and-forget' video option with full programmatic control."*

### Finding 2 — Visible cursor: three viable paths, ranked [HIGH]

Headless Chromium does not render an OS cursor, and Playwright's [Issue #6629](https://github.com/microsoft/playwright/issues/6629) ("Request to show the cursor on a video recording") and [Issue #1374](https://github.com/microsoft/playwright/issues/1374) ("Mouse helper") both remain `P3-collecting-feedback` — no native fix is coming. The three practical workarounds:

**(a) `page.screencast.showActions()` — official, built-in [HIGH].** Instead of a moving cursor, Playwright overlays the *name of each action* (e.g. "click 'Sign up'") near the interacted element during the video. For a **marketing landing-page demo**, this is materially better than a cursor: viewers see what the action *means* rather than having to track a dot. Zero dependencies, one method call.

**(b) `cenfun/mouse-helper` — dedicated OSS cursor overlay [HIGH].** MIT-licensed npm package explicitly supporting both Puppeteer and Playwright ([repo](https://github.com/cenfun/mouse-helper)). Installed as an init script:

```js
await context.addInitScript({ path: './node_modules/mouse-helper/dist/mouse-helper.js' });
const page = await context.newPage();
await page.evaluate(() => window['mouse-helper']());
// all subsequent page.mouse.move / page.click will be visualized
```

Shows three states: position indicator, click/mousedown, idle. Works in headless, records into the WebM correctly. This is the path if you specifically need a cursor *and* action labels.

**(c) `ghost-cursor-playwright` — human-like curves, not cursor rendering [MEDIUM].** Both [Xetera/ghost-cursor](https://github.com/Xetera/ghost-cursor) (Puppeteer) and [reaz1995/ghost-cursor-playwright](https://github.com/reaz1995/ghost-cursor-playwright) (Playwright port) generate *Bezier-curve mouse movement coordinates* that look human — but they **do not render the cursor visually by default**. Xetera's docs confirm `installMouseHelper()` is a "debug-only" option. These libraries matter if you want non-linear mouse paths (aesthetically nicer than straight jumps), but you still need mouse-helper or `showActions` for visibility.

**Ruled out: native OS cursor via screen capture.** Running headed Chromium under WSLg and capturing with ffmpeg x11grab is technically possible ([WSLg](https://github.com/microsoft/wslg) supports X11 apps) but introduces frame-drop risk at higher resolutions and display-setup fragility. Given `page.screencast` gives deterministic, lossless, OS-independent recording via CDP, adopting screen capture would be a regression.

### Finding 3 — `@playwright/cli` and Playwright MCP give Claude Code/agents direct video-recording tools [HIGH]

Microsoft shipped [`@playwright/cli`](https://www.npmjs.com/package/@playwright/cli) in early 2026 as a separate npm package built specifically for AI coding agents. It saves accessibility snapshots as YAML files instead of streaming the full tree into the model's context window — roughly a 4× token reduction versus piping through Playwright MCP ([Medium field guide](https://medium.com/@adnanmasood/playwright-and-playwright-mcp-a-field-guide-for-agentic-browser-automation-f11b9daa3627)). Video-recording commands are first-class:

```
playwright-cli video-start demo.webm
playwright-cli video-chapter "Feature X" --description="Shows how to create a plan" --duration=2000
playwright-cli run-code --filename demo-script.js
playwright-cli video-stop
```

Alternatively, the [official Microsoft `playwright-mcp` server](https://github.com/microsoft/playwright-mcp) (Apache-2.0) exposes the same functionality as MCP tools when launched with `--caps=devtools`:

- `browser_start_video` (filename, width, height)
- `browser_stop_video`
- `browser_video_chapter` (title, description, duration)

Auto-recording can be enabled via `PLAYWRIGHT_MCP_SAVE_VIDEO=800x600` env var ([Playwright MCP video docs](https://playwright.dev/mcp/tools/video)). A third-party fork [korwabs/playwright-record-mcp](https://github.com/korwabs/playwright-record-mcp) predates the official release and adds mp4 output and pause/resume, but the official MCP is now preferred.

### Finding 4 — `browser-use` does not record video natively [MEDIUM]

[browser-use](https://github.com/browser-use/browser-use) — one of the most popular local AI browser agents — has an open feature request ([Issue #4533](https://github.com/browser-use/browser-use/issues/4533)) for a `browser-use record` command. The maintainers acknowledge this is not implemented; the CLI uses `cdp-use` under the hood rather than Playwright, so `record_video_dir` is not available. Currently the only workarounds are screenshot loops (loses timing) or OS-level screen capture (headless-incompatible). **This rules browser-use out as a primary choice** despite its excellent narrative-driven agent capability. If you want an AI agent that both drives the browser from natural language *and* records video, Playwright MCP with Claude Code is the only complete stack today.

Related sibling project [browser-use/video-use](https://github.com/browser-use/video-use) is **not** a browser recorder — it is a Claude-Code-integrated *video editor* that trims filler words, color grades, and adds subtitles to pre-recorded footage. Useful as a post-production step if you were recording a voiced-over demo, but orthogonal to this user's problem.

### Finding 5 — Purpose-built AI demo toolkits exist but add complexity [MEDIUM]

[`digitalsamba/claude-code-video-toolkit`](https://github.com/digitalsamba/claude-code-video-toolkit) (MIT, ~937 stars) is the closest thing to a turnkey solution. It bundles **nine specialized Claude Code skills** — including `playwright-recording` explicitly described as *"Browser automation — record demos as video"* — plus [Remotion](https://www.remotion.dev/) for React-based composition, moviepy, ffmpeg, ElevenLabs TTS, FLUX image-gen, and Qwen3-TTS. The slash command `/record-demo` triggers Playwright-based browser capture, and the product-demo template is directly relevant.

**However**, the toolkit's AI-generation features (voiceover, music, imagery, talking heads) require **cloud GPU credits** via Modal or RunPod — which violates the user's no-SaaS rule. The *recording* and *basic editing* pieces work fully offline (ffmpeg, Remotion, Playwright), but you lose most of the toolkit's differentiated value if you can't use the AI-gen. For this user, **extract the `playwright-recording` skill pattern, skip the rest.**

[`calesthio/OpenMontage`](https://github.com/calesthio/OpenMontage) (AGPLv3) has a "Screen Demo" pipeline but — on close inspection of the README — the pipeline is **composition-only**: it assembles pre-recorded clips with titles, zooms, and music. It does not capture live browser interactions. Not a fit for turning a narrative into a recorded demo end-to-end.

### Finding 6 — `OpenScreen` / `open-recorder` — OSS Screen Studio alternatives [MEDIUM]

For the *cursor-animation/auto-zoom/motion-blur* polish commonly associated with Scribe and Arcade, two open-source tools stand out:

- [`siddharthvaddem/openscreen`](https://github.com/siddharthvaddem/openscreen) — AppImage-distributed, Linux-compatible (requires PipeWire on Ubuntu 22.04+), ~16k stars, "no watermarks, free for commercial use."
- [`imbhargav5/open-recorder`](https://github.com/imbhargav5/open-recorder) — Tauri+Rust, adds auto-zoom and cursor animations to screen recordings.

Both are **interactive desktop apps** that record the OS screen — they are not scriptable and do not fit a "narrative → automated video" pipeline. They are useful if the user decides to abandon automation and record by hand. **In the automated path, they are unnecessary**: `page.screencast.showActions()` + DaVinci Resolve's built-in zoom/keyframe animation give you Scribe-grade polish in post.

### Finding 7 — WSL compatibility: CDP screencast sidesteps every WSL display headache [HIGH]

This is the single most important practical win for a WSL user. `page.screencast` (and `context.recordVideo`) record the browser viewport via the **Chrome DevTools Protocol** inside the Chromium process itself — no host OS screen capture, no X server, no Wayland compositor, no WSLg dependency. It works identically in headless mode on WSL, a Linux CI runner, or a macOS laptop.

Contrast with the alternatives:
- **ffmpeg x11grab**: requires a running X server; WSLg provides one but x11grab "drops frames at high resolutions and lags the entire X server" ([Tony Tascioglu wiki](https://wiki.tonytascioglu.com/scripts/ffmpeg/kmsgrab_screen_capture)). kmsgrab is better but WSLg doesn't expose the KMS device.
- **OBS + websocket**: works with WSLg but adds a second heavy process and orchestration complexity.
- **wf-recorder**: Wayland-only, may or may not work under WSLg depending on compositor exposure.

**Conclusion**: stay in the Playwright CDP path and you avoid every one of these gotchas. Headless Chromium recording on WSL is a solved problem.

### Finding 8 — Narrative → Playwright script translation is a well-trodden pattern [HIGH]

Multiple independent projects demonstrate the pattern of feeding an LLM a narrative brief and getting back a runnable Playwright script ([Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/how-to-integrate-playwright-mcp-for-ai-driven-test-automation/4470372); [jingbinw/ai-playwright-automation](https://github.com/jingbinw/ai-playwright-automation); [DEV.to tutorial](https://dev.to/debs_obrien/generate-playwright-tests-without-code-access-using-mcp-and-copilot-2m05)). The now-standard recipe:

1. Claude (or GPT-4) is given the narrative + a live `page.ariaSnapshot({ mode: 'ai' })` of the landing-page app
2. The LLM produces a deterministic `.spec.ts` Playwright script with selector-based clicks, fills, waits, and screencast calls
3. The user runs the script; it emits the WebM deterministically, re-runnably, debuggably

This is **much more reliable** than asking an agent (browser-use, computer-use) to click the UI live, because: (a) the clip is reproducible without re-invoking the LLM, (b) you can edit the script by hand to tweak timing/camera angles, (c) you pay the LLM cost *once* rather than every take. For a landing-page hero video, determinism matters more than autonomy.

The [Playwright codegen](https://playwright.dev/docs/codegen) command (`playwright codegen <url>`) is the non-AI version of the same pattern — you click through the app once, it records a script; then you edit the narrative into it.

### Finding 9 — SaaS tools ruled out (all confirmed SaaS, no OSS equivalents that fit) [HIGH]

| Tool | Status | OSS alternative? |
|---|---|---|
| **[Scribe](https://scribehow.com/)** | SaaS (freemium, watermark on free) | None that matches — Scribe's step-auto-detection is proprietary |
| **[Supademo](https://supademo.com/)** | SaaS | Demo-category overlap only, no true OSS clone |
| **[Arcade](https://www.arcade.software/)** | SaaS | Howdygo and Storylane are also SaaS; no true OSS clone |
| **[Tella](https://www.tella.tv/)** | SaaS | Use OpenScreen/open-recorder for manual recording |
| **[Guidde](https://www.guidde.com/)** | SaaS | None — proprietary AI guide generation |
| **[Loom](https://www.loom.com/)** / **Loom AI** | SaaS | [contrastio/recorder](https://github.com/contrastio/recorder), [addyosmani/recorder](https://github.com/addyosmani/recorder) for in-browser recording |
| **[ScreenStudio](https://www.screen.studio/)** | Paid desktop app | [OpenScreen](https://github.com/siddharthvaddem/openscreen), [open-recorder](https://github.com/imbhargav5/open-recorder) |

None of the SaaS products above will match the user's requirement of a scriptable, local, reproducible pipeline. Even if the user accepted a one-time pay-per-use model, none expose a local CLI — they all require web upload of the captured material.

---

## Recommendation — Primary Stack

**The stack**:

```
┌─────────────────────────────────────────────────────────────┐
│ narrative-script.md  (your existing narrative)              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Claude Code + @playwright/cli + Playwright MCP             │
│ • Claude opens the deployed frontend                        │
│ • Inspects the DOM via ariaSnapshot                         │
│ • Writes demo.spec.ts with page.screencast + mouse-helper  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ npx playwright test demo.spec.ts                            │
│ • Runs headless Chromium via CDP on WSL                     │
│ • page.screencast.start() → demo.webm                       │
│ • mouse-helper injected via addInitScript → visible cursor  │
│ • showActions() → title labels on every click               │
│ • showChapter() → 3-4 section cards                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Multiple .webm clips (one per narrative section)            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ DaVinci Resolve                                             │
│ • Import .webm clips                                        │
│ • Trim, add transitions, titles                             │
│ • Layer royalty-free ambient track (Pixabay / YT Audio Lib) │
│ • Export .mp4 1080p                                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
                   landing-page hero video
```

**Why this stack wins**:

1. **Fully local, no SaaS** — only cost is Claude API usage during the one-time script-generation step (estimate: <$1 per narrative, cacheable/reusable).
2. **Deterministic** — you run `npx playwright test` N times until the clips look right without re-invoking the LLM.
3. **WSL-native** — CDP screencast sidesteps every WSL display issue. No X server, no OBS, no ffmpeg capture layer.
4. **Editable** — the generated `.spec.ts` is plain TypeScript you can hand-edit for pacing, selectors, and emphasis.
5. **Quality matches SaaS** — `showActions` + `showChapter` + `mouse-helper` + DaVinci's zoom/keyframe tools produce Scribe-grade output with zero vendor lock-in.

**Fallback stack** (if `page.screencast` has issues or you want more AI orchestration):

- [`digitalsamba/claude-code-video-toolkit`](https://github.com/digitalsamba/claude-code-video-toolkit) with only the `playwright-recording` and `ffmpeg` skills enabled, cloud GPU pieces disabled. Use its `/record-demo` slash command. More opinionated than the primary stack — good if you want scaffolding rather than to write your own glue.

---

## Minimal Pipeline Sketch

Not full code — just enough to judge feasibility. The complete working script is ~50 lines.

**1. Setup (one-time)**:
```bash
cd ~/projects/demo-video
npm init -y
npm i -D @playwright/test mouse-helper
npx playwright install chromium
```

**2. Narrative → script (Claude Code session)**:
```
You: Here's my narrative: "Show a user creating a project, then
     adding three documents, then previewing the final output."
     The app is deployed at https://iw.example.com, seeded with
     demo@iw.example.com / password123.

Claude: [uses Playwright MCP to open the URL, inspect ariaSnapshot,
         identify selectors, then writes demo.spec.ts with
         page.screencast.start(), showChapter() between sections,
         showActions(), and page.mouse.move() sequences paced at
         human speed with pressSequentially() for typing]
```

**3. Script skeleton (what Claude produces)**:
```typescript
import { test } from '@playwright/test';

test('landing page demo', async ({ page, context }) => {
  // Inject visible cursor
  await context.addInitScript({
    path: './node_modules/mouse-helper/dist/mouse-helper.js'
  });
  await page.evaluate(() => (window as any)['mouse-helper']());

  // Start recording at 1080p
  await page.screencast.start({
    path: 'out/demo.webm',
    size: { width: 1920, height: 1080 }
  });
  await page.screencast.showActions({ duration: 800, position: 'top-right' });

  // Chapter 1
  await page.screencast.showChapter('Create a project',
    { description: 'Start from a blank canvas', duration: 2000 });
  await page.goto('https://iw.example.com/login');
  await page.getByLabel('Email').pressSequentially('demo@iw.example.com', { delay: 60 });
  // ... etc

  await page.screencast.stop();
});
```

**4. Record clips**:
```bash
npx playwright test demo.spec.ts --project=chromium
# → out/demo.webm  (one long take)
# OR split the spec into multiple tests for separate clips
```

**5. Finish in DaVinci Resolve** — import `.webm` clips, layer ambient audio from Pixabay/YouTube Audio Library, export 1080p mp4.

---

## Comparison Table

| Tool / Approach | Local-only | Records video natively | Visible cursor OOB | Narrative/LLM-driven | WSL-compatible | Setup effort | License |
|---|---|---|---|---|---|---|---|
| **Playwright 1.59 `page.screencast`** | yes | yes (WebM/CDP) | no (needs `mouse-helper` or `showActions`) | via Claude Code | yes | low | Apache-2.0 |
| **`@playwright/cli`** | yes | yes (video-start/stop/chapter) | same as above | yes (agent-first) | yes | low | Apache-2.0 |
| **Playwright MCP (`--caps=devtools`)** | yes | yes (browser_start_video) | same as above | yes (via Claude) | yes | low | Apache-2.0 |
| **`mouse-helper` (cenfun)** | yes | no (cursor only) | yes | n/a | yes | trivial | MIT |
| **`ghost-cursor` / `ghost-cursor-playwright`** | yes | no (coords only) | no (debug flag only) | n/a | yes | low | MIT |
| **`claude-code-video-toolkit`** | partial (AI-gen needs cloud) | yes (via `playwright-recording` skill) | yes (depends on skill impl) | yes | yes | medium | MIT |
| **`browser-use` (Python)** | yes | **no** (feature request open) | n/a | yes (top-tier) | yes | low | MIT |
| **`browser-use/video-use`** | yes | no (edits existing footage) | n/a | partial | yes | low | unspecified |
| **OpenMontage** | yes | no (composition only, no browser capture) | n/a | yes | yes | medium | AGPLv3 |
| **Anthropic computer-use demo** | yes (Docker) | via container VNC | yes (actual OS cursor) | yes | yes (Docker) | medium | MIT |
| **Stagehand (Browserbase)** | partial | via Browserbase replay (SaaS) | unclear | yes | yes | low | MIT (core) |
| **Skyvern** | yes | live viewport streaming | unclear | yes | yes | medium | AGPLv3 |
| **OpenScreen** (desktop app) | yes | yes (manual screen capture) | yes (OS cursor) | no | yes (AppImage) | trivial | open-source |
| **open-recorder** (Tauri) | yes | yes (manual, with auto-zoom) | yes | no | yes | trivial | MIT |
| **ffmpeg x11grab + WSLg** | yes | yes | yes | no | yes (fragile) | high | LGPL |
| **OBS + websocket** | yes | yes | yes | partial (via websocket API) | yes (fragile on WSLg) | high | GPLv2 |
| **Scribe / Supademo / Arcade / Tella / Guidde / Loom AI** | **no** (all SaaS) | yes | yes | partial | n/a | trivial | proprietary |

---

## Gotchas & Failure Modes

1. **Headless Chromium renders no cursor without `mouse-helper`.** This is the #1 surprise. If you record and the video has no cursor, you forgot the `addInitScript` line. `page.screencast.showActions()` is independent of the cursor — it overlays text, not a pointer.

2. **`context.recordVideo` (old API) vs `page.screencast` (1.59 API) are different products.** `recordVideo` is config-level, fires for every test, writes on context close — built for failure-replay test artifacts. `page.screencast` is programmatic, mid-test, with annotations — built for demos. Use `page.screencast` for this use case. Don't mix.

3. **Agent-driven takes are flaky; scripted takes are deterministic.** Do NOT have Claude drive the browser *live* while recording — one stale selector and you waste a take. Have Claude write the script, then run the script with `npx playwright test` as many times as you need.

4. **Clip stitching is DaVinci's job, not Playwright's.** Record short, bounded takes (one per narrative section = 5–15s each). Trying to record one long take where everything must succeed is brittle. Splitting into multiple `test()` functions, each producing its own `.webm`, is the pattern.

5. **Video size vs. page viewport.** `page.screencast.start({ size: { width: 1920, height: 1080 } })` records at that size, but if your page viewport is different, the content is scaled. Set `page.setViewportSize({ width: 1920, height: 1080 })` to match — otherwise you'll get unexpected scaling artifacts.

6. **Timing feels robotic without `pressSequentially` and `waitForTimeout`.** A human types slower than `page.fill()` dumps text instantly. Use `page.getByLabel(...).pressSequentially(text, { delay: 60 })` for typing, and insert deliberate `await page.waitForTimeout(800)` pauses between actions for the video to read as demo-paced rather than test-paced.

7. **WebM may need conversion for some editors.** DaVinci Resolve (free) historically had spotty WebM support on Linux — if you hit an import issue, `ffmpeg -i demo.webm -c:v libx264 -preset slow -crf 18 demo.mp4` gives you a lossless-enough mp4 in seconds. DaVinci Studio (paid) handles WebM natively; if the user has the free edition, add this step.

8. **WSL audio is separate.** `page.screencast` does not record audio (the page isn't playing any). All ambient/music audio is added in DaVinci. This is actually ideal — it means you don't need to worry about PulseAudio/PipeWire routing in WSL.

9. **Cloud-deployed frontend + localhost Playwright = make sure the URL is publicly reachable or tunnel it.** If the staging URL requires VPN/IP allowlisting, Playwright running on WSL needs the same network access. Test with `curl` first.

10. **Chapter cards are obtrusive.** `showChapter()` blurs the page and shows a full-screen card for `duration` ms. For a 30–60s hero video, one chapter card at the start is fine; three is usually too many. Consider using lighter `showOverlay()` HTML banners instead for mid-video section markers.

---

## Royalty-Free Ambient Audio (added in DaVinci)

- [YouTube Audio Library](https://studio.youtube.com/) — requires a YT account, but tracks are free for any use, CC0 or attribution-only
- [Pixabay Music](https://pixabay.com/music/) — large ambient/corporate library, free commercial use, no attribution required
- [Incompetech](https://incompetech.com/) — Kevin MacLeod's catalog, CC-BY (attribution required)
- [Free Music Archive](https://freemusicarchive.org/) — mixed licenses, filter for CC0/CC-BY

None of the recording tools in the primary stack mix audio natively; this is DaVinci's job.

---

## Limitations

- **Source coverage gap on mouse-helper internals.** The `cenfun/mouse-helper` README (verified via WebFetch) confirms it works with Playwright via `addInitScript` and shows three states, but does not document its click-effect customization in depth. A quick code read of `dist/mouse-helper.js` before adopting would be prudent.
- **`@playwright/cli` is <6 months old.** Released early 2026; ecosystem still settling. Expect minor API churn. If stability matters more than cutting-edge features, use Playwright Test Runner + `page.screencast` directly (same API, older package).
- **`agentskills.so` page for `playwright-recording` returned 403** during research, so claims about that specific skill rely on the toolkit's main README rather than the skill's self-documentation.
- **Anthropic computer-use demo** was identified but not deeply evaluated — it runs Ubuntu + Claude in a Docker container with VNC, which *could* be recorded, but adds a full VM layer that `page.screencast` makes unnecessary. Flagged for completeness; not recommended for this use case.
- **No hands-on testing performed.** All findings are based on official docs, maintainer-authored release notes, and primary GitHub READMEs. Real-world cursor-rendering fidelity and WSL1 vs WSL2 behavior should be validated with a 5-minute proof-of-concept before committing.

---

## Next Steps for the User

1. **Proof-of-concept (30 minutes)**: on a fresh directory, `npm i -D @playwright/test mouse-helper`, write a 20-line script that records a 10-second clip of any public site with `showActions` + `mouse-helper` on, run on WSL, confirm the cursor is visible in the WebM. This validates the entire stack with one afternoon's work.
2. **If PoC passes**: share your narrative script + staging URL in a Claude Code session, let Claude write the per-section `.spec.ts` files.
3. **If PoC fails on cursor rendering**: fall back to `page.screencast.showActions()` alone — the action labels are often more compelling for a marketing demo than the cursor anyway.
4. **Polish in DaVinci**: cut, transitions, ambient music, title card, export 1080p mp4 at ~8 Mbps for the landing page.

---

## Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | Playwright Screencast API (official) | HIGH (Microsoft official docs) | https://playwright.dev/docs/api/class-screencast |
| 2 | Playwright videos docs (official) | HIGH (Microsoft official docs) | https://playwright.dev/docs/videos |
| 3 | Playwright release notes (official) | HIGH (Microsoft official docs) | https://playwright.dev/docs/release-notes |
| 4 | Playwright MCP video tool (official) | HIGH (Microsoft official docs) | https://playwright.dev/mcp/tools/video |
| 5 | Playwright CLI Video Recording deep-dive (knightli.com, Apr 2026) | MEDIUM (blog, aligned with official) | https://www.knightli.com/en/2026/04/15/playwright-cli-video-recording/ |
| 6 | What's new in Playwright 1.59 (bug0.com) | MEDIUM (analyst blog) | https://bug0.com/blog/whats-new-playwright-1-59 |
| 7 | @playwright/cli on npm | HIGH (official npm registry) | https://www.npmjs.com/package/@playwright/cli |
| 8 | microsoft/playwright-mcp (GitHub) | HIGH (Microsoft official) | https://github.com/microsoft/playwright-mcp |
| 9 | Playwright Issue #6629 — cursor in video | HIGH (official issue tracker) | https://github.com/microsoft/playwright/issues/6629 |
| 10 | Playwright Issue #1374 — mouse helper | HIGH (official issue tracker) | https://github.com/microsoft/playwright/issues/1374 |
| 11 | cenfun/mouse-helper (GitHub) | MEDIUM (community library, MIT) | https://github.com/cenfun/mouse-helper |
| 12 | Xetera/ghost-cursor (GitHub) | HIGH (widely-used OSS lib) | https://github.com/Xetera/ghost-cursor |
| 13 | reaz1995/ghost-cursor-playwright (GitHub) | MEDIUM (community fork) | https://github.com/reaz1995/ghost-cursor-playwright |
| 14 | digitalsamba/claude-code-video-toolkit (GitHub) | MEDIUM (~937 stars, MIT) | https://github.com/digitalsamba/claude-code-video-toolkit |
| 15 | calesthio/OpenMontage (GitHub) | MEDIUM (AGPLv3, comprehensive) | https://github.com/calesthio/OpenMontage |
| 16 | browser-use/browser-use (GitHub) | HIGH (popular OSS agent) | https://github.com/browser-use/browser-use |
| 17 | browser-use Issue #4533 — record command | HIGH (official issue tracker) | https://github.com/browser-use/browser-use/issues/4533 |
| 18 | browser-use/video-use (GitHub) | MEDIUM (Claude Code editor skill) | https://github.com/browser-use/video-use |
| 19 | korwabs/playwright-record-mcp (GitHub) | MEDIUM (community MCP fork) | https://github.com/korwabs/playwright-record-mcp |
| 20 | browserbase/stagehand (GitHub) | HIGH (MIT, ~10k stars) | https://github.com/browserbase/stagehand |
| 21 | Skyvern-AI/skyvern (GitHub) | HIGH (AGPLv3, well-funded) | https://github.com/Skyvern-AI/skyvern |
| 22 | Anthropic computer-use demo | HIGH (Anthropic official) | https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo |
| 23 | siddharthvaddem/openscreen (GitHub) | MEDIUM (~16k stars) | https://github.com/siddharthvaddem/openscreen |
| 24 | imbhargav5/open-recorder (GitHub) | MEDIUM (Tauri/Rust) | https://github.com/imbhargav5/open-recorder |
| 25 | microsoft/wslg (GitHub) | HIGH (Microsoft official) | https://github.com/microsoft/wslg |
| 26 | jingbinw/ai-playwright-automation (GitHub) | MEDIUM (example project) | https://github.com/jingbinw/ai-playwright-automation |
| 27 | Playwright MCP field guide (Medium) | MEDIUM (analyst blog) | https://medium.com/@adnanmasood/playwright-and-playwright-mcp-a-field-guide-for-agentic-browser-automation-f11b9daa3627 |
| 28 | Generate Playwright Tests Without Code Access (DEV.to, Debbie O'Brien) | HIGH (Playwright DevRel) | https://dev.to/debs_obrien/generate-playwright-tests-without-code-access-using-mcp-and-copilot-2m05 |
| 29 | How to Integrate Playwright MCP for AI-Driven Test Automation (Microsoft Community Hub) | HIGH (Microsoft official community) | https://techcommunity.microsoft.com/blog/azuredevcommunityblog/how-to-integrate-playwright-mcp-for-ai-driven-test-automation/4470372 |
| 30 | kmsgrab vs x11grab (Tony Tascioglu wiki) | MEDIUM (technical wiki) | https://wiki.tonytascioglu.com/scripts/ffmpeg/kmsgrab_screen_capture |
