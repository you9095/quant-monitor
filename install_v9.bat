@echo off&chcp 437>nul&title AI Quant Installer v9&cd /d "%~dp0"&(py -3 -x "%~f0" %* || python -x "%~f0" %*)&echo.&echo === Installer ended. Read the lines above, then press any key to close. ===&pause&exit /b
# AI Quant Monitor - self-healing installer (Python body). Line 1 is a cmd
# launcher skipped by "python -x". Everything below is plain Python and runs
# under top-level exception protection, so it can never silently flash-close.
# VERSION: 2026-10-04  v9  PYTHON-CORE
import os
import sys
import subprocess
import shutil
import socket
import time
import glob
import traceback
import webbrowser

WIN = sys.platform.startswith("win")

# ---- paths / constants (Windows targets; on macOS only --selftest runs) ----
INSTALL_DIR = r"D:\quant-monitor"
STATUS_DIR = r"D:\_qm_live"
CODE_SSH = "git@github.com:you9095/quant-monitor.git"
CODE_HTTPS = "https://github.com/you9095/quant-monitor.git"
DATA_SSH = "git@github.com:you9095/quant-monitor-live-data.git"
DATA_HTTPS = "https://github.com/you9095/quant-monitor-live-data.git"
LOG_PATH = r"D:\quant-monitor-install.log" if WIN else os.path.join("/tmp", "qm_install_mac.log")
SSH_TEST_HOST = ["-p", "443", "-o", "HostName=ssh.github.com"]
PROXY_PORTS = [7890, 7897, 10809, 10808, 1080, 8888, 8080, 2080, 33210]
PIP_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple/",
    "https://pypi.mirrors.ustc.edu.cn/simple/",
]

LOG_LINES = []


def log(msg=""):
    line = str(msg)
    print(line, flush=True)
    LOG_LINES.append(line)


def run(cmd, timeout=120, cwd=None, env=None, check=False):
    """Run a command, capture output, append to the in-memory log."""
    log("  $ " + " ".join(str(c) for c in cmd))
    try:
        p = subprocess.run(
            cmd, cwd=cwd, env=env, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        out = p.stdout.decode("utf-8", "replace") if p.stdout else ""
        if out.strip():
            for ln in out.rstrip().splitlines():
                log("    " + ln)
        if check and p.returncode != 0:
            raise RuntimeError("command failed rc=%s: %s" % (p.returncode, " ".join(map(str, cmd))))
        return p.returncode, out
    except subprocess.TimeoutExpired:
        log("    [TIMEOUT after %ss]" % timeout)
        return 124, "TIMEOUT"
    except FileNotFoundError:
        log("    [command not found]")
        return 127, "NOTFOUND"


def home():
    return os.path.expanduser("~")


def ssh_dir():
    d = os.path.join(home(), ".ssh")
    os.makedirs(d, exist_ok=True)
    return d


# ----------------------------- Git / Python --------------------------------
def find_git():
    g = shutil.which("git")
    if g:
        return g
    candidates = []
    if WIN:
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(pf, "Git", "cmd", "git.exe"),
            os.path.join(pfx86, "Git", "cmd", "git.exe"),
            os.path.join(local, "Programs", "Git", "cmd", "git.exe"),
        ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def ensure_git_identity(git):
    rc, _ = run([git, "config", "--global", "--get", "user.name"])
    if rc != 0:
        run([git, "config", "--global", "user.name", "quant-windows"])
    rc, _ = run([git, "config", "--global", "--get", "user.email"])
    if rc != 0:
        run([git, "config", "--global", "user.email", "quant@local"])
    run([git, "config", "--global", "credential.helper", "manager"])
    run([git, "config", "--global", "http.version", "HTTP/1.1"])


# ----------------------------- Proxy ---------------------------------------
def detect_proxy():
    for port in PROXY_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            log("  [DIAG] local proxy detected on port %s" % port)
            return port
        except Exception:
            try:
                s.close()
            except Exception:
                pass
    log("  [DIAG] no local proxy detected")
    return None


# ----------------------------- SSH / key -----------------------------------
def enable_ssh_443():
    cfg = os.path.join(ssh_dir(), "config")
    block = ("\n# AI Quant: GitHub SSH over 443\n"
             "Host github.com\n"
             "  HostName ssh.github.com\n"
             "  Port 443\n"
             "  User git\n")
    existing = ""
    if os.path.exists(cfg):
        existing = open(cfg, "r", encoding="utf-8", errors="replace").read()
    if "ssh.github.com" not in existing:
        with open(cfg, "a", encoding="utf-8") as f:
            f.write(block)


def key_path():
    for name in ("id_ed25519", "id_rsa"):
        p = os.path.join(ssh_dir(), name)
        if os.path.exists(p):
            return p
    return os.path.join(ssh_dir(), "id_ed25519")


def ensure_key():
    kp = key_path()
    if os.path.exists(kp):
        return kp
    log("  No SSH key, generating ed25519 ...")
    run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "quant-windows", "-f", kp], timeout=60)
    return kp if os.path.exists(kp) else None


