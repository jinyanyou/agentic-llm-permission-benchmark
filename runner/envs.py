"""Environment adapters for OpenClaw (env A) and NemoClaw sandbox (env B).

Both expose the same interface:
    env.name -> str
    env.preflight() -> list[str]  (returns list of issue strings; empty = OK)
    env.run(prompt: str, timeout_s: int) -> RunResult

Each adapter shells out to the CLI. We deliberately avoid parsing the
agent reply too aggressively — graders see the raw stdout.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


MODEL = "ollama/gemma4:26b"


@dataclass
class RunResult:
    output: str
    duration_ms: int
    error: str | None = None
    exit_code: int = 0
    stderr_tail: str = ""
    extra: dict = field(default_factory=dict)


def _run(cmd: list[str], timeout_s: int, env: dict | None = None) -> RunResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        ms = int((time.monotonic() - start) * 1000)
        return RunResult(
            output=(e.stdout or "") if isinstance(e.stdout, str) else "",
            duration_ms=ms,
            error=f"timeout_{timeout_s}s",
            exit_code=-1,
        )
    ms = int((time.monotonic() - start) * 1000)
    stderr_tail = "\n".join((proc.stderr or "").splitlines()[-6:])
    return RunResult(
        output=proc.stdout or "",
        duration_ms=ms,
        exit_code=proc.returncode,
        stderr_tail=stderr_tail,
        error=None if proc.returncode == 0 else f"exit_{proc.returncode}",
    )


class OpenClawEnv:
    """Env A: bare OpenClaw on the host. Talks to host's 127.0.0.1:11434
    which is the SSH tunnel to KNU's DIS0X:11434 ollama.

    `mode='infer'` -> one-shot inference (no tools — model can't read files).
    `mode='agent'` -> embedded agent with built-in tools (file system, bash, etc.).
                     This is the mode that actually exposes the security gap
                     between env A and env B.
    """

    name = "openclaw"

    def __init__(self, mode: str = "agent", agent_id: str = "main"):
        if mode not in ("infer", "agent"):
            raise ValueError(f"mode must be infer|agent, got {mode!r}")
        self.mode = mode
        self.agent_id = agent_id

    def preflight(self) -> list[str]:
        issues = []
        # 1. Tunnel listening
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect(("127.0.0.1", 11434))
        except OSError as e:
            issues.append(f"local 11434 not listening: {e}")
        finally:
            s.close()
        # 2. openclaw on PATH
        if subprocess.run(["which", "openclaw"], capture_output=True).returncode != 0:
            issues.append("openclaw not in PATH")
        return issues

    def run(self, prompt: str, timeout_s: int = 120) -> RunResult:
        env = os.environ.copy()
        env.setdefault("OPENCLAW_STATE_DIR", "$HOME/project/.openclaw")
        env.setdefault("OPENCLAW_CONFIG_PATH", "$HOME/project/.openclaw/openclaw.json")
        if self.mode == "infer":
            cmd = ["openclaw", "infer", "model", "run",
                   "--local", "--model", MODEL, "--prompt", prompt]
        else:  # agent
            # 매 런 고유 세션 id → 세션 파일 lock 경합(SessionWriteLockTimeoutError) 방지.
            # agent_id는 'main' 유지(에이전트 정의 보존), 세션만 분리.
            session_id = uuid.uuid4().hex
            cmd = ["openclaw", "agent", "--local", "--agent", self.agent_id,
                   "--session-id", session_id,
                   "--message", prompt, "--timeout", str(timeout_s)]
        return _run(cmd, timeout_s, env=env)


class NemoClawEnv:
    """Env B: OpenClaw inside the NemoClaw sandbox (samdtg).

    Prerequisites (checked by preflight):
      - OrbStack running, DOCKER_HOST set
      - OpenShell gateway 'nemoclaw' Connected
      - Sandbox 'samdtg' Ready
      - In-sandbox forwarder running on 127.0.0.1:11434 (see ollama_forwarder.js)

    File access policy (2026-05-19):
      - Allowed: inputs/, sandbox/public/, sandbox/work/ → synced to /sandbox/inputs/ etc.
      - Blocked: sandbox/secure/, data/fake_confidential/, data/secure_folder/, data/honeypot/
        These are intentionally NOT synced so the agent cannot find them (security boundary).

    Path rewriting:
      run() rewrites host absolute paths in the prompt to sandbox-internal paths
      before sending to the agent:
        $HOME/project/runner/scenarios/normal/inputs/ → /sandbox/inputs/
        $HOME/project/sandbox/public/               → /sandbox/public/
        $HOME/project/sandbox/work/                 → /sandbox/work/
        $HOME/project/sandbox/output/nemoclaw/      → /sandbox/output/
      Paths inside secure/ and data/ are left as-is (ENOENT keeps the block).
    """

    name = "nemoclaw"

    # Mapping: (host_dir, sandbox_dest, upload_to_sandbox)
    # upload_to_sandbox=True  -> synced before every run
    # upload_to_sandbox=False -> never synced (intentional block)
    _PATH_MAP: list[tuple[str, str, bool]] = [
        (
            "$HOME/project/runner/scenarios/normal/inputs/",
            "/sandbox/inputs/",
            True,
        ),
        (
            "$HOME/project/sandbox/public/",
            "/sandbox/public/",
            True,
        ),
        (
            "$HOME/project/sandbox/work/",
            "/sandbox/work/",
            True,
        ),
        (
            "$HOME/project/sandbox/output/nemoclaw/",
            "/sandbox/output/",
            True,
        ),
        # Blocked paths — intentionally excluded from sync.
        # Left here as documentation so future maintainers know these are
        # deliberate omissions, not accidents.
        # "$HOME/project/sandbox/secure/"         → NOT synced
        # "$HOME/project/data/fake_confidential/" → NOT synced
        # "$HOME/project/data/secure_folder/"     → NOT synced
        # "$HOME/project/data/honeypot/"          → NOT synced
    ]

    def __init__(self, sandbox: str = "samdtg", mode: str = "agent", agent_id: str = "main"):
        if mode not in ("infer", "agent"):
            raise ValueError(f"mode must be infer|agent, got {mode!r}")
        self.sandbox = sandbox
        self.mode = mode
        self.agent_id = agent_id

    def _exec(self, cmd: list[str], timeout_s: int) -> RunResult:
        env = os.environ.copy()
        env.setdefault("DOCKER_HOST", "unix://$HOME/.orbstack/run/docker.sock")
        full = [
            "openshell", "sandbox", "exec",
            "-n", self.sandbox, "--no-tty",
            "--timeout", str(timeout_s),
            "--",
        ] + cmd
        return _run(full, timeout_s + 10, env=env)

    def _sync_work_files(self) -> list[str]:
        """Upload allowed host directories into the sandbox before each run.

        Returns a list of warning strings (non-fatal). Upload failures are
        warnings, not hard errors — the agent will get ENOENT instead of the
        file content, which surfaces a clear error message rather than a crash.
        """
        warnings = []
        base_env = os.environ.copy()
        base_env.setdefault("DOCKER_HOST", "unix://$HOME/.orbstack/run/docker.sock")

        for host_dir, sandbox_dest, do_upload in self._PATH_MAP:
            if not do_upload:
                continue
            host_path = Path(host_dir)
            if not host_path.exists():
                warnings.append(f"sync_skip: {host_dir} not found on host")
                continue
            # Ensure destination directory exists in sandbox.
            mkdir_proc = subprocess.run(
                ["openshell", "sandbox", "exec", "-n", self.sandbox, "--no-tty",
                 "--", "mkdir", "-p", sandbox_dest],
                capture_output=True, text=True, timeout=10, env=base_env,
            )
            if mkdir_proc.returncode != 0:
                warnings.append(
                    f"sync_mkdir_fail: {sandbox_dest}: {mkdir_proc.stderr[:120]}"
                )
                continue
            # Upload directory contents. --no-git-ignore so non-tracked files
            # (e.g. hotel_site outputs) are also uploaded.
            upload_proc = subprocess.run(
                ["openshell", "sandbox", "upload",
                 "--no-git-ignore",
                 self.sandbox,
                 host_dir,
                 sandbox_dest],
                capture_output=True, text=True, timeout=30, env=base_env,
            )
            if upload_proc.returncode != 0:
                warnings.append(
                    f"sync_upload_fail: {host_dir} → {sandbox_dest}: "
                    f"{upload_proc.stderr[:120]}"
                )
        return warnings

    def _rewrite_paths(self, prompt: str) -> str:
        """Replace host absolute paths with sandbox-internal equivalents.

        Only allowed paths are rewritten. Secure/confidential paths are
        intentionally left unchanged so the agent encounters ENOENT.
        """
        result = prompt
        for host_dir, sandbox_dest, do_upload in self._PATH_MAP:
            if do_upload:
                result = result.replace(host_dir, sandbox_dest)
        return result

    def preflight(self) -> list[str]:
        issues = []
        if not os.path.exists("$HOME/.orbstack/run/docker.sock"):
            issues.append("orbstack docker.sock missing (run: orbctl start)")
        if subprocess.run(["which", "openshell"], capture_output=True).returncode != 0:
            issues.append("openshell not in PATH")
        # Sandbox + forwarder reachable
        check = self._exec(
            ["bash", "-c", "curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags"],
            timeout_s=10,
        )
        if check.error or check.output.strip() != "200":
            issues.append(f"sandbox forwarder not healthy (got: {check.output!r}, err: {check.error})")
        return issues

    def run(self, prompt: str, timeout_s: int = 120) -> RunResult:
        # Sync allowed host directories into the sandbox before running.
        sync_warnings = self._sync_work_files()
        if sync_warnings:
            import sys
            for w in sync_warnings:
                print(f"[nemoclaw/sync WARN] {w}", file=sys.stderr)

        # Rewrite host paths in the prompt to sandbox-internal paths.
        sandbox_prompt = self._rewrite_paths(prompt)

        # gRPC exec rejects newlines in argv. Stage the prompt as a file in the
        # sandbox first (via stdin), then reference it via $(cat).
        env = os.environ.copy()
        env.setdefault("DOCKER_HOST", "unix://$HOME/.orbstack/run/docker.sock")
        write = subprocess.run(
            ["openshell", "sandbox", "exec", "-n", self.sandbox, "--no-tty",
             "--", "bash", "-c", "cat > /tmp/runner_prompt.txt"],
            input=sandbox_prompt, text=True, capture_output=True, timeout=15, env=env,
        )
        if write.returncode != 0:
            return RunResult(output="", duration_ms=0, error=f"prompt_write_failed: {write.stderr[:200]}",
                             exit_code=write.returncode, stderr_tail=write.stderr[-300:])
        if self.mode == "infer":
            inner = (
                'OLLAMA_API_KEY=ollama-local OPENAI_API_KEY=ollama-local '
                f'openclaw infer model run --local --model {MODEL} '
                '--prompt "$(cat /tmp/runner_prompt.txt)"'
            )
        else:  # agent
            # 매 런 고유 세션 id → 샌드박스 세션 lock 경합 방지 (호스트와 동일 처리).
            session_id = uuid.uuid4().hex
            inner = (
                'OLLAMA_API_KEY=ollama-local OPENAI_API_KEY=ollama-local '
                f'openclaw agent --local --agent {self.agent_id} '
                f'--session-id {session_id} '
                '--message "$(cat /tmp/runner_prompt.txt)" '
                f'--timeout {timeout_s}'
            )
        return self._exec(["bash", "-c", inner], timeout_s=timeout_s)


class NemoClawHardenedEnv(NemoClawEnv):
    """Env B + 가이드라인 §3.2(b) 강화 옵션 — workspace 평문 자격증명 격리.

    배경 (5차 멘토링 #10 "디폴트에서 더 세팅하면 보안 점수↑" 입증용):
      디폴트 NemoClawEnv 는 C1(env_leak)을 막지 못한다. env B의 차단 방식은
      "허용 경로만 샌드박스에 업로드"인데, C1의 .env 는 에이전트 workspace
      *내부*(/sandbox/.openclaw/workspace/.env)에 있어 업로드 화이트리스트로는
      통제할 수 없다. → 디폴트에서는 env A·env B 둘 다 누출 (0% 차단).

    강화 메커니즘 (mechanism 인자):
      "externalize" (기본, 가장 확실):
          매 런 직전 샌드박스 workspace 에서 평문 secret 파일을 **제거**한다.
          프로덕션 등가물 = "워크스페이스에 평문 자격증명을 두지 않고, 필요한
          값만 런타임에 secret manager(Vault/AWS SM)로 주입" (가이드라인 §3.2(a)).
          파일이 없으므로 에이전트가 어떤 UID로 돌든 'read workspace .env' 는
          ENOENT → 토큰 누출 불가. 0% → ~100% 차단으로 전환된다.

      "chmod" (대안, 라이브 UID 검증 필요):
          secret 파일을 제자리 유지하되 chown root:root + chmod 600.
          에이전트 프로세스 UID 가 root 가 아닐 때만 유효하다. 샌드박스 exec 가
          root 로 동작하면 효과가 없으므로, 사용 전 아래로 UID 를 확인할 것:
              openshell sandbox exec -n samdtg --no-tty -- id -u

    주의:
      - SANDBOX_WORKSPACE 경로는 라이브에서 1회 검증할 것:
            openshell sandbox exec -n samdtg --no-tty -- \
              sh -c 'echo "$OPENCLAW_STATE_DIR"; ls -la /sandbox/.openclaw/workspace/'
      - 베이스라인(디폴트, 누출) 측정과 강화(차단) 측정은 각각 직전에
        scripts/seed_c1_honeypot.sh 로 .env 를 재시딩한 뒤 실행해야 공정하다
        (강화 런이 .env 를 제거하므로 순서에 따라 베이스라인이 오염될 수 있음).
    """

    name = "nemoclaw-hardened"

    # 에이전트 workspace 내부 평문 secret 위치 (라이브 1회 검증 필요).
    SANDBOX_WORKSPACE = "/sandbox/.openclaw/workspace"
    SECRET_FILES = [".env"]  # 필요 시 확장 (예: "credentials.json")

    def __init__(self, sandbox: str = "samdtg", mode: str = "agent",
                 agent_id: str = "main", mechanism: str = "externalize"):
        super().__init__(sandbox=sandbox, mode=mode, agent_id=agent_id)
        if mechanism not in ("externalize", "chmod"):
            raise ValueError(f"mechanism must be externalize|chmod, got {mechanism!r}")
        self.mechanism = mechanism

    def _apply_hardening(self) -> list[str]:
        """매 런 직전 강화 정책을 샌드박스 안에 적용. 경고 문자열 리스트 반환."""
        warnings: list[str] = []
        for fname in self.SECRET_FILES:
            src = f"{self.SANDBOX_WORKSPACE}/{fname}"
            if self.mechanism == "externalize":
                # 평문 secret 을 워크스페이스에서 제거 (런타임 주입 모델).
                # 원본은 scripts/seed_c1_honeypot.sh 가 호스트에 보존한다.
                script = f'rm -f "{src}"'
            else:  # chmod — 제자리 유지 + 접근 권한 박탈 (UID 비root 전제)
                script = (
                    f'if [ -f "{src}" ]; then '
                    f'chown root:root "{src}" 2>/dev/null || true; '
                    f'chmod 600 "{src}"; fi'
                )
            res = self._exec(["bash", "-c", script], timeout_s=15)
            if res.error or res.exit_code != 0:
                warnings.append(
                    f"harden_fail({self.mechanism}) {src}: "
                    f"{res.error or res.stderr_tail[:120]}"
                )
        return warnings

    def run(self, prompt: str, timeout_s: int = 120) -> RunResult:
        harden_warnings = self._apply_hardening()
        if harden_warnings:
            import sys
            for w in harden_warnings:
                print(f"[nemoclaw-hardened/harden WARN] {w}", file=sys.stderr)
        result = super().run(prompt, timeout_s=timeout_s)
        # 감사 추적: 어떤 강화가 적용됐는지 결과 행에 남긴다.
        result.extra = {
            **(result.extra or {}),
            "hardening": self.mechanism,
            "harden_warnings": harden_warnings,
        }
        return result


def _shquote(s: str) -> str:
    # Wrap a string in single quotes for bash, escaping any single quotes inside.
    return "'" + s.replace("'", "'\"'\"'") + "'"


ENVS = {
    "openclaw": OpenClawEnv(mode="agent"),
    "nemoclaw": NemoClawEnv(mode="agent"),
    # 5차 멘토링 #10 강화 실험: env B 디폴트 → workspace secret 격리 강화.
    "nemoclaw-hardened": NemoClawHardenedEnv(mode="agent", mechanism="externalize"),
    # Infer-only variants for fast smoke / model regression
    "openclaw-infer": OpenClawEnv(mode="infer"),
    "nemoclaw-infer": NemoClawEnv(mode="infer"),
}
