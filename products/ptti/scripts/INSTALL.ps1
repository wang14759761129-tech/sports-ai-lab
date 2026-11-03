param([switch]$NoDesktop)
$ErrorActionPreference='Stop'
$pttiSource=Join-Path $PSScriptRoot 'PTTI'
$pttiTarget=Join-Path $env:LOCALAPPDATA 'Programs\PTTI\versions\0.1.2'
$pttiExe=Join-Path $pttiTarget 'PTTI\PTTI.exe'
if(-not(Test-Path -LiteralPath (Join-Path $pttiSource 'PTTI.exe'))){throw 'Extract the whole PTTI ZIP before running INSTALL.cmd.'}
if(Test-Path -LiteralPath $pttiTarget){
    if(-not(Test-Path -LiteralPath $pttiExe)){throw 'An incomplete installation already exists. Preserve it before retrying.'}
    if((Get-FileHash -LiteralPath $pttiExe).Hash -ne (Get-FileHash -LiteralPath (Join-Path $pttiSource 'PTTI.exe')).Hash){throw 'A different 0.1.2 build exists. No files were overwritten.'}
}else{
    $null=New-Item -ItemType Directory -Path $pttiTarget
    Copy-Item -LiteralPath $pttiSource -Destination $pttiTarget -Recurse
    foreach($pttiName in @('sample','docs','START-HERE.txt','UNINSTALL.ps1')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $pttiName) -Destination $pttiTarget -Recurse}
}
$pttiShell=New-Object -ComObject WScript.Shell
$pttiStart=Join-Path ([Environment]::GetFolderPath('Programs')) 'PTTI'
$null=New-Item -ItemType Directory -Path $pttiStart -Force
$pttiLinks=@((Join-Path $pttiStart 'PTTI.lnk'))
if(-not $NoDesktop){$pttiLinks+=(Join-Path ([Environment]::GetFolderPath('Desktop')) 'PTTI.lnk')}
foreach($pttiLink in $pttiLinks){
    if(Test-Path -LiteralPath $pttiLink){Copy-Item -LiteralPath $pttiLink -Destination ($pttiLink+'.backup-'+(Get-Date -Format 'yyyyMMddHHmmssfff'))}
    $pttiShortcut=$pttiShell.CreateShortcut($pttiLink)
    $pttiShortcut.TargetPath=$pttiExe;$pttiShortcut.WorkingDirectory=Split-Path -Parent $pttiExe
    $pttiShortcut.IconLocation=$pttiExe+',0';$pttiShortcut.Description='PTTI - Personal Table Tennis Intelligence'
    $pttiShortcut.Save()
}
$pttiUninstall=$pttiShell.CreateShortcut((Join-Path $pttiStart 'Uninstall PTTI.lnk'))
$pttiUninstall.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$pttiUninstall.Arguments='-NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $pttiTarget 'UNINSTALL.ps1')+'"'
$pttiUninstall.WorkingDirectory=$pttiTarget;$pttiUninstall.Save()
Write-Output ('Installed: '+$pttiExe)
Write-Output 'Desktop / Start Menu shortcuts ready. User match data is preserved.'
