param([string]$Register,[string]$Activate,[string]$RegistryRoot=$PSScriptRoot)
$ErrorActionPreference='Stop'
function Hash-File([string]$p){$s=[IO.File]::OpenRead($p);$h=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($h.ComputeHash($s)).Replace('-','').ToLowerInvariant()}finally{$s.Dispose();$h.Dispose()}}
$mutex=New-Object Threading.Mutex($false,'Local\PTTI-Active-Release-Launcher');$owned=$false
try{
 $owned=$mutex.WaitOne(10000);if(-not $owned){throw 'Launcher busy; try later.'}
 if($Register){
  $r=Get-Content -LiteralPath $Register -Raw|ConvertFrom-Json
  if($r.contract -ne 'ptti.local-release/0.1' -or $r.status -ne 'ACCEPTED' -or $r.id -notmatch '^[a-z0-9-]{1,80}$'){throw 'Only accepted versioned releases can be registered.'}
  foreach($gate in @('startup','core_flow','privacy')){if($r.acceptance.$gate -ne $true){throw ('Acceptance incomplete: '+$gate)}}
  if(-not $r.evidence -or -not $r.files -or -not($r.files.path -contains $r.launcher)){throw 'Evidence and launcher identity required.'}
  foreach($f in @($r.files)+@($r.evidence)){if((Hash-File $f.path) -ne $f.sha256){throw 'Release or evidence hash mismatch.'}}
  $dest=Join-Path $RegistryRoot ('releases\'+$r.id+'.json');if(Test-Path -LiteralPath $dest){throw 'Release ID already registered; never overwrite.'}
  Copy-Item -LiteralPath $Register -Destination $dest
 }
 if($Activate){
  if($Activate -notmatch '^[a-z0-9-]{1,80}$'){throw 'Invalid release ID.'}
  $r=Get-Content -LiteralPath (Join-Path $RegistryRoot ('releases\'+$Activate+'.json')) -Raw|ConvertFrom-Json
  if($r.id -ne $Activate -or $r.status -ne 'ACCEPTED'){throw 'Not an accepted release.'}
  foreach($gate in @('startup','core_flow','privacy')){if($r.acceptance.$gate -ne $true){throw 'Acceptance incomplete.'}}
  foreach($f in @($r.files)+@($r.evidence)){if((Hash-File $f.path) -ne $f.sha256){throw 'Release or evidence hash mismatch.'}}
  $p=Join-Path $RegistryRoot 'active-release.json';$old=Get-Content -LiteralPath $p -Raw|ConvertFrom-Json
  Copy-Item -LiteralPath $p -Destination ($p+'.'+(Get-Date -Format 'yyyyMMddHHmmssfff')+'.backup')
  $next=@{contract='ptti.active-release/0.1';current=$Activate;fallbacks=@($old.current)+@($old.fallbacks)|Select-Object -Unique}
  $tmp=$p+'.pending';$next|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $tmp -Encoding UTF8
  [IO.File]::Replace($tmp,$p,($p+'.atomic-previous-'+(Get-Date -Format 'yyyyMMddHHmmssfff')))
  Write-Output 'Activation saved for the next launch. No running service changed.'
 }
}finally{if($owned){$mutex.ReleaseMutex()};$mutex.Dispose()}
