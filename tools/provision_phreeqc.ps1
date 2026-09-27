param([string]$Destination = (Join-Path $env:TEMP 'flahax-phreeqc/installed'))
$ErrorActionPreference = 'Stop'
$install = Join-Path $Destination 'phreeqc-3.8.6-17100-x64'
$exe = Join-Path $install 'bin/Release/phreeqc.exe'
$database = Join-Path $install 'database/minteq.v4.dat'
if (-not (Test-Path -LiteralPath $exe)) {
    $download = Join-Path $env:TEMP ('flahax-phreeqc-' + [guid]::NewGuid() + '.msi')
    Invoke-WebRequest 'https://water.usgs.gov/water-resources/software/PHREEQC/phreeqc-3.8.6-17100-x64.msi' -OutFile $download
    if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne '6E5F6697FA727F919EB4E7C1C2BC20E8C2717378AAF77731EFD831EF66578243') {
        throw 'Pinned PHREEQC installer hash mismatch; refusing execution'
    }
    # Administrative extraction only; no system-wide installation or PATH edits.
    $process = Start-Process msiexec.exe -ArgumentList @('/a', "`"$download`"", '/qn', "TARGETDIR=`"$Destination`"") -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "PHREEQC extraction failed: $($process.ExitCode)" }
}
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne 'D1CC2AD3AE66AF8A95C3FBB605AFFC4D22149C8D5AAB4239919792C524635006') { throw 'PHREEQC executable hash mismatch' }
if ((Get-FileHash -LiteralPath $database -Algorithm SHA256).Hash -ne 'AB0A8F7C7375E1BD997990F4BC3A9AF497516F10E57F4AAA3CEFB55DCCAC5AE7') { throw 'MINTEQ database hash mismatch' }
$env:FLAHAX_PHREEQC_ROOT = $install
$env:FLAHAX_REQUIRE_PHREEQC = '1'
if ($env:GITHUB_ENV) {
    "FLAHAX_PHREEQC_ROOT=$install" | Out-File -LiteralPath $env:GITHUB_ENV -Append -Encoding utf8
    'FLAHAX_REQUIRE_PHREEQC=1' | Out-File -LiteralPath $env:GITHUB_ENV -Append -Encoding utf8
}
Write-Output "Verified pinned PHREEQC outside checkout: $install"
