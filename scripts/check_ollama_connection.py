#!/usr/bin/env python3
"""
check_ollama_connection.py — Ollama API 연결 및 토큰 응답 검사기

사용법:
    python3 check_ollama_connection.py
    python3 check_ollama_connection.py --host 127.0.0.1 --port 11434
    python3 check_ollama_connection.py --sandbox --timeout 15

결과:
    - stdout: JSON (check_host, check_token, check_sandbox)
    - logs/environment_check.md: 표 형태로 append
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "environment_check.md")
MODEL = "ollama/gemma4:26b"
OLLAMA_MODEL_ID = "gemma4:26b"
MIN_TOKENS = 1  # generate 응답에서 기대하는 최소 토큰 수


def _http_get(url: str, timeout: int) -> tuple[int, str]:
    """GET 요청. (status_code, body) 반환. 실패 시 (0, error_str)."""
    try:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)


def _http_post(url: str, body: dict, timeout: int) -> tuple[int, str]:
    """POST 요청. (status_code, body) 반환."""
    data = json.dumps(body).encode()
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        try:
            body_str = e.read().decode()
        except Exception:
            body_str = str(e)
        return e.code, body_str
    except Exception as e:
        return 0, str(e)


def check_host(host: str, port: int, timeout: int) -> dict:
    """호스트 Ollama API 점검 (3단계)."""
    result = {
        "target": f"http://{host}:{port}",
        "port_open": False,
        "tags_status": 0,
        "model_present": False,
        "models": [],
        "generate_status": 0,
        "generate_tokens": 0,
        "generate_response": "",
        "error": None,
        "passed": False,
    }

    # 1. 포트 리슨 확인
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        result["port_open"] = True
    except OSError as e:
        result["error"] = f"port_connect: {e}"
        return result
    finally:
        s.close()

    # 2. /api/tags — 모델 목록
    tags_url = f"http://{host}:{port}/api/tags"
    status, body = _http_get(tags_url, timeout)
    result["tags_status"] = status
    if status == 200:
        try:
            data = json.loads(body)
            names = [m.get("name", "") for m in data.get("models", [])]
            result["models"] = names
            result["model_present"] = OLLAMA_MODEL_ID in names
        except Exception as e:
            result["error"] = f"tags_parse: {e}"
    else:
        result["error"] = f"tags_http_{status}: {body[:200]}"
        return result

    # 3. /api/generate — 짧은 프롬프트로 토큰 응답 확인
    gen_url = f"http://{host}:{port}/api/generate"
    payload = {
        "model": OLLAMA_MODEL_ID,
        "prompt": "1+1= (숫자만 답해)",
        "stream": False,
        "options": {"num_predict": 8},
    }
    t0 = time.monotonic()
    gen_status, gen_body = _http_post(gen_url, payload, timeout)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    result["generate_status"] = gen_status
    result["generate_elapsed_ms"] = elapsed_ms
    if gen_status == 200:
        try:
            gdata = json.loads(gen_body)
            resp_text = gdata.get("response", "")
            result["generate_response"] = resp_text[:120]
            # gemma4 계열은 response 필드가 빈 문자열이어도 eval_count로 토큰 생성 확인
            result["generate_tokens"] = len(resp_text.split()) or gdata.get("eval_count", 0)
            result["generate_eval_count"] = gdata.get("eval_count", 0)
            result["generate_done_reason"] = gdata.get("done_reason", "")
        except Exception as e:
            result["error"] = f"generate_parse: {e}"
    else:
        result["error"] = f"generate_http_{gen_status}: {gen_body[:200]}"

    result["passed"] = (
        result["port_open"]
        and result["tags_status"] == 200
        and result["model_present"]
        and result["generate_status"] == 200
        and result["generate_tokens"] >= MIN_TOKENS
    )
    return result


def check_sandbox(sandbox: str, timeout: int) -> dict:
    """샌드박스(samdtg) 안에서 포워더를 통해 Ollama API 응답 확인."""
    result = {
        "sandbox": sandbox,
        "forwarder_running": False,
        "tags_status": 0,
        "model_present": False,
        "generate_status": 0,
        "generate_tokens": 0,
        "error": None,
        "passed": False,
    }

    docker_host = os.environ.get(
        "DOCKER_HOST", "unix://$HOME/.orbstack/run/docker.sock"
    )
    env = os.environ.copy()
    env["DOCKER_HOST"] = docker_host

    def _sb_exec(cmd: list[str], input_text: str | None = None) -> subprocess.CompletedProcess:
        full = [
            "openshell", "sandbox", "exec",
            "-n", sandbox, "--no-tty",
            "--",
        ] + cmd
        return subprocess.run(
            full,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            env=env,
            input=input_text,
        )

    # 1. 포워더 프로세스 확인
    try:
        proc = _sb_exec(["pgrep", "-c", "-f", "ollama_forwarder"])
        count = proc.stdout.strip()
        result["forwarder_running"] = count.isdigit() and int(count) > 0
    except Exception as e:
        result["error"] = f"forwarder_check: {e}"
        return result

    # 2. 샌드박스 내 /api/tags 확인
    try:
        proc = _sb_exec([
            "curl", "-s", "--max-time", str(timeout),
            "-w", "\\nHTTP_CODE:%{http_code}",
            "http://127.0.0.1:11434/api/tags",
        ])
        out = proc.stdout
        if "HTTP_CODE:" in out:
            parts = out.rsplit("HTTP_CODE:", 1)
            body = parts[0].strip()
            code_str = parts[1].strip()
            result["tags_status"] = int(code_str) if code_str.isdigit() else 0
            if result["tags_status"] == 200:
                try:
                    data = json.loads(body)
                    names = [m.get("name", "") for m in data.get("models", [])]
                    result["model_present"] = OLLAMA_MODEL_ID in names
                except Exception:
                    pass
        else:
            result["error"] = f"curl_unexpected: {out[:200]}"
    except Exception as e:
        result["error"] = f"tags_exec: {e}"
        return result

    # 3. 샌드박스 내 /api/generate 확인
    prompt_b64 = "1+1= (숫자만 답해)"
    gen_payload = json.dumps({
        "model": OLLAMA_MODEL_ID,
        "prompt": prompt_b64,
        "stream": False,
        "options": {"num_predict": 8},
    })
    try:
        proc = _sb_exec([
            "bash", "-c",
            f"curl -s --max-time {timeout} -X POST -H 'Content-Type: application/json' "
            f"-d '{gen_payload}' "
            "http://127.0.0.1:11434/api/generate",
        ])
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                gdata = json.loads(proc.stdout)
                resp_text = gdata.get("response", "")
                result["generate_response"] = resp_text[:120]
                # gemma4 계열은 response 필드가 빈 문자열이어도 eval_count로 토큰 생성 확인
                result["generate_tokens"] = len(resp_text.split()) or gdata.get("eval_count", 0)
                result["generate_eval_count"] = gdata.get("eval_count", 0)
                result["generate_done_reason"] = gdata.get("done_reason", "")
                result["generate_status"] = 200
            except Exception as e:
                result["error"] = f"generate_parse: {e}"
        else:
            result["error"] = f"generate_exec: exit={proc.returncode} stderr={proc.stderr[:200]}"
    except Exception as e:
        result["error"] = f"generate_exec: {e}"

    result["passed"] = (
        result["forwarder_running"]
        and result["tags_status"] == 200
        and result["model_present"]
        and result["generate_status"] == 200
        and result["generate_tokens"] >= MIN_TOKENS
    )
    return result


def append_to_log(results: dict, args: argparse.Namespace) -> None:
    """결과를 logs/environment_check.md 에 누적 append."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    host_r = results.get("check_host", {})
    sb_r = results.get("check_sandbox", {})

    lines = [
        f"\n## {ts} — Ollama 연결 점검\n",
        f"**호스트**: `{args.host}:{args.port}`  ",
        f"**sandbox**: `{args.sandbox if args.sandbox else '점검 안 함'}`  ",
        f"**timeout**: {args.timeout}s\n",
        "| 점검 항목 | 결과 | 비고 |",
        "|---|---|---|",
    ]

    # host 결과
    lines.append(
        f"| [host] 포트 11434 리슨 | {'PASS' if host_r.get('port_open') else 'FAIL'} | |"
    )
    lines.append(
        f"| [host] /api/tags HTTP | {'PASS' if host_r.get('tags_status') == 200 else 'FAIL'} "
        f"| status={host_r.get('tags_status')} |"
    )
    lines.append(
        f"| [host] gemma4:26b 모델 | {'PASS' if host_r.get('model_present') else 'FAIL'} "
        f"| models={host_r.get('models', [])} |"
    )
    lines.append(
        f"| [host] /api/generate 응답 | {'PASS' if host_r.get('generate_status') == 200 else 'FAIL'} "
        f"| tokens={host_r.get('generate_tokens', 0)}, "
        f"elapsed={host_r.get('generate_elapsed_ms', '-')}ms |"
    )
    if host_r.get("error"):
        lines.append(f"| [host] 오류 | - | `{host_r['error'][:120]}` |")

    # sandbox 결과
    if sb_r:
        lines.append(
            f"| [sandbox] 포워더 프로세스 | {'PASS' if sb_r.get('forwarder_running') else 'FAIL'} | |"
        )
        lines.append(
            f"| [sandbox] /api/tags HTTP | {'PASS' if sb_r.get('tags_status') == 200 else 'FAIL'} "
            f"| status={sb_r.get('tags_status')} |"
        )
        lines.append(
            f"| [sandbox] gemma4:26b 모델 | {'PASS' if sb_r.get('model_present') else 'FAIL'} | |"
        )
        lines.append(
            f"| [sandbox] /api/generate 응답 | {'PASS' if sb_r.get('generate_status') == 200 else 'FAIL'} "
            f"| tokens={sb_r.get('generate_tokens', 0)} |"
        )
        if sb_r.get("error"):
            lines.append(f"| [sandbox] 오류 | - | `{sb_r['error'][:120]}` |")

    # 최종 판정
    host_pass = host_r.get("passed", False)
    sb_pass = sb_r.get("passed", True) if sb_r else True  # sandbox 미점검 시 무시
    overall = "PASS" if (host_pass and sb_pass) else "FAIL"
    lines.append(f"\n**최종 판정**: **{overall}**\n")
    if not host_pass and host_r.get("error"):
        lines.append(f"- host 실패 원인: `{host_r['error']}`")
    if sb_r and not sb_r.get("passed") and sb_r.get("error"):
        lines.append(f"- sandbox 실패 원인: `{sb_r['error']}`")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama 연결 및 토큰 응답 검사기")
    parser.add_argument("--host", default="127.0.0.1", help="Ollama API 호스트 (기본: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=11434, help="Ollama API 포트 (기본: 11434)")
    parser.add_argument("--sandbox", default="", help="OpenShell 샌드박스 이름 (비워두면 sandbox 점검 건너뜀)")
    parser.add_argument("--timeout", type=int, default=30, help="각 요청 타임아웃 초 (기본: 30)")
    args = parser.parse_args()

    results: dict = {}

    print(f"[check] host Ollama API: http://{args.host}:{args.port} ...", flush=True)
    host_result = check_host(args.host, args.port, args.timeout)
    results["check_host"] = host_result

    if args.sandbox:
        print(f"[check] sandbox '{args.sandbox}' forwarder + API ...", flush=True)
        sb_result = check_sandbox(args.sandbox, args.timeout)
        results["check_sandbox"] = sb_result

    # stdout: JSON
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # log append
    try:
        append_to_log(results, args)
        print(f"\n[check] 결과를 {LOG_PATH} 에 기록했습니다.", file=sys.stderr)
    except Exception as e:
        print(f"[check] 로그 기록 실패: {e}", file=sys.stderr)

    # exit code
    host_pass = results.get("check_host", {}).get("passed", False)
    sb_r = results.get("check_sandbox", {})
    sb_pass = sb_r.get("passed", True) if sb_r else True
    sys.exit(0 if (host_pass and sb_pass) else 1)


if __name__ == "__main__":
    main()
