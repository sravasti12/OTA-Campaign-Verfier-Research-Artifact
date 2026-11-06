param(
    [ValidateSet('Build', 'Run')][string]$Action = 'Run',
    [string]$Distribution = 'Ubuntu-24.04'
)
$ErrorActionPreference = 'Stop'
$scriptName = if ($Action -eq 'Build') { 'build-reference.sh' } else { 'run-reference.sh' }
$localPath = Join-Path $PSScriptRoot $scriptName
$linuxPath = (& wsl -d $Distribution -- wslpath -a $localPath.Replace('\', '/')).Trim()
if ($LASTEXITCODE -ne 0) { throw 'WSL path conversion failed' }
$savedPreference = $ErrorActionPreference
try {
    # Cargo writes normal build progress and warnings to stderr.
    $ErrorActionPreference = 'Continue'
    & wsl -d $Distribution -- bash $linuxPath
    $nativeExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedPreference
}
if ($nativeExit -ne 0) { throw "MCUboot $Action failed: exit $nativeExit" }
