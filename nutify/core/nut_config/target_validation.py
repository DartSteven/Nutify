"""NUT target readiness checks shared by setup validation flows."""

import subprocess
import time

from core.upsc_readiness import (
    evaluate_upsc_readiness,
    nominal_power_metadata,
    parse_upsc_output,
)


def check_upsc_targets(targets, upsc_bin, runner=subprocess.run):
    """Run one upsc check for each target and return response components."""
    failures = []
    summary_lines = []
    detail_blocks = []
    for candidate in targets:
        host = candidate['host']
        port = int(candidate.get('port') or 3493)
        host_with_port = host if port == 3493 else f'{host}:{port}'
        ups_spec = f"{candidate['ups_name']}@{host_with_port}"
        result = runner([upsc_bin, ups_spec], capture_output=True, text=True)
        if result.returncode != 0:
            error_text = (result.stderr or result.stdout or 'Unknown error').strip()
            failures.append(f'{ups_spec}: {error_text}')
            summary_lines.append(f'FAILED {ups_spec} - {error_text}')
            continue
        output_text = (result.stdout or '').strip()
        ready, readiness_error = evaluate_upsc_readiness(parse_upsc_output(output_text))
        if not ready:
            failures.append(f'{ups_spec}: {readiness_error}')
            summary_lines.append(f'WAITING {ups_spec} - {readiness_error}')
            continue
        summary_lines.append(f'OK {ups_spec}')
        detail_blocks.append(
            f"[{ups_spec}]\n{output_text if output_text else 'Connection successful'}"
        )
    return failures, summary_lines, detail_blocks


def wait_for_upsc_targets(
    targets,
    upsc_bin,
    timeout_seconds,
    interval_seconds=1.0,
    runner=subprocess.run,
    sleeper=time.sleep,
):
    """Poll until all local targets are ready or startup timeout expires."""
    deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
    while True:
        result = check_upsc_targets(targets, upsc_bin, runner=runner)
        if not result[0] or time.monotonic() >= deadline:
            return result
        sleeper(max(float(interval_seconds), 0.0))


def summarize_upsc_details(detail_blocks):
    """Return structured target and nominal metadata from successful details."""
    summaries = []
    for block in detail_blocks:
        lines = str(block or '').splitlines()
        target = lines[0].strip()[1:-1] if lines and lines[0].startswith('[') and lines[0].endswith(']') else ''
        raw_payload = parse_upsc_output('\n'.join(lines[1:]))
        summaries.append({
            'target': target,
            'raw': raw_payload,
            'nominal_power': nominal_power_metadata(raw_payload),
        })
    return summaries
