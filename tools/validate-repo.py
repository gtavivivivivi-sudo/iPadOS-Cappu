#!/usr/bin/env python3
"""Validate repository integrity, patch sequences, and script syntax.

  tools/validate-repo.py [--verbose]

Checks:
  1. Patch sequence in xnu/patches/:
     - Sequential numbering starting at 0001 with no duplicates or gaps.
     - Patch files are non-empty and have valid unified diff markers.
  2. Python script syntax:
     - All tools/*.py compile cleanly via py_compile.
  3. Shell script syntax:
     - All tools/*.sh, shim/*.sh, and xnu/patches/*.sh pass bash -n check.
"""
import argparse, glob, os, py_compile, re, subprocess, sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def green(text): return f"\033[92m{text}\033[0m"
def red(text): return f"\033[91m{text}\033[0m"
def bold(text): return f"\033[1m{text}\033[0m"


def validate_patches(verbose=False):
    patch_dir = os.path.join(REPO_ROOT, 'xnu/patches')
    patch_files = sorted(glob.glob(os.path.join(patch_dir, '*.patch')))
    if not patch_files:
        print(red("[-] Error: No patch files found in xnu/patches/"))
        return False

    errors = []
    seen_numbers = {}

    for path in patch_files:
        fname = os.path.basename(path)
        m = re.match(r'^(\d{4})-(.+)\.patch$', fname)
        if not m:
            errors.append(f"Invalid patch filename format: {fname}")
            continue

        num = int(m.group(1))
        if num in seen_numbers:
            errors.append(f"Duplicate patch number {num:04d}: {fname} and {seen_numbers[num]}")
        seen_numbers[num] = fname

        size = os.path.getsize(path)
        if size == 0:
            errors.append(f"Patch is empty: {fname}")
            continue

        with open(path, 'r', errors='ignore') as f:
            head = f.read(2048)
            if not ('--- ' in head or 'diff ' in head or 'Index:' in head):
                errors.append(f"Patch missing standard diff header: {fname}")

    # Check contiguous sequence
    if seen_numbers:
        sorted_nums = sorted(seen_numbers.keys())
        expected = 1
        for num in sorted_nums:
            if num != expected:
                errors.append(f"Gap in patch sequence: expected {expected:04d}, found {num:04d} ({seen_numbers[num]})")
                expected = num + 1
            else:
                expected += 1

    if errors:
        print(red(f"[-] Patch validation failed with {len(errors)} error(s):"))
        for err in errors:
            print(f"    - {err}")
        return False

    print(green(f"[✓] Validated {len(patch_files)} patches (0001-{len(patch_files):04d} contiguous, format OK)"))
    return True


def validate_python_scripts(verbose=False):
    tools_dir = os.path.join(REPO_ROOT, 'tools')
    py_files = sorted(glob.glob(os.path.join(tools_dir, '*.py')))
    errors = []

    for path in py_files:
        fname = os.path.basename(path)
        try:
            py_compile.compile(path, doraise=True)
            if verbose:
                print(f"    [OK] {fname}")
        except py_compile.PyCompileError as e:
            errors.append(f"{fname}: {e}")

    if errors:
        print(red(f"[-] Python syntax validation failed with {len(errors)} error(s):"))
        for err in errors:
            print(f"    - {err}")
        return False

    print(green(f"[✓] Validated {len(py_files)} Python tools (syntax OK)"))
    return True


def validate_shell_scripts(verbose=False):
    sh_files = sorted(
        glob.glob(os.path.join(REPO_ROOT, 'tools/*.sh')) +
        glob.glob(os.path.join(REPO_ROOT, 'shim/*.sh')) +
        glob.glob(os.path.join(REPO_ROOT, 'xnu/patches/*.sh'))
    )
    errors = []
    env_problems = []

    for path in sh_files:
        rel = os.path.relpath(path, REPO_ROOT).replace('\\', '/')
        try:
            # Relative path + cwd: Windows' WSL bash cannot open E:\... style paths.
            res = subprocess.run(['bash', '-n', rel], capture_output=True, text=True, cwd=REPO_ROOT)
        except FileNotFoundError:
            print(f"[!] bash not found, shell script syntax check skipped ({len(sh_files)} scripts)")
            return True
        if res.returncode != 0:
            msg = (res.stderr + res.stdout).strip()
            low = msg.lower()
            if 'no such file' in low or 'distribution' in low or 'wsl' in low:
                env_problems.append(rel)  # bash itself is unusable here, not a script error
            else:
                errors.append(f"{rel}: {msg}")
        elif verbose:
            print(f"    [OK] {rel}")

    if env_problems and not errors and len(env_problems) == len(sh_files):
        print(f"[!] bash here cannot open the scripts (WSL without a distro?), shell syntax check skipped")
        return True
    errors += [f"{r}: bash could not open the file" for r in env_problems]

    if errors:
        print(red(f"[-] Shell syntax validation failed with {len(errors)} error(s):"))
        for err in errors:
            print(f"    - {err}")
        return False

    print(green(f"[✓] Validated {len(sh_files)} Shell scripts (syntax OK)"))
    return True


def main():
    ap = argparse.ArgumentParser(description="Validate repository integrity, patches, and scripts.")
    ap.add_argument('-v', '--verbose', action='store_true', help='Show detailed per-file output')
    a = ap.parse_args()

    print(bold("=== Running iPadOS-Cappu Repository Validation ==="))
    ok_patches = validate_patches(a.verbose)
    ok_python = validate_python_scripts(a.verbose)
    ok_shell = validate_shell_scripts(a.verbose)

    if ok_patches and ok_python and ok_shell:
        print(bold(green("\nAll repository integrity checks PASSED successfully!")))
        return 0
    else:
        print(bold(red("\nRepository integrity check FAILED.")))
        return 1


if __name__ == '__main__':
    sys.exit(main())
