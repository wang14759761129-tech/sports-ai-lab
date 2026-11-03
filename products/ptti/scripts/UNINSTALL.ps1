$ErrorActionPreference='Stop'
$pttiRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$pttiExpected=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\PTTI\versions\0.1.2'))
if($pttiRoot -ne $pttiExpected){throw 'Run uninstall from the installed version folder only.'}
$pttiConfirm=Read-Host 'Remove PTTI 0.1.2 application only? Match database will be retained. Type YES'
if($pttiConfirm -ne 'YES'){exit}
$pttiExe=Join-Path $pttiRoot 'PTTI\PTTI.exe'
$pttiShell=New-Object -ComObject WScript.Shell
$pttiStart=Join-Path ([Environment]::GetFolderPath('Programs')) 'PTTI'
foreach($pttiLink in @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'PTTI.lnk'),(Join-Path $pttiStart 'PTTI.lnk'))){
    if((Test-Path -LiteralPath $pttiLink) -and ($pttiShell.CreateShortcut($pttiLink).TargetPath -eq $pttiExe)){Remove-Item -LiteralPath $pttiLink}
}
$pttiUninstallLink=Join-Path $pttiStart 'Uninstall PTTI.lnk'
if(Test-Path -LiteralPath $pttiUninstallLink){$pttiExisting=$pttiShell.CreateShortcut($pttiUninstallLink);if($pttiExisting.Arguments.Contains((Join-Path $pttiRoot 'UNINSTALL.ps1'))){Remove-Item -LiteralPath $pttiUninstallLink}}
Remove-Item -LiteralPath $pttiRoot -Recurse
Write-Output 'Application removed. %LOCALAPPDATA%\PTTI data retained.'
