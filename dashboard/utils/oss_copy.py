"""Human-readable copy for OSS compliance findings.

Provides domain-level context ("why this matters") and severity-level impact
("what happens if you publish anyway") used to build rich hover tooltips in
the OSS compliance page. Kept in one place so the editorial wording can be
reviewed alongside the iw-oss-publish skill's check catalog.
"""

from __future__ import annotations

from typing import TypedDict


class DomainCopy(TypedDict):
    name: str
    what: str
    risk: str


class SeverityCopy(TypedDict):
    label: str
    impact: str


DOMAIN_CONTEXT: dict[str, DomainCopy] = {
    "environment": {
        "name": "Environment pre-flight",
        "what": (
            "Basic preconditions for a scan to run: the target is a git repo, "
            "required tools are installed, and the skill config is resolvable."
        ),
        "risk": (
            "Without these, every other check becomes unreliable — findings may "
            "be false negatives because the tool could not execute."
        ),
    },
    "hygiene": {
        "name": "Repository hygiene",
        "what": (
            "Gitignore coverage, no tracked secret/state files, no oversized "
            "blobs, and a sane default branch."
        ),
        "risk": (
            "Hygiene gaps let developers accidentally commit `.env` files, "
            "private keys, or terraform state into a public repo — and bloat "
            "the clone with artifacts that should never have been tracked."
        ),
    },
    "secrets": {
        "name": "Secrets scanning",
        "what": (
            "Detects credentials, API keys, and tokens in the working tree and full git history."
        ),
        "risk": (
            "Publishing with live secrets is an immediate incident: credentials "
            "get scraped by automated bots within minutes, leading to cloud-account "
            "takeover, data exfiltration, and forced rotation across every system "
            "the secret touched."
        ),
    },
    "history": {
        "name": "Git history",
        "what": (
            "Enforces a history strategy before flip-to-public (nuke / "
            "filter-repo / preserve), surfaces contributor email leaks, and "
            "blocks internal submodule URLs."
        ),
        "risk": (
            "Once a commit is pushed to a public GitHub repo, GitHub indexes "
            "its SHA forever — even a later force-push cannot un-leak secrets "
            "or internal domains visible in old commits."
        ),
    },
    "internal_refs": {
        "name": "Internal references",
        "what": (
            "Finds RFC-1918 IPs, internal FQDNs (`.internal`, `.corp`, "
            "`.local`), absolute home paths, and employee email addresses "
            "outside SECURITY/CoC docs."
        ),
        "risk": (
            "Internal references give attackers a free map of your network and "
            "naming conventions. A single internal hostname in a README can "
            "narrow a reconnaissance target from thousands of companies to yours."
        ),
    },
    "ci": {
        "name": "CI / CD surface",
        "what": (
            "Checks GitHub Actions workflows for pinned SHAs, least-privilege "
            "permissions, no `pull_request_target` misuse, and no inline secrets."
        ),
        "risk": (
            "Unpinned actions execute whatever code the upstream maintainer "
            "publishes today — a supply-chain compromise of a popular action "
            "can run arbitrary code in your CI with your repo tokens."
        ),
    },
    "github": {
        "name": "GitHub live settings",
        "what": (
            "Verifies branch protection, signed-commit enforcement, secret "
            "scanning, Dependabot, and private-vulnerability-reporting are "
            "enabled on the live repo."
        ),
        "risk": (
            "Missing branch protection lets anyone with write access force-push "
            "to main or merge without review; missing secret scanning means "
            "leaks are caught weeks later in the wild rather than at push time."
        ),
    },
    "dependencies": {
        "name": "Dependencies & SBOM",
        "what": (
            "Generates SPDX / CycloneDX SBOMs, runs vulnerability scanners "
            "(grype, osv-scanner), and flags unresolved CVEs."
        ),
        "risk": (
            "Shipping a dependency with a known critical CVE exposes every "
            "downstream user of the library to the same bug — and is the #1 "
            "path through which supply-chain attacks propagate."
        ),
    },
    "license": {
        "name": "License & attribution",
        "what": (
            "Confirms the LICENSE file is present, OSI-approved, SPDX-matched, "
            "and that NOTICE / THIRD_PARTY_LICENSES are correct for the chosen "
            "license."
        ),
        "risk": (
            "Without a clear license, the project is legally un-usable — "
            "nobody can redistribute, fork, or build on it. Wrong copyright "
            "holders or missing NOTICE files can trigger claims of IP "
            "infringement."
        ),
    },
    "community": {
        "name": "Community health",
        "what": (
            "README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY policy, issue "
            "templates, and CODEOWNERS — the files GitHub's community tab "
            "checks for."
        ),
        "risk": (
            "Projects missing these rank lower on OpenSSF Scorecard, feel "
            "abandoned to would-be contributors, and have no documented path "
            "for responsible vulnerability disclosure."
        ),
    },
    "privacy": {
        "name": "Privacy & PII",
        "what": (
            "Looks for real-looking email addresses, phone numbers, and "
            "personal names in test fixtures and sample data."
        ),
        "risk": (
            "Even fictional-looking PII in fixtures can match real people; "
            "under GDPR this is a processing-without-consent violation and "
            "fixtures become subject to data-subject-access and erasure "
            "requests."
        ),
    },
    "export": {
        "name": "Export control",
        "what": (
            "Flags cryptography imports that may trigger US EAR / BIS "
            "notification requirements before public release."
        ),
        "risk": (
            "Publishing non-standard cryptography without BIS/NSA notification "
            "can violate US export law — penalties include fines per instance "
            "and export-privilege revocation."
        ),
    },
    "trademark": {
        "name": "Trademark & brand",
        "what": (
            "Checks for name collisions on package registries (PyPI, npm, "
            "crates.io) and surfaces reminders for manual USPTO / WIPO "
            "trademark searches."
        ),
        "risk": (
            "Publishing under a name that clashes with an existing trademark "
            "can force a rename after adoption has built momentum — breaking "
            "every URL, badge, and integration already deployed."
        ),
    },
    "contributor_agreement": {
        "name": "Contributor agreement",
        "what": (
            "Verifies DCO (sign-off) or CLA workflow is configured, and that "
            "the chosen mechanism is documented."
        ),
        "risk": (
            "Without DCO/CLA, the project has no paper trail that contributors "
            "had the right to license their work — acquirers and large "
            "corporate adopters will decline to use it until the gap is closed."
        ),
    },
    "release": {
        "name": "Release provenance",
        "what": (
            "Signed tags, release workflow on tag push, reproducible build "
            "metadata, and SLSA provenance attestations."
        ),
        "risk": (
            "Unsigned releases cannot be verified against tampering — a mirror "
            "or CDN compromise could swap the binary without any downstream "
            "signal."
        ),
    },
    "governance": {
        "name": "Governance",
        "what": (
            "Documented project governance, maintainer list, decision process, and a bus-factor >1."
        ),
        "risk": (
            "Single-maintainer projects are rejected by risk-averse adopters "
            "and downgraded by Scorecard — and lose all continuity the moment "
            "the maintainer steps away."
        ),
    },
}


