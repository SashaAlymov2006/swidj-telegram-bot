param(
    [string]$Image = 'swidj:local-verified',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$swiProject = Split-Path -Parent $PSScriptRoot
$swiDocker = Get-Command docker.exe -ErrorAction SilentlyContinue
if (-not $swiDocker) {
    $swiCandidates = @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    )
    $swiExecutable = $swiCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $swiExecutable) { throw 'Docker CLI is not installed.' }
} else { $swiExecutable = $swiDocker.Source }
$env:PATH = (Split-Path -Parent $swiExecutable) + ';' + $env:PATH
function Invoke-SwiDocker {
    param([string[]]$DockerArguments)
    $swiPreviousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell treats native stderr progress as ErrorRecords.
        # Preserve the text and judge Docker by its actual process exit code.
        $ErrorActionPreference = 'Continue'
        & $swiExecutable @DockerArguments 2>&1 | ForEach-Object { $_.ToString() }
        if ($LASTEXITCODE -ne 0) { throw "Docker command failed with exit code $LASTEXITCODE." }
    } finally { $ErrorActionPreference = $swiPreviousPreference }
}
$swiEngine = Invoke-SwiDocker -DockerArguments @('info','--format','{{.OSType}}')
if ($swiEngine -ne 'linux') { throw 'Start Docker Desktop with the Linux/WSL 2 backend first.' }
if (-not $SkipBuild) {
    Invoke-SwiDocker -DockerArguments @('build','--progress=plain','--tag',$Image,$swiProject)
}
Invoke-SwiDocker -DockerArguments @('run','--rm','--network','none','--mount',"type=bind,source=$swiProject,target=/workspace/SwiDJ,readonly",'--workdir','/workspace/SwiDJ',$Image,'python','-m','unittest','discover','-s','tests','-v')
Invoke-SwiDocker -DockerArguments @('run','--rm','--network','none',$Image,'python','-m','pip','check')
Invoke-SwiDocker -DockerArguments @('run','--rm','--network','none','--mount','type=volume,target=/home/bot/.cache',$Image,'python','-c',"import os,tempfile; assert os.getuid() != 0; cache=tempfile.TemporaryFile(dir='/home/bot/.cache'); cache.write(b'permission-check'); cache.close(); print('Fresh model-cache volume is writable by the non-root bot user')")
Invoke-SwiDocker -DockerArguments @('run','--rm','--network','none','--user','0','--env','RAILWAY_PROJECT_ID=offline-fixture','--env','RAILWAY_VOLUME_MOUNT_PATH=/app/data','--mount','type=volume,target=/app/data','--entrypoint','sh',$Image,'-c','chown 0:0 /app/data && chmod 700 /app/data && touch /app/data/existing-root-owned-file && exec python /app/railway_start.py --check-storage')
Write-Output 'Full offline container tests, dependency checks, Docker cache and Railway volume permissions passed. No Telegram polling started.'
