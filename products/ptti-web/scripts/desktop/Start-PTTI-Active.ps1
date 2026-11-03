param([switch]$NoBrowser, [switch]$CheckOnly, [string]$RegistryRoot=$PSScriptRoot)
$ErrorActionPreference='Stop'
$mutex=$null; $owned=$false
function Hash-File([string]$p){$s=[IO.File]::OpenRead($p);$h=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($h.ComputeHash($s)).Replace('-','').ToLowerInvariant()}finally{$s.Dispose();$h.Dispose()}}
function Log([string]$s){Add-Content -LiteralPath (Join-Path $RegistryRoot 'active-launcher.log') -Encoding UTF8 -Value ((Get-Date -Format o)+' '+$s)}
function Read-Release([string]$id){
 if($id -notmatch '^[a-z0-9-]{1,80}$'){throw 'Invalid release ID.'}
 $r=Get-Content -LiteralPath (Join-Path $RegistryRoot ('releases\'+$id+'.json')) -Raw|ConvertFrom-Json
 if($r.contract -ne 'ptti.local-release/0.1' -or $r.id -ne $id -or $r.status -ne 'ACCEPTED'){throw 'Release is not accepted.'}
 foreach($gate in @('startup','core_flow','privacy')){if($r.acceptance.$gate -ne $true){throw ('Missing acceptance: '+$gate)}}
 if(-not $r.evidence -or -not $r.files){throw 'Missing release evidence or file identities.'}
 if($r.url -notmatch '^http://127\.0\.0\.1:\d{4,5}/$'){throw 'Only local loopback releases are supported.'}
 foreach($f in @($r.files)+@($r.evidence)){if((Hash-File $f.path) -ne $f.sha256){throw ('Release file identity mismatch: '+[IO.Path]::GetFileName($f.path))}}
 if(-not ($r.files.path -contains $r.launcher)){throw 'Launcher not covered by release identity.'}
 return $r
}
try{
 $mutex=New-Object Threading.Mutex($false,'Local\PTTI-Active-Release-Launcher');try{$owned=$mutex.WaitOne(45000)}catch [Threading.AbandonedMutexException]{$owned=$true};if(-not $owned){throw 'Another launch is still in progress.'}
 $active=Get-Content -LiteralPath (Join-Path $RegistryRoot 'active-release.json') -Raw|ConvertFrom-Json
 if($active.contract -ne 'ptti.active-release/0.1'){throw 'Invalid active-release manifest. Restore its backup.'}
 $chosen=$null; $firstError=$null
 foreach($id in @($active.current)+@($active.fallbacks)|Select-Object -Unique){
  try{
   $r=Read-Release $id
   $args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$r.launcher,'-NoBrowser');if($CheckOnly){$args+='-CheckOnly'}
   $raw=& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" @args
   if($LASTEXITCODE -ne 0){throw 'Release launcher failed; see original launcher log.'}
   $health=Invoke-RestMethod -Uri ($r.url+'__ptti/health.json') -UseBasicParsing -TimeoutSec 2
   foreach($field in $r.health.PSObject.Properties){if($health.($field.Name) -ne $field.Value){throw ('Health identity mismatch: '+$field.Name)}}
   $chosen=$r;break
  }catch{$firstError=$_.Exception.Message;Log ('REJECT '+$id+' '+$firstError)}
 }
 if(-not $chosen){throw ('No accepted release could start. '+$firstError)}
 # A fallback is used for this launch only. Never rewrite activation while software may be open.
 $result=@{release=$chosen.id;url=$chosen.url;observed_san=$health.san_head;playback=$health.playback_head;fallback=($chosen.id -ne $active.current)}
 $result|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $RegistryRoot 'last-launch.json') -Encoding UTF8
 Log ('READY '+$chosen.id+' '+$chosen.url+' fallback='+$result.fallback)
 if($NoBrowser -or $CheckOnly){$result|ConvertTo-Json -Compress;exit 0}
 $ram=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
 if($ram -lt 2.5){throw ('Service ready; browser BLOCKED by 2.5 GiB guard. Available '+[math]::Round($ram,2)+' GiB.')}
 Start-Process $chosen.url
 Log ('BROWSER_OPEN_REQUEST '+$chosen.url)
}catch{
 Log ('ERROR '+$_.Exception.Message)
 if($NoBrowser -or $CheckOnly){Write-Error $_;exit 1}
 Add-Type -AssemblyName PresentationFramework
 [System.Windows.MessageBox]::Show(('PTTI could not open: '+$_.Exception.Message+[Environment]::NewLine+'See active-launcher.log. Original stable launcher is retained.'),'PTTI Cinema')|Out-Null
 exit 1
}finally{if($owned){$mutex.ReleaseMutex()};if($mutex){$mutex.Dispose()}}
