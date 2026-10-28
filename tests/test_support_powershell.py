# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Exercise provisioning control flow with simulated commands, never an installer."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which('pwsh') or shutil.which('powershell')


@unittest.skipUnless(SHELL, 'PowerShell interpreter unavailable')
class ProvisioningContractTests(unittest.TestCase):
    def test_pinned_provisioning_success_and_refusals(self):
        # All filesystem probes, hashes, download and process commands are replaced.
        # Only the GitHub environment output is written, inside this temporary folder.
        script = r"""
param([string]$Target, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
$env:TEMP = Split-Path $OutputPath
$cases = @(
    'installed', 'extract', 'installer_hash', 'executable_hash',
    'database_hash', 'extract_failure'
)
foreach ($case in $cases) {
    $global:case = $case
    $global:downloads = 0
    $global:starts = 0
    function Test-Path {
        param($LiteralPath)
        return ($global:case -in @('installed', 'executable_hash', 'database_hash'))
    }
    function Invoke-WebRequest { param($Uri, $OutFile) $global:downloads++ }
    function Start-Process {
        param($FilePath, $ArgumentList, [switch]$Wait, [switch]$PassThru, $WindowStyle)
        if ($FilePath -ne 'msiexec.exe' -or $WindowStyle -ne 'Hidden' -or
            -not $Wait -or -not $PassThru) { throw 'process contract' }
        if ($ArgumentList[0] -ne '/a' -or $ArgumentList[2] -ne '/qn') {
            throw 'extraction contract'
        }
        $global:starts++
        return @{ExitCode = $(if ($global:case -eq 'extract_failure') { 1 } else { 0 })}
    }
    function Get-FileHash {
        param($LiteralPath, $Algorithm)
        if ($Algorithm -ne 'SHA256') { throw 'hash algorithm' }
        $hash = if ($LiteralPath -like '*.msi') {
            if ($global:case -eq 'installer_hash') {
                'bad' } else {
                '6E5F6697FA727F919EB4E7C1C2BC20E8C2717378AAF77731EFD831EF66578243'
            }
        } elseif ($LiteralPath -like '*.exe') {
            if ($global:case -eq 'executable_hash') {
                'bad' } else {
                'D1CC2AD3AE66AF8A95C3FBB605AFFC4D22149C8D5AAB4239919792C524635006'
            }
        } else {
            if ($global:case -eq 'database_hash') {
                'bad' } else {
                'AB0A8F7C7375E1BD997990F4BC3A9AF497516F10E57F4AAA3CEFB55DCCAC5AE7'
            }
        }
        return @{Hash = $hash}
    }
    $env:FLAHAX_PHREEQC_ROOT = ''
    $env:FLAHAX_REQUIRE_PHREEQC = ''
    $env:GITHUB_ENV = if ($case -eq 'extract') { $OutputPath } else { '' }
    $failure = ''
    try {
        & $Target -Destination (Split-Path $OutputPath) | Out-Null } catch {
        $failure = $_.Exception.Message
    }
    if ($case -in @('installed', 'extract')) {
        if ($failure -or $env:FLAHAX_REQUIRE_PHREEQC -ne '1' -or
            -not $env:FLAHAX_PHREEQC_ROOT.EndsWith('phreeqc-3.8.6-17100-x64')) {
                throw "success contract: $case $failure"
            }
    } else {
        $expected = switch ($case) {
            'installer_hash' { 'Pinned PHREEQC installer hash mismatch' }
            'executable_hash' { 'PHREEQC executable hash mismatch' }
            'database_hash' { 'MINTEQ database hash mismatch' }
            'extract_failure' { 'PHREEQC extraction failed: 1' }
        }
        if (-not $failure.StartsWith($expected) -or $env:FLAHAX_REQUIRE_PHREEQC) {
            throw "refusal contract: $case $failure"
        }
    }
    $expectedDownloads = if ($case -in @('extract', 'installer_hash', 'extract_failure')) {
        1 } else {
        0
    }
    $expectedStarts = if ($case -in @('extract', 'extract_failure')) { 1 } else { 0 }
    if ($global:downloads -ne $expectedDownloads -or $global:starts -ne $expectedStarts) {
        throw "side effect contract: $case"
    }
    Write-Output "PASS $case"
}
"""
        with tempfile.TemporaryDirectory() as folder:
            harness = Path(folder) / 'contract.ps1'
            output = Path(folder) / 'github-env'
            harness.write_text(script, encoding='utf-8')
            result = subprocess.run(
                [
                    SHELL,
                    '-NoProfile',
                    '-NonInteractive',
                    '-ExecutionPolicy',
                    'Bypass',
                    '-File',
                    str(harness),
                    str(ROOT / 'tools/provision_phreeqc.ps1'),
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count('PASS '), 6)
            saved = output.read_text(encoding='utf-8-sig')
            self.assertIn('FLAHAX_REQUIRE_PHREEQC=1', saved)
            self.assertIn('phreeqc-3.8.6-17100-x64', saved)
