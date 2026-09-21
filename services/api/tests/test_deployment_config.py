"""The deployment's configuration contract: what a clean clone needs, and what must never be in it.

Lives here rather than in a package for the same reason `test_packaging.py` does — it is the seam
between the repository, the edge Worker and the workflow that publishes them, and no package owns
that seam.

Two things it holds:

  **No credential is ever committed.** Config in this repo is identifiers and hostnames; anything
  that grants access is set by a human out of band. A token pasted into a file is a token that has
  to be rotated, and the scan is cheap next to noticing by hand.

  **Every value the Worker reads is a value somebody was told to set.** `NIGHT_TOKEN` was read at
  the edge, refused loudly when absent, and documented nowhere — so a correctly deployed platform
  would have worked no nights and said so only in a log nobody was tailing. A binding the code
  needs and the setup instructions omit is a silent outage waiting for a quiet night.
"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]
EDGE = ROOT / "deploy/cloudflare"

#: Prefixes that only ever appear on something live. Not an exhaustive scanner — that is what
#: GitHub's secret scanning is for — but these are the ones this platform's deploy actually uses,
#: and each one is a credential the moment it exists.
CREDENTIAL = re.compile(r"\bcfat_[A-Za-z0-9_-]{20,}|\bFlyV1 fm2_|\bsk-ant-[A-Za-z0-9_-]{20,}"
                        r"|\bghp_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")

TEXT = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".toml", ".yml", ".yaml", ".md", ".sh",
        ".env", ".cfg", ".ini", ".html", ".css", ""}


def _tracked() -> list[pathlib.Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout
    return [ROOT / p for p in out.split("\0") if p]


def test_no_credential_is_committed():
    here = pathlib.Path(__file__).resolve()
    offenders = []
    for path in _tracked():
        if path == here or path.suffix.lower() not in TEXT or not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if CREDENTIAL.search(body):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        f"A live credential is committed in {offenders}. Rotate it first — a secret in git "
        f"history is a secret that has been published — then set it out of band: a repository "
        f"secret for CI, `wrangler secret put` for the Worker.")


def test_the_edge_knows_which_account_it_deploys_to():
    """An identifier, so it is committed and a clean clone can publish without a flag nobody
    remembers. If this ever holds something that grants access, the scan above catches it."""
    toml = (EDGE / "wrangler.toml").read_text()
    assert re.search(r'^account_id = "[0-9a-f]{32}"$', toml, re.M), (
        "wrangler.toml declares no account_id, so `npm run deploy` from a clean clone cannot tell "
        "Cloudflare which account to publish to.")


def test_every_value_the_worker_reads_is_one_somebody_was_told_to_set():
    """The NIGHT_TOKEN regression: read at the edge, refused loudly when absent, documented
    nowhere. A correctly deployed platform would have worked no nights and said so only in a log
    nobody was tailing."""
    env_block = re.search(r"export interface Env \{(.+?)\n\}", (EDGE / "src/index.ts").read_text(),
                          re.S).group(1)
    names = set(re.findall(r"^\s*(\w+)\??:", env_block, re.M))

    # Configured, not merely mentioned: a binding or var wrangler actually declares, or a name
    # the setup instructions and the workflow tell a human to set. A passing reference in a
    # comment is how NIGHT_TOKEN went missing in the first place, so a comment does not count.
    toml = (EDGE / "wrangler.toml").read_text()
    configured = set(re.findall(r'binding\s*=\s*"(\w+)"', toml)) | \
        set(re.findall(r"^(\w+) = ", toml, re.M))
    told = (EDGE / "README.md").read_text() + (ROOT / ".github/workflows/deploy.yml").read_text()
    undocumented = sorted(n for n in names if n not in configured and n not in told)
    assert not undocumented, (
        f"The Worker reads {undocumented}, and nothing tells a deployer to set it. A binding the "
        f"code needs and the setup instructions omit is a silent outage waiting for a quiet "
        f"night.")
