#!/usr/bin/env python3
"""Parse JUnit XML and Cobertura Coverage XML to output GitHub Step Summary markdown."""

import os
import sys
import xml.etree.ElementTree as ET


def parse_junit(junit_path: str):
    if not os.path.exists(junit_path):
        return None
    try:
        tree = ET.parse(junit_path)
        root = tree.getroot()

        # Handle either <testsuites> as root or single <testsuite>
        if root.tag == "testsuites":
            suites = root.findall("testsuite")
            if not suites:
                suites = [root]
        else:
            suites = [root]

        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        total_time = 0.0

        for s in suites:
            total_tests += int(s.get("tests", 0))
            total_failures += int(s.get("failures", 0))
            total_errors += int(s.get("errors", 0))
            total_skipped += int(s.get("skipped", 0))
            total_time += float(s.get("time", 0.0))

        failed = total_failures + total_errors
        passed = max(0, total_tests - failed - total_skipped)

        return {
            "total": total_tests,
            "passed": passed,
            "failed": failed,
            "skipped": total_skipped,
            "time": total_time,
        }
    except Exception as exc:
        print(f"Warning: could not parse JUnit XML {junit_path}: {exc}", file=sys.stderr)
        return None


def parse_coverage(cov_path: str):
    if not os.path.exists(cov_path):
        return None
    try:
        tree = ET.parse(cov_path)
        root = tree.getroot()
        line_rate = root.get("line-rate")
        if line_rate is not None:
            pct = float(line_rate) * 100.0
            return f"{pct:.1f}%"
        lines_valid = root.get("lines-valid")
        lines_covered = root.get("lines-covered")
        if lines_valid and int(lines_valid) > 0:
            pct = (int(lines_covered) / int(lines_valid)) * 100.0
            return f"{pct:.1f}%"
        return "N/A"
    except Exception as exc:
        print(f"Warning: could not parse coverage XML {cov_path}: {exc}", file=sys.stderr)
        return None


def main():
    title = sys.argv[1] if len(sys.argv) > 1 else "Test Results"
    junit_path = sys.argv[2] if len(sys.argv) > 2 else ""
    cov_path = sys.argv[3] if len(sys.argv) > 3 else ""

    junit_data = parse_junit(junit_path) if junit_path else None
    cov_str = parse_coverage(cov_path) if cov_path else None

    print(f"\n### 📊 {title}\n")

    if junit_data:
        status_emoji = "✅ Pass" if junit_data["failed"] == 0 else "❌ Fail"
        print("| Status | Total Tests | Passed | Failed | Skipped | Time | Line Coverage |")
        print("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        print(
            f"| {status_emoji} | {junit_data['total']} | {junit_data['passed']} | "
            f"{junit_data['failed']} | {junit_data['skipped']} | {junit_data['time']:.2f}s | "
            f"{cov_str or 'N/A'} |"
        )
    elif cov_str:
        print(f"**Line Coverage:** {cov_str}")
    else:
        print("No test report or coverage artifacts found.")
    print()


if __name__ == "__main__":
    main()
