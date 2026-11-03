param(
 [ValidateSet('Native','Web')][string]$Choice,
 [switch]$CheckOnly, [switch]$NoBrowser,
 [switch]$UiSmokeTest, [string]$SmokeReceipt, [string]$CheckReceipt
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$nativeRoot=Join-Path (Split-Path -Parent $root) 'NativeRoot\PTTI-Cinema'
$native=Join-Path $nativeRoot 'launcher.ps1'
$web='<LOCAL_USER_ROOT>\PTTI\Web-Pro\Start-PTTI-Active.ps1'
$ps="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
function Log([string]$message) { Add-Content -LiteralPath (Join-Path $root 'launcher.log') -Encoding UTF8 -Value ((Get-Date -Format o)+' '+$message) }
function Hash-File([string]$path) {
 $stream=[IO.File]::OpenRead($path);$sha=[Security.Cryptography.SHA256]::Create()
 try {return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$stream.Dispose();$sha.Dispose()}
}
# BEGIN PTTI_NATIVE_R4_PROCESS_IDENTITY_V1
function Get-NativeR4ProcessState {
 [CmdletBinding()]
 param(
  [Parameter(Mandatory=$true)][string]$ExecutablePath,
  [Parameter(Mandatory=$true)][string]$ExpectedSha256,
  [Parameter(Mandatory=$true)][string]$VerifiedSha256,
  [object[]]$ProcessSnapshot,
  [scriptblock]$ProcessResolver
 )
 $target=[IO.Path]::GetFullPath($ExecutablePath)
 $targetName=[IO.Path]::GetFileName($target)
 $actualHash=$VerifiedSha256.ToLowerInvariant()
 if($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$' -or $actualHash -notmatch '^[0-9a-f]{64}$' -or -not [string]::Equals($actualHash,$ExpectedSha256,[StringComparison]::OrdinalIgnoreCase)) {
  return [pscustomobject]@{IdentityVerified=$false;IdentityFailure='TARGET_IMAGE_HASH_MISMATCH';ActualSha256=$actualHash;RunningPids=@();UnverifiedPids=@();CanLaunch=$false}
 }
 if($null -eq $ProcessSnapshot) {
  try { $ProcessSnapshot=@(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop) }
  catch { return [pscustomobject]@{IdentityVerified=$false;IdentityFailure='PROCESS_SNAPSHOT_UNAVAILABLE';ActualSha256=$actualHash;RunningPids=@();UnverifiedPids=@();CanLaunch=$false} }
 }
 if(-not $ProcessResolver) {
  $ProcessResolver={
   param([int]$ProcessId)
   $process=$null
   try {
    $process=[Diagnostics.Process]::GetProcessById($ProcessId)
    if($process.HasExited){return [pscustomobject]@{Status='Exited';ProcessId=$ProcessId}}
    $imagePath=$process.MainModule.FileName
    $startTicks=$process.StartTime.ToUniversalTime().Ticks
    if($process.HasExited){return [pscustomobject]@{Status='Exited';ProcessId=$ProcessId}}
    return [pscustomobject]@{Status='Resolved';ProcessId=$process.Id;Path=$imagePath;StartTimeUtcTicks=$startTicks;HasExited=$false}
   } catch [ArgumentException] {
    return [pscustomobject]@{Status='Exited';ProcessId=$ProcessId}
   } catch {
    return [pscustomobject]@{Status='Unreadable';ProcessId=$ProcessId}
   } finally { if($process){$process.Dispose()} }
  }
 }
 $running=New-Object 'System.Collections.Generic.List[int]'
 $unverified=New-Object 'System.Collections.Generic.List[int]'
 $seen=@{}
 foreach($entry in @($ProcessSnapshot)) {
  $id=0
  try { $id=[int]$entry.ProcessId } catch { continue }
  if($id -le 0 -or $seen.ContainsKey([string]$id)){continue}
  $seen[[string]$id]=$true
  $name=[string]$entry.Name
  $snapshotFull=$null
  $snapshotPath=[string]$entry.ExecutablePath
  $candidate=$false
  if($snapshotPath) {
   try { $snapshotFull=[IO.Path]::GetFullPath($snapshotPath) }
   catch { if([string]::Equals($name,$targetName,[StringComparison]::OrdinalIgnoreCase)){$candidate=$true}else{continue} }
  if($snapshotFull) {
   if([string]::Equals($snapshotFull,$target,[StringComparison]::OrdinalIgnoreCase)){$candidate=$true}
   elseif([string]::Equals([IO.Path]::GetFileName($snapshotFull),$targetName,[StringComparison]::OrdinalIgnoreCase)){$candidate=$true}
   else{continue}
   }
  } elseif([string]::Equals($name,$targetName,[StringComparison]::OrdinalIgnoreCase)) {
   # Exact R4 basename with unreadable snapshot path is ambiguous; fail closed after live-handle inspection.
   $candidate=$true
  } else {
   continue
  }
  if(-not $candidate){continue}
  $current=$null
  try { $current=& $ProcessResolver $id } catch { $current=$null }
  if(-not $current){$unverified.Add($id);continue}
  $status=[string]$current.Status
  if($status -eq 'Exited'){continue}
  if($status -ne 'Resolved'){$unverified.Add($id);continue}
  try {
   $currentId=[int]$current.ProcessId
   $currentPath=[string]$current.Path
   $startTicks=[long]$current.StartTimeUtcTicks
   $hasExited=[bool]$current.HasExited
  } catch { $unverified.Add($id);continue }
  if($hasExited){continue}
  if($currentId -ne $id -or -not $currentPath -or $startTicks -le 0){$unverified.Add($id);continue}
  try { $currentFull=[IO.Path]::GetFullPath($currentPath) }
  catch { $unverified.Add($id);continue }
  # The live process handle is authoritative. A reused PID resolving to another executable is not stale R4 state.
  if([string]::Equals($currentFull,$target,[StringComparison]::OrdinalIgnoreCase)){$running.Add($id);continue}
  if(-not [string]::Equals([IO.Path]::GetFileName($currentFull),$targetName,[StringComparison]::OrdinalIgnoreCase)){continue}
  try {$currentHash=(Hash-File $currentFull).ToLowerInvariant()}
  catch {$unverified.Add($id);continue}
  if([string]::Equals($currentHash,$ExpectedSha256,[StringComparison]::OrdinalIgnoreCase)){$running.Add($id)}
 }
 $known=@($running.ToArray())
 $unknown=@($unverified.ToArray())
 return [pscustomobject]@{IdentityVerified=$true;IdentityFailure=$null;ActualSha256=$actualHash;RunningPids=$known;UnverifiedPids=$unknown;CanLaunch=($known.Count -eq 0 -and $unknown.Count -eq 0)}
}
# END PTTI_NATIVE_R4_PROCESS_IDENTITY_V1
function Throw-EntryFailure([string]$kind,[string]$message) {
 $exception=New-Object System.InvalidOperationException($message)
 $exception.Data['PTTIFailureKind']=$kind
 throw $exception
}
function Open-NativeLauncher([string]$path) {
 $canonical=[IO.Path]::GetFullPath($path)
 $parent=Split-Path -Parent $canonical
$parentExists=Test-Path -LiteralPath $parent -PathType Container
$fileExists=Test-Path -LiteralPath $canonical -PathType Leaf
$knownLocalAppData=[Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
Log ('NATIVE_PATH_CONTEXT path='+$canonical+' parentExists='+$parentExists+' fileExists='+$fileExists+' knownLocalAppData='+$knownLocalAppData+' envLocalAppData='+$env:LOCALAPPDATA)
 if(-not (Test-Path -LiteralPath $parent -PathType Container)){Throw-EntryFailure 'NATIVE_PATH_MISSING' ('原生启动器目录不存在：'+$parent)}
 if(-not (Test-Path -LiteralPath $canonical -PathType Leaf)){Throw-EntryFailure 'NATIVE_PATH_MISSING' ('原生启动器文件不存在：'+$canonical)}
 $component=$canonical
 while($component) {
  try {$componentItem=Get-Item -Force -LiteralPath $component -ErrorAction Stop}catch{Throw-EntryFailure 'NATIVE_PATH_UNREADABLE' ('无法读取原生启动器路径组件：'+$component+'；'+$_.Exception.Message)}
  if(($componentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Throw-EntryFailure 'NATIVE_PATH_UNTRUSTED' ('原生启动器路径包含重解析组件，已拒绝：'+$component)}
  if($component -eq $canonical){$item=$componentItem}
  $parentPath=Split-Path -Parent $component
  if(-not $parentPath -or $parentPath -eq $component){break}
  $component=$parentPath
 }
 $stream=$null
 try {
  $stream=[IO.File]::Open($canonical,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  $sha=[Security.Cryptography.SHA256]::Create()
  try {$hash=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant();$stream.Position=0}finally{$sha.Dispose()}
 } catch {
  if($stream){$stream.Dispose()}
  if($_.Exception.Data -and $_.Exception.Data.Contains('PTTIFailureKind')){throw}
  Throw-EntryFailure 'NATIVE_PATH_UNREADABLE' ('原生启动器存在但当前用户无法安全读取：'+$canonical+'；'+$_.Exception.Message)
 }
 Log ('NATIVE_PATH_READY path='+$canonical+' bytes='+$item.Length+' sha256='+$hash+' parent64='+[Environment]::Is64BitProcess)
 return @{Path=$canonical;Stream=$stream;Hash=$hash}
}
# BEGIN PTTI_NATIVE_POINTER_LEASE_V1
function Open-NativePointerLease([string]$nativeRootPath) {
 $leases=New-Object 'System.Collections.Generic.List[object]'
 try {
  foreach($name in @('current-preview.json','previous-preview.json')) {
   $path=[IO.Path]::GetFullPath((Join-Path $nativeRootPath $name))
   if(-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    if($name -eq 'current-preview.json'){throw 'The current R4 pointer is unavailable.'}
    continue
   }
   $item=Get-Item -Force -LiteralPath $path -ErrorAction Stop
   if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw ('The R4 pointer is a reparse point: '+$path)}
   $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
   $leases.Add([pscustomobject]@{Path=$path;Stream=$stream})
  }
  return ,$leases
 } catch {
  foreach($lease in $leases){$lease.Stream.Dispose()}
  throw
 }
}
# END PTTI_NATIVE_POINTER_LEASE_V1
function Run-Child([string]$file,[string]$flags) {
 $fullFile=[IO.Path]::GetFullPath($file)
 if(-not (Test-Path -LiteralPath $fullFile -PathType Leaf)){Throw-EntryFailure 'CHILD_SCRIPT_PATH_MISSING' ('子进程脚本路径不存在：'+$fullFile)}
 $arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$fullFile+'" '+$flags
 $id=[guid]::NewGuid().ToString('N'); $out=Join-Path $root ($id+'.out'); $err=Join-Path $root ($id+'.err')
 try {
  Log ('CHILD_START powershell='+$ps+' parent64='+[Environment]::Is64BitProcess+' file='+$fullFile+' fileExists=True argv='+$arguments)
  $p=Start-Process -FilePath $ps -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $handle=$p.Handle
  Log ('CHILD_CREATED pid='+$p.Id+' powershell='+$ps+' file='+$fullFile)
  if(-not $p.WaitForExit(45000)){throw '入口检查超过45秒，未终止任何进程；请查看日志。'}
  $result=Get-Content -LiteralPath $out -Raw -ErrorAction SilentlyContinue
  if($p.ExitCode -ne 0){$detail=Get-Content -LiteralPath $err -Raw -ErrorAction SilentlyContinue;Log ('CHILD_FAILED exit='+$p.ExitCode+' file='+$fullFile+' fileExists='+(Test-Path -LiteralPath $fullFile -PathType Leaf)+' error='+$detail);throw ('入口拒绝启动：'+$detail)}
  Log ('CHILD_EXIT exit=0 file='+$fullFile)
  return $result
 } finally { Remove-Item -LiteralPath $out,$err -ErrorAction SilentlyContinue }
}
function Invoke-Choice([string]$selected) {
 $mutex=New-Object Threading.Mutex($false,'Local\PTTI-Unified-Dispatch'); $owned=$false
 $nativeLease=$null
 $nativePointerLease=$null
 try {
  try {$owned=$mutex.WaitOne(0)}catch [Threading.AbandonedMutexException]{$owned=$true}
  if(-not $owned){throw '已有启动请求正在处理，请稍候。'}
  if($selected -eq 'Native') {
   $nativeLease=Open-NativeLauncher $native
   $native=$nativeLease.Path
   $nativePointerLease=Open-NativePointerLease $nativeRoot
   $exe=(Run-Child $native '-VerifyOnly').Trim()
   if(-not (Test-Path -LiteralPath $exe -PathType Leaf) -or [IO.Path]::GetFileName($exe) -notlike 'PTTI*R4*.exe'){throw '原生入口返回了无法识别的 R4 路径。'}
   $expectedR4Sha256='FCA3BDF09A96E3D95A1F676EA63793909057C6E8A1D95D0A9274D3C3FC6738AB'
   $r4Sha256=(Hash-File $exe).ToLowerInvariant()
   if(-not [string]::Equals($r4Sha256,$expectedR4Sha256,[StringComparison]::OrdinalIgnoreCase)){Throw-EntryFailure 'NATIVE_EXE_IDENTITY_MISMATCH' '原生 R4 EXE 与候选核验身份不符；未启动。'}
   $ram=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
   $processState=Get-NativeR4ProcessState -ExecutablePath $exe -ExpectedSha256 $expectedR4Sha256 -VerifiedSha256 $r4Sha256
   $running=@(@($processState.RunningPids)+@($processState.UnverifiedPids))
   if($CheckOnly -or $NoBrowser) {return (@{choice='Native';status='VERIFIED_ONLY';launcher=$native;exe=$exe;sha256=$r4Sha256;freeGiB=$ram;running=$running;runningUnverified=@($processState.UnverifiedPids);identityVerified=$processState.IdentityVerified;identityFailure=$processState.IdentityFailure;processIdentity='exact-path-sha256-live-pid-starttime-v1';heavyLaunch='NOT_TESTED'}|ConvertTo-Json -Compress)}
   if(-not $processState.IdentityVerified){Throw-EntryFailure 'NATIVE_EXE_IDENTITY_MISMATCH' '原生 R4 EXE 身份校验未通过；未启动。'}
   if($processState.UnverifiedPids.Count -gt 0){Throw-EntryFailure 'NATIVE_PROCESS_IDENTITY_UNVERIFIED' '检测到可能的 R4 进程但无法验证其路径；为避免重复启动，本次停止。'}
   if($processState.RunningPids.Count -gt 0){throw 'Cinema 原生播放器已经在运行；本次未再开一个实例。'}
   if($ram -lt 2.5){Log ('NATIVE_RAM_GUARD blocked freeGiB='+[math]::Round($ram,3)+' thresholdGiB=2.5');Throw-EntryFailure 'NATIVE_RAM_GUARD' ('可用内存 '+[math]::Round($ram,2)+' GiB，低于 2.5 GiB；请稍后再打开原生播放器。')}
   $ram=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
   if($ram -lt 2.5){Log ('NATIVE_RAM_GUARD recheck_blocked freeGiB='+[math]::Round($ram,3)+' thresholdGiB=2.5');Throw-EntryFailure 'NATIVE_RAM_GUARD' ('启动前可用内存复核为 '+[math]::Round($ram,2)+' GiB，低于 2.5 GiB；请稍后再打开原生播放器。')}
   $processState=Get-NativeR4ProcessState -ExecutablePath $exe -ExpectedSha256 $expectedR4Sha256 -VerifiedSha256 $r4Sha256
   if(-not $processState.IdentityVerified){Throw-EntryFailure 'NATIVE_EXE_IDENTITY_MISMATCH' '启动前 R4 身份复核未通过；未启动。'}
   if($processState.UnverifiedPids.Count -gt 0){Throw-EntryFailure 'NATIVE_PROCESS_IDENTITY_UNVERIFIED' '启动前发现无法核验的可能 R4 进程；为避免重复启动，本次停止。'}
   if($processState.RunningPids.Count -gt 0){throw 'Cinema 原生播放器已经在运行；本次未再开一个实例。'}
   # Keep the original package verification, fallback, profile and database behavior.
   $null=Run-Child $native ''
  } else {
   $flags=''; if($NoBrowser){$flags+=' -NoBrowser'}; if($CheckOnly){$flags+=' -CheckOnly'}
   $result=Run-Child $web $flags
   if($CheckOnly -or $NoBrowser){return $result}
  }
  try { [IO.File]::WriteAllText((Join-Path $root 'last-choice.txt'),$selected) }catch{Log ('PREFERENCE_WRITE_FAILED '+$_.Exception.Message)}
  Log ('DISPATCH_REQUESTED '+$selected)
 } finally {if($nativePointerLease){foreach($lease in $nativePointerLease){$lease.Stream.Dispose()}};if($nativeLease){$nativeLease.Stream.Dispose()};if($owned){$mutex.ReleaseMutex()};$mutex.Dispose()}
}
try {
 if($Choice){$result=Invoke-Choice $Choice; Log ('CHECK_OR_DISPATCH '+$Choice);if($result){if($CheckReceipt -and ($CheckOnly -or $NoBrowser)){$result|Set-Content -LiteralPath $CheckReceipt -Encoding UTF8};Write-Output $result};exit 0}
 if($CheckOnly -or $NoBrowser){throw '检查模式必须指定 -Choice Native 或 Web。'}
 Add-Type -AssemblyName System.Windows.Forms
 Add-Type -AssemblyName System.Drawing
 [Windows.Forms.Application]::EnableVisualStyles()
 $form=New-Object Windows.Forms.Form
 $form.Text='PTTI Cinema'; $form.ClientSize=New-Object Drawing.Size(520,300)
 $form.StartPosition='CenterScreen'; $form.FormBorderStyle='FixedDialog'; $form.MaximizeBox=$false
 $form.Font=New-Object Drawing.Font('Microsoft YaHei UI',10)
 $form.BackColor=[Drawing.Color]::FromArgb(246,248,252)
 $icon='<LOCAL_USER_ROOT>\PTTI\Web-Pro\ptti-cinema.ico'; if(Test-Path $icon){$form.Icon=New-Object Drawing.Icon($icon)}
 $title=New-Object Windows.Forms.Label; $title.Text='今天用哪个 PTTI？';$title.Location=New-Object Drawing.Point(26,20);$title.Size=New-Object Drawing.Size(470,36);$title.Font=New-Object Drawing.Font('Microsoft YaHei UI',17,[Drawing.FontStyle]::Bold);$form.Controls.Add($title)
 $hint=New-Object Windows.Forms.Label;$hint.Text='一个图标，两个独立程序。请选择要打开的工作区。';$hint.Location=New-Object Drawing.Point(28,65);$hint.Size=New-Object Drawing.Size(470,30);$form.Controls.Add($hint)
 $buttons=@{}
 foreach($item in @(@('Native','Cinema 原生播放器 R4',106),@('Web','Web Pro 专业工作台',171))) {
  $b=New-Object Windows.Forms.Button;$b.Text=$item[1];$b.Tag=$item[0];$b.Location=New-Object Drawing.Point(28,$item[2]);$b.Size=New-Object Drawing.Size(464,53);$b.BackColor=[Drawing.Color]::White;$b.FlatStyle='Flat';$buttons[$item[0]]=$b;$form.Controls.Add($b)
  $b.Add_Click({
   $selected=[string]$this.Tag
   try {$form.UseWaitCursor=$true;foreach($button in $buttons.Values){$button.Enabled=$false};$status.Text='正在校验并打开，请稍候…';$status.Refresh();$null=Invoke-Choice $selected;$form.Close()}
   catch {$status.Text='未启动，请查看提示。';$kind='ENTRY_REJECTED';if($_.Exception.Data -and $_.Exception.Data.Contains('PTTIFailureKind')){$kind=[string]$_.Exception.Data['PTTIFailureKind']};$message=$_.Exception.Message;if($kind -eq 'NATIVE_PATH_MISSING' -or $kind -eq 'NATIVE_PATH_UNREADABLE'){$message+="`r`n`r`nWeb Pro 工作台仍可用；返回此选择器后可单独选择 Web Pro。"};[Windows.Forms.MessageBox]::Show($message,'PTTI Cinema')|Out-Null;Log ('REFUSED '+$selected+' kind='+$kind+' '+$_.Exception.Message)}
   finally {$form.UseWaitCursor=$false;foreach($button in $buttons.Values){$button.Enabled=$true}}
  })
 }
 $default='Native';try{$saved=[IO.File]::ReadAllText((Join-Path $root 'last-choice.txt')).Trim();if($buttons.ContainsKey($saved)){$default=$saved}}catch{}
 $form.AcceptButton=$buttons[$default];$form.Add_Shown({$buttons[$default].Focus();Log ('MENU_SHOWN default='+$default+' smoke='+$UiSmokeTest)})
 $status=New-Object Windows.Forms.Label;$status.Text='回车打开：'+$buttons[$default].Text+'  ·  记住上次成功选择';$status.Location=New-Object Drawing.Point(28,245);$status.Size=New-Object Drawing.Size(464,45);$form.Controls.Add($status)
 if($UiSmokeTest){
  if(-not $SmokeReceipt){throw 'SmokeReceipt required'}
  $script:smokeFailed=$false
  $timer=New-Object Windows.Forms.Timer;$timer.Interval=1000
  $timer.Add_Tick({
   $timer.Stop();$bitmap=$null;$stream=$null
   try {
    $bitmap=New-Object Drawing.Bitmap($form.Width,$form.Height)
    $form.DrawToBitmap($bitmap,(New-Object Drawing.Rectangle(0,0,$form.Width,$form.Height)))
    # Explicit PNG stream: no GDI+ filename/encoder inference or shared image handle.
    $stream=[IO.File]::Open(($SmokeReceipt+'.png'),[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    $bitmap.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
    @{status='PASS';buttons=@($buttons.Native.Text,$buttons.Web.Text);visible=$form.Visible;default=$default;kind='WINFORMS_SHOWN_AND_RENDERED_NO_APP_LAUNCH'}|ConvertTo-Json|Set-Content -LiteralPath $SmokeReceipt -Encoding UTF8
   } catch {
    $script:smokeFailed=$true
    Log ('SMOKE_FAILED '+$_.Exception.Message)
    @{status='FAIL';error=$_.Exception.Message}|ConvertTo-Json|Set-Content -LiteralPath $SmokeReceipt -Encoding UTF8
   } finally {
    if($stream){$stream.Dispose()};if($bitmap){$bitmap.Dispose()};$form.Close()
   }
  })
  $timer.Start()
 }
 [void]$form.ShowDialog();if($timer){$timer.Dispose()};$form.Dispose();if($script:smokeFailed){exit 1};exit 0
} catch {
 $kind='ENTRY_ERROR';if($_.Exception.Data -and $_.Exception.Data.Contains('PTTIFailureKind')){$kind=[string]$_.Exception.Data['PTTIFailureKind']};try{Log ('ERROR kind='+$kind+' '+$_.Exception.Message)}catch{}
 if($Choice -or $UiSmokeTest -or $CheckOnly -or $NoBrowser){Write-Error $_;exit 1}
 # The bootstrap falls back to the original guarded Web entry on a UI failure.
 exit 1
}