SEVERITY_IMPACT: dict[str, SeverityCopy] = {
    "MUST": {
        "label": "Critical — blocks publish",
        "impact": (
            "Publishing with this failure is considered unsafe. The skill "
            "exits with code 1 and the publish playbook will refuse to run. "
            "If overridden, expect legal, security, or compliance exposure "
            "within hours of the repo going public."
        ),
    },
    "SHOULD": {
        "label": "Warning",
        "impact": (
            "Publishing is permitted, but the project will not meet "
            "best-practice expectations. Expect a lower OpenSSF Scorecard, "
            "reduced community trust, and a longer remediation backlog after "
            "the fact."
        ),
    },
    "INFO": {
        "label": "Informational",
        "impact": (
            "No publish block. Good to know, but the project is free to ship without addressing it."
        ),
    },
    "MAY": {
        "label": "Informational",
        "impact": "No publish block. Advisory nudge aimed at polish rather than safety.",
    },
}


STATUS_COPY: dict[str, dict[str, str]] = {
    "pass": {
        "label": "PASS",
        "line": "This check passed on the last scan.",
    },
    "fail": {
        "label": "FAIL",
        "line": "This check failed on the last scan.",
    },
    "skip": {
        "label": "SKIPPED",
        "line": (
            "This check was skipped — usually because a required tool is "
            "missing or the check was disabled in config."
        ),
    },
    "human_required": {
        "label": "HUMAN ATTESTATION",
        "line": (
            "This check cannot be automated and is waiting for a human "
            "attestation to be recorded in the skill config."
        ),
    },
    "accepted": {
        "label": "ACCEPTED",
        "line": "This finding has been accepted as a deliberate risk.",
    },
}


def domain_copy(domain: str) -> DomainCopy:
    return DOMAIN_CONTEXT.get(
        domain,
        {
            "name": domain.replace("_", " ").title(),
            "what": "Compliance check in this domain.",
            "risk": "Failing checks in this domain may reduce publish readiness.",
        },
    )


def severity_copy(severity: str) -> SeverityCopy:
    return SEVERITY_IMPACT.get(
        severity,
        {"label": severity, "impact": "Impact not classified."},
    )


def status_copy(status: str) -> dict[str, str]:
    return STATUS_COPY.get(status, {"label": status.upper(), "line": ""})
