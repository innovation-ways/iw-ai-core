# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/innovation-ways/iw-ai-core/compare/v0.1.0...v0.2.0) (2026-07-06)


### Features

* **dashboard:** add /api/usage/llm/embed iframe view for external bars ([3558614](https://github.com/innovation-ways/iw-ai-core/commit/35586146dad3e1e5db3d680401de719014a2f498))
* **dashboard:** add JSON /api/usage/llm endpoint for external consumers ([77bfc77](https://github.com/innovation-ways/iw-ai-core/commit/77bfc779852cb78584c50a53d3994eed738d1fad))
* **docs:** add "Generate ALL" button to regenerate every catalog doc ([81063b1](https://github.com/innovation-ways/iw-ai-core/commit/81063b1f5b5b0ceeccbaaee043cc0c4cf45bb573))
* **docs:** brand-consistent rendering, D2 architecture diagrams, diagram validation ([79a34dd](https://github.com/innovation-ways/iw-ai-core/commit/79a34ddfcff57f0c3bd33ff961fb5499ba21c93d))
* **docs:** elegant paged document layout — cover, index, per-chapter pages, running header/footer ([d47a52e](https://github.com/innovation-ways/iw-ai-core/commit/d47a52ea68de5c1b9fcc30bf4d197b837d9fd6cd))
* **docs:** migration to persist _default doc-guide chapter/chrome rules ([88c8cf3](https://github.com/innovation-ways/iw-ai-core/commit/88c8cf31bd9f725356a7210f3333ab9d7a67e2fe))
* **mcp:** add HTTP transport so iw-mcp can run as an independent network service ([cd720c0](https://github.com/innovation-ways/iw-ai-core/commit/cd720c07a517e2f141360bf09410cda974faa90e))
* **mcp:** add MCP agent-control server exposing AI CORE to autonomous agents (R-00165) ([b789c25](https://github.com/innovation-ways/iw-ai-core/commit/b789c25e88927ff86b837351f92c118eaa7db307))
* **mcp:** make the iw-mcp entry point writable by default ([9f21b9a](https://github.com/innovation-ways/iw-ai-core/commit/9f21b9afbe63b2c7805f7d4b5a513d690619f754))
* **ops:** add MCP to the ai-core.sh menu, status badge, and a verify command ([9af210c](https://github.com/innovation-ways/iw-ai-core/commit/9af210cc18402aabd096edaf17b978cdb01f1144))
* **ops:** add systemd unit for reboot-persistent MCP HTTP server ([2a821db](https://github.com/innovation-ways/iw-ai-core/commit/2a821db234f81a5d005cb90c59d1e205ea2decf7))
* **ops:** manage the MCP HTTP server as a first-class ai-core.sh service ([aa415a8](https://github.com/innovation-ways/iw-ai-core/commit/aa415a8e68af9def5aee965b6dd24cd295e999d4))
* **research:** add diagram & chart visualization to research docs ([d25a9b0](https://github.com/innovation-ways/iw-ai-core/commit/d25a9b09cfd464daed038476f843829b5f90e497))
* **research:** richer report structure + wikilink rendering ([e15b91e](https://github.com/innovation-ways/iw-ai-core/commit/e15b91efe366e21d9b38645778eac6607f3d6921))


### Bug Fixes

* **daemon:** resolve pi_narration_guard.py by absolute path (all projects) ([d28b3f9](https://github.com/innovation-ways/iw-ai-core/commit/d28b3f9e0a6757843e8e24400acd1198bf52a741))
* **daemon:** resolve relative IW_CORE_PID_FILE against CORE_ROOT, not CWD ([cd3b8b8](https://github.com/innovation-ways/iw-ai-core/commit/cd3b8b8c99652cd3aefe294af572138ec88f9a91))
* **dashboard:** make usage-bar color a continuous gradient by percentage ([4cc3dc2](https://github.com/innovation-ways/iw-ai-core/commit/4cc3dc2137da4abbff7241f1467e917e9ac79c28))
* **dashboard:** send no-store on the usage embed so iframes never cache ([50a3744](https://github.com/innovation-ways/iw-ai-core/commit/50a3744ec3ea8519309ab888660a0bf529b2ae84))
* **db-backup:** unstick F-00092 poller ([36aaa6e](https://github.com/innovation-ways/iw-ai-core/commit/36aaa6e55b9958ce8f4ca85f6eec90208c2e0f98))
* **deps:** patch 14 CVEs in aiohttp, starlette, python-multipart, pip ([0284670](https://github.com/innovation-ways/iw-ai-core/commit/0284670e62921bf8eb9c8fc679ae5b592b4baf16))
* **docs:** render Mermaid on Markdown tab + persist HTML/PDF cache ([28d1fb2](https://github.com/innovation-ways/iw-ai-core/commit/28d1fb243b711b01a23ea764ae73b25e31de05c1))
* **executor:** gate frontend npm install on package.json, not dir presence ([63c0699](https://github.com/innovation-ways/iw-ai-core/commit/63c0699bcc447383b8c6d0884428269b3c908218))
* **mcp:** judge daemon liveness by DB heartbeat, not namespace-local PID ([fe6625e](https://github.com/innovation-ways/iw-ai-core/commit/fe6625e8cd708825152e4f88e63dd8b6a096dd61))
* **mcp:** materialise policy-list rows inside the session ([fba853a](https://github.com/innovation-ways/iw-ai-core/commit/fba853ad0e5dedbe11f58b701f980a49ff686773))
* **mcp:** refresh iwcore_workflow_guide to describe write tools + approval handshake ([cb4509b](https://github.com/innovation-ways/iw-ai-core/commit/cb4509b2993234f1a3700bb6374a59321d672180))
* **merge:** gate orch migration pipeline to the orch-DB project (I-00131) ([8888ec6](https://github.com/innovation-ways/iw-ai-core/commit/8888ec636d2906ff3c3d8907ce716765e1d4334d))
* **pi-chat:** realign iw-chat-approvals extension + approval bridge to Pi 0.79 ([07e3976](https://github.com/innovation-ways/iw-ai-core/commit/07e3976ce6832738d2f38fa3d58703dde4cda634))
* **runtime:** un-pinned projects inherit catalogue default, not hardcoded opencode ([25387ce](https://github.com/innovation-ways/iw-ai-core/commit/25387ce554f7870c6799154a1eda600b49fc30e5))
* **runtime:** update minimax M3 display labels (were stuck at "MiniMax 2.7") ([bd088bc](https://github.com/innovation-ways/iw-ai-core/commit/bd088bc272981fe03d6d8e8c7eb061f185320a86))
* **tests,pdf:** green the full suite + quality gates after doc-layout & migration merges ([82b58d3](https://github.com/innovation-ways/iw-ai-core/commit/82b58d3a51b18ba5ddf798b681a833244032a7d4))
* **usage:** correct MiniMax plan parsing (general bucket + percent + weekly) ([70a9d50](https://github.com/innovation-ways/iw-ai-core/commit/70a9d50cc1cc3e26d3d0ffd9d44f854f2ca98827))
* **usage:** keep embed bar colors under forced-colors / High-Contrast mode ([b0af60c](https://github.com/innovation-ways/iw-ai-core/commit/b0af60c63989879d38a37b6cf97c55b242cf36b6))
* **usage:** move embed bar width/color into &lt;style&gt; (no inline style attrs) ([9015b6e](https://github.com/innovation-ways/iw-ai-core/commit/9015b6e5a38bc67fa69e607b8523bb6129e821f2))
* **usage:** render embed bars as block so the colored fill is visible ([0f6048d](https://github.com/innovation-ways/iw-ai-core/commit/0f6048d85059cbcba30de91bb174ab542f2e041e))


### Documentation

* **mcp:** document HTTP transport, ufw/container networking, and Hermes HTTP client ([5f28fb9](https://github.com/innovation-ways/iw-ai-core/commit/5f28fb905a126cf1377f517e0445d49c135746c5))
* **projects:** document always_in_scope for edge/compose on browser-verified projects ([ac243df](https://github.com/innovation-ways/iw-ai-core/commit/ac243dfa084cbd0c91b301ebd45c4d7cd68d0566))

## [Unreleased]

### Added
- Initial public release scaffolding.

<!--
Section templates — use as entries are added:

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

Example entry:
### Added
- New `--json` output flag for scan mode ([#12](https://github.com/innovation-ways/IW AI Core Platform/pull/12))
-->