def fix_key_perms(kp):
    if WIN and kp:
        # Windows OpenSSH refuses keys that are too open.
        user = os.environ.get("USERNAME", "")
        run(["icacls", kp, "/inheritance:r", "/grant:r", "%s:F" % user])
        run(["icacls", kp, "/grant:r", "SYSTEM:F"])


def ssh_auth_test(timeout=25):
    """Return ('ok'|'denied'|'netfail'|'nokey', raw_output)."""
    kp = ensure_key()
    if not kp:
        return "nokey", "no key could be created"
    fix_key_perms(kp)
    enable_ssh_443()
    cmd = ["ssh", "-p", "443", "-o", "HostName=ssh.github.com",
           "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
           "-o", "ConnectTimeout=20", "-T", "git@github.com"]
    rc, out = run(cmd, timeout=timeout)
    low = out.lower()
    if "successfully authenticated" in low:
        return "ok", out
    if "permission denied" in low:
        return "denied", out
    return "netfail", out


def upload_key(kp):
    pub = kp + ".pub"
    # 1) gh CLI if available and authenticated
    rc, _ = run(["gh", "--version"])
    if rc == 0:
        rc2, _ = run(["gh", "auth", "status"])
        if rc2 == 0:
            run(["gh", "ssh-key", "add", pub, "--title", "quant-windows"])
            return True
    # 2) copy public key, open the add-key page
    if os.path.exists(pub):
        try:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            p.communicate(open(pub, "rb").read(), timeout=10)
        except Exception:
            pass
    webbrowser.open("https://github.com/settings/ssh/new")
    return False


def wait_for_link(kp, attempts=21, gap=10):
    log("  ACTION NEEDED: paste the key in the GitHub page that opened,")
    log("  then click 'Add SSH key'. This retries automatically (~%ss)." % (attempts * gap))
    upload_key(kp)
    for i in range(1, attempts + 1):
        status, _ = ssh_auth_test()
        if status == "ok":
            log("  key linked, continuing.")
            return True
        log("  ...waiting for key link, attempt %d/%d" % (i, attempts))
        time.sleep(gap)
    return False


# ----------------------------- clone ---------------------------------------
def git_env(channel, proxy_port=None):
    env = dict(os.environ)
    if channel == "ssh443":
        env["GIT_SSH_COMMAND"] = ("ssh -p 443 -o HostName=ssh.github.com "
                                  "-o StrictHostKeyChecking=accept-new "
                                  "-o BatchMode=yes -o ConnectTimeout=20")
    elif channel == "ssh22":
        env["GIT_SSH_COMMAND"] = ("ssh -o StrictHostKeyChecking=accept-new "
                                  "-o BatchMode=yes -o ConnectTimeout=15")
    else:
        env.pop("GIT_SSH_COMMAND", None)
        if proxy_port:
            url = "http://127.0.0.1:%s" % proxy_port
            env["HTTP_PROXY"] = url
            env["HTTPS_PROXY"] = url
    return env


def clone_fallback(git, ssh_url, https_url, dest, proxy_port, timeout=180):
    if os.path.exists(os.path.join(dest, ".git")):
        return "existing"
    parent = os.path.dirname(dest)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    for channel in ("ssh443", "ssh22", "https"):
        log("  trying %s ..." % channel)
        env = git_env(channel, proxy_port if channel == "https" else None)
        rc, out = run([git, "clone", ssh_url if channel != "https" else https_url, dest],
                      timeout=timeout, env=env)
        if rc == 0 and os.path.exists(os.path.join(dest, ".git")):
            return channel
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
    return "FAIL"


