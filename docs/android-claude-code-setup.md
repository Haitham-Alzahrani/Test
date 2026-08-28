# Running Claude Code on Android (Termux + proot Debian)

Verified working on 2026-08-28: Claude Code v2.1.250, Opus 5, on an Android
phone with no laptop.

**The short version:** Claude Code ships no Android binary. Termux alone
will not work. You need a proot Debian container — and you must make sure
Debian uses *its own* Node, because Termux's `PATH` leaks through proot and
silently breaks everything.

---

## Why plain Termux fails

Termux's Node reports `process.platform === 'android'`. Claude Code's
postinstall maps that to the target `linux-arm64-android`, which has no
published build:

```
[@anthropic-ai/claude-code postinstall] Native binaries for linux-arm64-android
are not available on this release channel.
  Available: darwin-arm64, darwin-x64, linux-x64, linux-arm64,
             linux-x64-musl, linux-arm64-musl, win32-x64, win32-arm64
```

Note that `linux-arm64` **is** available. The goal is simply to run a Node
that identifies as `linux` instead of `android`.

This is a property of how Node was *built*, not of the kernel or the
environment. Unsetting `ANDROID_ROOT` and friends does nothing.

---

## Setup

### 1. Termux

Install from [F-Droid](https://f-droid.org/packages/com.termux/) or the
[GitHub releases](https://github.com/termux/termux-app/releases).
**Not** from Google Play — that build is abandoned.

```
pkg update && pkg upgrade -y
```

```
pkg install -y proot-distro
```

### 2. Debian container

```
proot-distro install debian
```

```
proot-distro login debian
```

Budget about 1 GB of storage.

### 3. Node — from Debian, not Termux

```
apt update
```

```
apt install -y curl git python3 python3-pip ripgrep
```

```
curl -fsSL https://deb.nodesource.com/setup_lts.x -o nodesource_setup.sh
```

```
bash nodesource_setup.sh
```

```
apt install -y nodejs
```

Debian's own `nodejs` package is usually too old, hence NodeSource.

### 4. Fix the PATH — the step everything hinges on

`proot-distro login` inherits Termux's `PATH`, so `node` and `npm` still
resolve to `/data/data/com.termux/files/usr/bin/` **inside Debian**. Every
command silently uses the Android build.

```
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

```
hash -r
```

Make it persist:

```
echo 'export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' >> ~/.bashrc
```

### 5. Verify before installing

Do not skip this. It is the difference between working and an hour of
confusing errors.

```
which node
```

```
node -p "process.platform"
```

Required output:

```
/usr/bin/node
linux
```

If you see `/data/data/com.termux/...` or `android`, the PATH fix did not
take. Stop and fix it before continuing.

### 6. Install Claude Code

npm 11 blocks postinstall scripts by default, and Claude Code needs its
postinstall to fetch the native binary. Allow it explicitly:

```
npm install -g --allow-scripts=@anthropic-ai/claude-code @anthropic-ai/claude-code
```

Success looks like **`added 2 packages`** — the second package is the
platform-native binary. If it says `added 1 package` with `allow-scripts`
warnings, the binary was not fetched.

```
claude
```

---

## Returning later

```
proot-distro login debian
```

```
claude
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Native binaries for linux-arm64-android are not available` | Running Termux's Node | Fix PATH (step 4), verify with step 5 |
| `claude native binary not installed` | postinstall blocked by npm | Reinstall with `--allow-scripts` (step 6) |
| `npm warn allow-scripts` persists | Package name truncated in the config | Quote it: `npm config set allow-scripts "@anthropic-ai/claude-code" --location=user` |
| `which node` shows a `com.termux` path | PATH leaked through proot | Step 4, then `hash -r` |
| Cross-session messaging warning on startup | proot user namespace has no uid mapping | Harmless — ignore |

### Diagnosing from scratch

If the platform detection misbehaves, read the actual rule rather than
guessing:

```
grep -n -i "android" "$(npm root -g)/@anthropic-ai/claude-code/install.cjs"
```

The relevant line is `if (platform === 'android')`, where `platform` comes
from `process.platform`.

---

## What this gets you

A phone that is a full Claude Code terminal — shell access, file editing,
git, and unrestricted network access from the device itself. For a mechanic
without a laptop, that is a working diagnostic and research terminal in your
pocket.

### Dead ends, so you don't repeat them

- Unsetting `ANDROID_ROOT`, `ANDROID_DATA`, `ANDROID_ART_ROOT` etc. —
  detection is not environment-based.
- `npm config set allow-scripts=...` without quotes — the shell truncates
  the value and the warning silently persists.
- Installing Claude Code before fixing PATH — it lands under Termux's npm
  prefix and must be reinstalled afterwards regardless.
- `uname -r` inside proot returns `6.17.0-PRoot-Distro`, with no "android"
  in it. The kernel string is *not* the detection mechanism.
