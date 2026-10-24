[![GitHub release](https://img.shields.io/github/v/release/deuza/proxy_stockfish?style=plastic)](https://github.com/deuza/proxy_stockfish/releases)
![GitHub Release Date](https://img.shields.io/github/release-date/deuza/proxy_stockfish)
[![GitHub last commit](https://img.shields.io/github/last-commit/deuza/proxy_stockfish?style=plastic)](https://github.com/deuza/proxy_stockfish/commits/main)
![GitHub commit activity](https://img.shields.io/github/commit-activity/t/deuza/proxy_stockfish)

[![License: CC0](https://img.shields.io/badge/license-CC0_1.0-lightgrey.svg?style=plastic)](https://creativecommons.org/publicdomain/zero/1.0/)
![Hack The Planet](https://img.shields.io/badge/hack-the--planet-black?style=flat-square\&logo=gnu\&logoColor=white)
![Built With Love](https://img.shields.io/badge/built%20with-%E2%9D%A4%20by%20DeuZa-red?style=plastic)

# Stockfish Remote Proxy

A small Python proxy that runs Stockfish on a remote server over SSH and
presents it to your local chess GUI (Arena, Lucas Chess, Scid vs PC,
ChessBase, ...) as if the engine were installed locally.

Use the horsepower of a dedicated server, a VPS or a spare machine for your
analysis, from any Windows, Linux or macOS desktop.

**Please read this README once in full before starting.** It is deliberately
exhaustive. If everything goes well the whole setup takes less than 30 minutes.

## Features

- **Transparent proxy**: the remote Stockfish behaves like a local engine
- **UCI**: every UCI command is forwarded unchanged to the engine
- **Auto-configuration**: threads, hash, MultiPV, ponder and any custom option
  are applied at startup from `config.json`
- **Analysis state tracking**: `go infinite` / `stop` are handled so the GUI
  never races the engine
- **Synchronisation**: the proxy waits for `uciok`, `readyok` and `bestmove`
  where it matters, with timeouts
- **Native OpenSSH**: no PuTTY, no plink, no `.ppk` keys, no Python SSH library
- **Cross-platform**: Windows, Linux and macOS clients
- **Logging**: optional detailed log file for debugging
- **Key-based authentication only**: no password anywhere

## Requirements

### Local machine (Windows, Linux or macOS)

- **Python 3.x**: [python.org/downloads](https://www.python.org/downloads/)
  - Windows: tick "Add Python to PATH" during installation
- **OpenSSH client**: shipped with Linux and macOS; on Windows 10/11 it is an
  optional feature, see
  [Microsoft's OpenSSH installation guide](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse).
  Check with `ssh -V` in a terminal.
- **An OpenSSH private key** (`id_ed25519` or `id_rsa`) **without a
  passphrase**. The proxy runs `ssh` in batch mode, nobody is there to type a
  passphrase. Alternative: a passphrase-protected key loaded in a running
  `ssh-agent` also works.

### Remote server

- **Stockfish** installed
- **sshd** with public key authentication for your user
- Any Unix-like host works: Debian/Ubuntu is used in the examples below,
  macOS with Homebrew has been tested too (`/opt/homebrew/bin/stockfish`)

Recommended resources:

- 4 CPU cores minimum to feel a real gain
- 8 GB RAM minimum for deep analysis
- A stable connection, ideally under 50 ms latency

## Installation

### 1. Remote server (Debian/Ubuntu)

Install Stockfish (prefix with `sudo` if you are not root, running Stockfish
under a dedicated unprivileged user is a very good idea):

```bash
apt install stockfish
```

Check the installation, then type `quit` to leave:

```bash
stockfish
```

You should see the engine banner, for example
`Stockfish 17.1 by the Stockfish developers (see AUTHORS file)`.

Find the binary path, you will need it in `config.json`:

```bash
which stockfish
```

Usually `/usr/games/stockfish` on Debian/Ubuntu.

### 2. Local machine

#### SSH key

Generate a key without a passphrase (`-N ""`). Ed25519 is the recommended
type, RSA still works:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
```

Copy the public key to the server:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@your-server.example.com
```

Without `ssh-copy-id` (older Windows builds), do it by hand:

```bash
cat ~/.ssh/id_ed25519.pub | ssh user@your-server.example.com "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Reference: [ssh-keygen(1)](https://man.openbsd.org/ssh-keygen.1),
[ssh-copy-id(1)](https://manpages.debian.org/trixie/openssh-client/ssh-copy-id.1.en.html).

#### Optional hardening

Since this key will only ever run Stockfish, you can lock it down on the
server side. Edit `~/.ssh/authorized_keys` on the server and prefix the key
with a forced command and the `restrict` option:

```text
restrict,command="/usr/games/stockfish" ssh-ed25519 AAAA... you@laptop
```

With this, the key cannot open a shell, forward ports or do anything else than
launch Stockfish, whatever the client asks for. See the
`AUTHORIZED_KEYS FILE FORMAT` section of
[sshd(8)](https://man.openbsd.org/sshd.8).

#### Get the project

```bash
git clone https://github.com/deuza/proxy_stockfish.git
cd proxy_stockfish
```

#### Edit config.json

A ready-to-edit `config.json` ships with the project:

```json
{
  "host": "your-server.example.com",
  "username": "your-user",
  "port": 22,
  "key_file": "~/.ssh/id_ed25519",
  "stockfish_command": "/usr/games/stockfish",
  "logging_enabled": true,
  "log_file": "debug.log",

  "_comment_stockfish": "Adjust to your server: sf_threads = nproc, sf_hash = half of the RAM in MB",
  "sf_threads": 4,
  "sf_hash": 2048,
  "sf_multipv": 1,
  "sf_ponder": false,

  "sf_options": {
    "Skill Level": 20,
    "UCI_ShowWDL": true
  },

  "ssh_options": ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
}
```

##### Connection parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `host` | IP address or hostname of the server | `"chess.example.com"` |
| `username` | Remote user | `"pi"`, `"stockfish"`, ... |
| `port` | SSH port | `22` |
| `key_file` | Path to your OpenSSH private key | `"~/.ssh/id_ed25519"` |
| `stockfish_command` | Path of the `stockfish` binary on the server | `"/usr/games/stockfish"` |
| `logging_enabled` | Write a log file | `true` or `false` |
| `log_file` | Log file name, next to the script | `"debug.log"` |
| `ssh_options` | Extra arguments passed to `ssh` | see below |

`key_file` accepts `~` on every OS (on Windows it expands to
`C:\Users\<you>`). A relative path is resolved from the script directory. If
your key lives somewhere else, use an absolute path, forward slashes are fine
on Windows:

```json
"key_file": "D:/keys/chess_ed25519"
```

Default `ssh_options`:

- `BatchMode=yes`: `ssh` never prompts for anything (passphrase, password).
  If it cannot authenticate it fails immediately instead of hanging the GUI.
- `StrictHostKeyChecking=accept-new`: the server host key is recorded on the
  first connection and refused afterwards if it changes. No interactive
  "Are you sure you want to continue connecting?" prompt, no silent acceptance
  of a changed key either.

##### Stockfish parameters

| Parameter | Description | Recommended value |
|-----------|-------------|-------------------|
| `sf_threads` | Number of CPU threads | number of cores of the server |
| `sf_hash` | Hash table size in MB | half of the server RAM |
| `sf_multipv` | Number of lines analysed | `1` (single line), `3` to `5` (multi-line) |
| `sf_ponder` | Think during the opponent's turn | `false` (avoids lock-ups) |
| `sf_options` | Any other UCI option, as `"name": value` | optional |

Shipped values (`4` threads, `2048` MB) are deliberately small so that the
proxy cannot bring a modest server to its knees on first launch. Raise them to
match your hardware:

- Threads: output of `nproc` on the server
- Hash: half of the total RAM in MB, which leaves room for the OS and the
  rest:

```bash
awk '/MemTotal/ {print int($2/2048)}' /proc/meminfo
```

Typical values:

| Server | `sf_threads` | `sf_hash` |
|--------|--------------|-----------|
| Raspberry Pi 5, 4 cores, 8 GB | 4 | 4096 |
| Mid-range VPS, 8 cores, 16 GB | 8 | 8192 |
| Dedicated server, 16+ cores, 32+ GB | 16 | 16384 |

Too large a hash is the most common mistake: the server fills its RAM, then
its swap, then falls over. When in doubt, start low.

### 3. Validation tests

#### Test 1: manual SSH connection

```bash
ssh -i ~/.ssh/id_ed25519 -p 22 user@your-server.example.com
```

Expected: you are logged in without being asked for a password or a
passphrase. Type `exit` to leave. (If you applied the optional hardening
above, you will get Stockfish instead of a shell: type `quit`.)

#### Test 2: the proxy itself

```bash
python proxysf.py
```

On startup the proxy performs its own `uci` / `isready` handshake with the
engine and applies your configuration, so you will see the engine banner, the
UCI option list, `uciok` and `readyok` scroll by before you type anything.
Then type:

```text
uci
isready
quit
```

You should get the option list ending with `uciok`, then `readyok`, then the
proxy exits.

With `logging_enabled` set to `true`, `debug.log` shows the auto-configuration:

```text
INFO - Initializing Stockfish with custom configuration...
INFO - Setting Stockfish threads to 4
INFO - Setting Stockfish hash to 2048MB
INFO - Setting Stockfish MultiPV to 1
INFO - Setting Stockfish Ponder to false
INFO - Stockfish initialization completed.
```

If both tests pass you are done. The next section is optional.

### 4. Building an executable (optional)

Most GUIs can launch a Python script directly, but a single-file executable
is easier to register as an engine. PyInstaller does it in one command:

```bash
pip install pyinstaller
pyinstaller --onefile --console proxysf.py
```

The result is `dist/proxysf.exe` on Windows,
`dist/proxysf` on Linux and macOS. The executable looks for
`config.json` in its own directory, so copy it next to the binary:

```bash
cp config.json dist/
```

### 5. Testing the executable

```text
cd dist
./proxysf        (Linux, macOS)
.\proxysf.exe    (Windows)
```

Same session as test 2: `uci`, `isready`, `quit`.

## Auto-configuration

At startup, before the GUI sends its first command, the proxy:

1. sends `uci` and waits for `uciok`
2. sets `Threads` from `sf_threads`
3. sets `Hash` from `sf_hash`
4. sets `MultiPV` from `sf_multipv`
5. sets `Ponder` from `sf_ponder`
6. sets every option listed in `sf_options`
7. sends `isready` and waits for `readyok`

The GUI can still change any option afterwards, it will simply override the
proxy's value. The recommended split: let the proxy own the server resources
(threads, hash), let the GUI own the game settings.

## Using the proxy in a chess GUI

### Arena

1. Launch Arena
2. `Engines` > `Install New Engine...`
3. Select `proxysf.exe` (or `proxysf` on Linux/macOS)
4. Engine type: `UCI`
5. Confirm

Arena now drives your remote Stockfish like any local engine, already
configured with the server resources from `config.json`.

### Other GUIs

Anything that speaks UCI should work: Lucas Chess, Scid vs PC, ChessBase, ...

## Infinite analysis handling

When the engine is in `go infinite` mode and the GUI sends another command,
the proxy:

1. sends `stop` to the engine
2. waits for `bestmove` (10 s timeout)
3. forwards the queued command

This prevents the GUI from flooding an engine that is still searching.

## Logs and debugging

With `"logging_enabled": true`, the proxy writes to `log_file` (default
`debug.log`, next to the script or the executable):

- the exact `ssh` command line used
- every line received from the engine
- every command typed by the GUI
- the auto-configuration steps
- SSH errors (stderr), timeouts, broken pipes

Set `logging_enabled` to `false` once everything works, the log grows fast
during long analysis sessions.

## Troubleshooting

### "ssh binary not found in PATH"

- Linux/macOS: install the OpenSSH client package of your distribution
- Windows: install the "OpenSSH Client" optional feature (link in the
  Requirements section), then open a new terminal and check `ssh -V`

### "Key file not found"

- Check the `key_file` path in `config.json`
- `ls -l ~/.ssh/id_ed25519` (Linux/macOS) or `dir %USERPROFILE%\.ssh`
  (Windows) to see what you actually have
- Use an absolute path if in doubt

### SSH connection fails

- Check `host`, `username`, `port`
- Check that your public key is in `~/.ssh/authorized_keys` on the server
- Run test 1 by hand, `ssh` prints a much better error than the proxy
- With `BatchMode=yes`, a key with a passphrase (and no agent) fails silently
  from the GUI's point of view: look at `debug.log`, the `STDERR` lines are
  there

### "Stockfish not found" or immediate disconnection

- Check `stockfish_command`, run `which stockfish` on the server
- Try the exact command over SSH:
  `ssh -i ~/.ssh/id_ed25519 user@host /usr/games/stockfish`

### Configuration not applied

- Validate the JSON syntax of `config.json` (a trailing comma is enough to
  break it)
- Read `debug.log`: every `setoption` is logged, and so is any failure
- Make sure values are within the engine limits: the `option name ... min
  ... max ...` lines printed after `uci` give them for your Stockfish version

### Engine stuck or running away

- The proxy sends `stop` automatically where needed
- If the GUI itself is stuck, `Ctrl+C` in the proxy console, or see the
  emergency stop below
- Then read the log

### Emergency stop

Server side:

```bash
killall stockfish
ps aux | grep [s]tockfish     # must print nothing
```

Local side, Windows (PowerShell):

```powershell
taskkill /f /im proxysf.exe
```

Local side, Linux/macOS:

```bash
pkill -f proxysf
```

### Multiple instances

The proxy does **not** check for other running instances. If you launch
several at once (engine tournaments with several workers, repeated tests...),
each one starts its own Stockfish on the server, each with its own hash. RAM
fills up, then swap, then the server crashes.

- Run a single proxy instance at a time
- During tournaments, keep `htop` open on the server
- Clean up leftover `stockfish` processes before relaunching

## How it works

```text
   +-----------------------+
   |  Chess GUI (UCI)      |   Arena, Lucas Chess, Scid vs PC, ...
   +-----------+-----------+
               |  stdin / stdout
               v
   +-----------------------+
   | proxysf   |   reads config.json, configures the engine,
   |                       |   tracks go/stop state, forwards everything
   +-----------+-----------+
               |  ssh -i key user@host stockfish
               v
   +-----------------------+
   |  Remote server        |
   |  sshd -> stockfish    |   Threads, Hash, MultiPV, ... from config.json
   +-----------------------+
```

Every line the engine prints goes back up the same pipe to the GUI.

## Distribution and security

### No prebuilt binary, on purpose

Only the source is published. Anyone can build their own executable in one
command (section 4). A prebuilt executable deserves suspicion by default:
anything could have been added to the code before compilation. If you still
want to use someone else's binary, check its checksum, scan it, and read the
source first.

### What the proxy does and does not do

- Key-based SSH authentication only, no password, nothing stored in clear
- Encrypted transport, obviously
- `ssh` runs in batch mode, it can never block on a prompt
- The remote command is exactly what you put in `stockfish_command`, nothing
  else is executed on the server (and with the optional `restrict,command=`
  hardening, nothing else *can* be)
- No instance management, no resource detection, no UCI parsing beyond the
  few markers it waits for: see below

## Known limitations

- Response time depends on the network latency to the server
- A stable connection is required: if SSH drops, the engine is gone from the
  GUI's point of view
- The server needs enough free CPU and RAM for the values you configure
- No detection of server resources: you set `sf_threads` and `sf_hash` by hand
- No protection against multiple instances (see above)
- No protection against an oversized hash (see above)

### KISS

This proxy favours simplicity and reliability. The limitations above are
documented and manual workarounds are given, rather than growing the code with
instance management, UCI parsing, remote resource probing or other machinery
that would make it harder to read and to trust.

## Previous version (plink)

Version 0.0.1 of `proxysf.py` relied on PuTTY's `plink.exe` and `.ppk` keys,
and was Windows only. It is kept for reference under the git tag `v0.0.1`:

```bash
git show v0.0.1:proxysf.py
```

## License

[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/). Do
whatever you want with it.

---

Tested with Stockfish 17.1 and 19, clients on Windows 11, Debian 12 and
macOS, servers on Debian and macOS (Homebrew).