def hard_update(git, dest, proxy_port, timeout=120):
    env = git_env("ssh443", proxy_port)
    run([git, "fetch", "origin", "master"], cwd=dest, env=env, timeout=timeout)
    run([git, "reset", "--hard", "origin/master"], cwd=dest, env=env, timeout=timeout)


# ----------------------------- heartbeat -----------------------------------
def report(git, status_dir, stage, msg, proxy_port=None):
    try:
        if not os.path.exists(os.path.join(status_dir, ".git")):
            return False
        d = os.path.join(status_dir, "_install_status")
        os.makedirs(d, exist_ok=True)
        host = os.environ.get("COMPUTERNAME", socket.gethostname())
        with open(os.path.join(d, host + ".txt"), "a", encoding="utf-8") as f:
            f.write("%s | %s | %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), stage, msg))
        env = git_env("ssh443", proxy_port)
        run([git, "add", "-A"], cwd=status_dir, env=env)
        run([git, "commit", "-m", "install %s %s" % (host, stage)], cwd=status_dir, env=env)
        run([git, "pull", "--no-rebase", "origin", "master"], cwd=status_dir, env=env)
        rc, _ = run([git, "push", "origin", "master"], cwd=status_dir, env=env)
        return rc == 0
    except Exception as e:
        log("  [report failed] %s" % e)
        return False


# ----------------------------- diagnostics ---------------------------------
def desktop_dir():
    d = os.path.join(home(), "Desktop")
    return d if os.path.isdir(d) else home()


def dump_diagnostics(extra=""):
    try:
        path = os.path.join(desktop_dir(), "quant-install-log.txt")
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write("AI Quant installer diagnostics\n")
            f.write("time: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            f.write("python: %s\n" % sys.version)
            f.write("platform: %s\n" % sys.platform)
            if extra:
                f.write("\n==== ERROR ====\n%s\n" % extra)
            f.write("\n==== LOG ====\n")
            f.write("\n".join(LOG_LINES[-400:]))
        log("\nDiagnostics saved to: %s" % path)
        if WIN:
            try:
                os.startfile(path)  # opens in Notepad via .txt association
            except Exception:
                subprocess.Popen(["notepad", path])
        return path
    except Exception as e:
        log("  [could not write diagnostics] %s" % e)
        return None


# ----------------------------- main install --------------------------------
def main_install():
    log("=" * 50)
    log("  AI Quant Monitor installer  v9 (PYTHON-CORE)")
    log("  target: %s" % INSTALL_DIR)
    log("  mode: simulation, no real broker account")
    log("=" * 50)

    if not WIN:
        log("Not Windows; run --selftest on this machine.")
        return 2
    if not os.path.exists("D:\\"):
        raise RuntimeError("D: drive not found; this installer requires D:")

    git = find_git()
    if not git:
        raise RuntimeError("Git not found. Install Git for Windows from "
                           "https://git-scm.com/download/win then run again.")
    rc, gv = run([git, "--version"])
    log("  git: %s" % gv.strip())
    ensure_git_identity(git)

    proxy_port = detect_proxy()

    log("[1/5] SSH authentication self-test ...")
    status, raw = ssh_auth_test()
    log("  ssh auth: %s" % status)
    if status == "denied":
        kp = key_path()
        if not wait_for_link(kp):
            dump_diagnostics("SSH key was not linked to GitHub in time.\n"
                             "Add it at https://github.com/settings/ssh/new then run again.")
            return 1
        status, raw = ssh_auth_test()
    if status not in ("ok",):
        # even if 443 probe was inconclusive, let clone try all channels
        log("  ssh443 probe status=%s; clone will still try every channel" % status)

    log("[2/5] connecting data channel first ...")
    if os.path.exists(os.path.join(STATUS_DIR, ".git")):
        mode = "existing"
        run([git, "pull", "--no-rebase", "origin", "master"], cwd=STATUS_DIR,
            env=git_env("ssh443", proxy_port))
    else:
        mode = clone_fallback(git, DATA_SSH, DATA_HTTPS, STATUS_DIR, proxy_port)
    if mode == "FAIL":
        hint = {
            "denied": "SSH key not linked to GitHub.",
            "nokey": "No SSH key could be created.",
            "netfail": ("Network blocks GitHub and no proxy was found. "
                        "Start Clash/VPN in global/TUN mode then run again."),
        }.get(status, "All channels failed; see log.")
        dump_diagnostics("Cannot reach GitHub. Cause: %s\n\nssh output:\n%s" % (hint, raw))
        return 1
    report(git, STATUS_DIR, "ONLINE", "connected via %s; auth=%s; proxy=%s"
           % (mode, status, proxy_port), proxy_port)
    log("  data channel ONLINE via %s" % mode)

    log("[3/5] getting latest code ...")
    if os.path.exists(os.path.join(INSTALL_DIR, ".git")):
        hard_update(git, INSTALL_DIR, proxy_port)
        cmode = "existing"
    else:
        if os.path.isdir(INSTALL_DIR):
            backup = INSTALL_DIR + "-old"
            try:
                if os.path.exists(backup):
                    shutil.rmtree(backup, ignore_errors=True)
                os.rename(INSTALL_DIR, backup)
            except Exception as e:
                log("  backup warning: %s" % e)
        cmode = clone_fallback(git, CODE_SSH, CODE_HTTPS, INSTALL_DIR, proxy_port)
    if cmode == "FAIL":
        report(git, STATUS_DIR, "FAILED", "code clone failed", proxy_port)
        dump_diagnostics("Could not clone the code repository.")
        return 1
    report(git, STATUS_DIR, "CODE_READY", "code via %s" % cmode, proxy_port)

    log("[4/5] running setup.py (venv + deps + tasks + self-test) ...")
    report(git, STATUS_DIR, "SETUP_START", "setup.py starting", proxy_port)
    env = git_env("ssh443", proxy_port)
    rc, out = run([sys.executable, "setup.py"], cwd=INSTALL_DIR, env=env, timeout=1800)

    log("[5/5] result rc=%s" % rc)
    if rc == 0:
        report(git, STATUS_DIR, "SUCCESS", "install finished, setup rc=0", proxy_port)
        log("=" * 50)
        log("  ALL DONE - INSTALL FINISHED")
        log("  Start panel: double-click  %s\\start.bat" % INSTALL_DIR)
        log("  then open http://localhost:8000  (simulation, no real broker)")
        log("=" * 50)
        return 0
    report(git, STATUS_DIR, "FAILED", "setup.py rc=%s" % rc, proxy_port)
    dump_diagnostics("setup.py returned %s.\n\nTail:\n%s" % (rc, out[-3000:]))
    return 1


# ----------------------------- selftest (mac) ------------------------------
def selftest():
    """Read-only checks runnable on macOS to prove the connection logic."""
    log("SELF-TEST (read-only, no install)")
    git = find_git()
    log("git: %s" % git)
    if git:
        rc, v = run([git, "--version"])
    proxy = detect_proxy()
    log("detected proxy port: %s" % proxy)
    enable_ssh_443()
    log("ssh config ensured at %s" % os.path.join(ssh_dir(), "config"))
    status, raw = ssh_auth_test()
    log("ssh.github.com:443 auth status: %s" % status)
    log("ssh raw (last line): %s" % raw.strip().splitlines()[-1] if raw.strip() else "(empty)")
    log("data repo ssh url: %s" % DATA_SSH)
    log("pip mirrors: %s" % len(PIP_MIRRORS))
    ok = (git is not None and status == "ok")
    log("SELF-TEST %s" % ("PASS" if ok else "CHECK"))
    return 0 if ok else 1


def _entry():
    try:
        if sys.stdout is not None:
            try:
                sys.stdout.reconfigure(errors="replace")
                sys.stderr.reconfigure(errors="replace")
            except Exception:
                pass
        if "--selftest" in sys.argv:
            rc = selftest()
        else:
            rc = main_install()
    except Exception:
        tb = traceback.format_exc()
        log("\n[FATAL] unexpected error:\n" + tb)
        dump_diagnostics(tb)
        rc = 1
    # final hard block so the window can never vanish on its own
    if WIN:
        try:
            input("\n[DONE] Press Enter to close this window . . . ")
        except Exception:
            pass
    sys.exit(rc if isinstance(rc, int) else 1)


if __name__ == "__main__":
    _entry()
