$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '..\Start-PTTI-Goal88-QA.cs'
$builder = Join-Path $PSScriptRoot '..\Build-GOAL88-QA.ps1'
$cs = Get-Content -LiteralPath $source -Raw
$ps = Get-Content -LiteralPath $builder -Raw
$checks = [ordered]@{
    target_manifest_hash_is_pinned = $cs.Contains('__TARGETS_SHA256__') -and $cs.Contains('ExpectedTargetsSha256')
    cinema_is_explicit_dev_preview = $cs.Contains('DEV_PREVIEW') -and $cs.Contains('127.0.0.1')
    cinema_process_path_and_command_checked = $cs.Contains('GetProcessIdentity') -and $cs.Contains('vite_script') -and $cs.Contains('SamePath')
    cinema_is_loopback_only = $cs.Contains('address != "127.0.0.1"') -and $cs.Contains('GetExtendedTcpTable')
    qa_desktop_uses_pinned_exe_and_release_hashes = $cs.Contains('CheckCinemaCandidate') -and $cs.Contains('RequireFileHash(target.exe') -and $cs.Contains('RequireFileHash(target.release_manifest')
    qa_desktop_checks_release_identity_before_launch = $cs.Contains('QA_ONLY_TEMP_VERSION_PORT_SCOPED') -and $cs.Contains('DISABLED_NO_R4_BRIDGE') -and $cs.Contains('OpenCinemaCandidate')
    qa_desktop_duplicate_detection_uses_exact_process_path = $cs.Contains('Process.GetProcessesByName(Path.GetFileNameWithoutExtension(expectedPath))') -and $cs.Contains('SamePath(runningPath, expectedPath)')
    qa_desktop_rejects_redirected_package_paths = $cs.Contains('Cinema QA package path is redirected') -and $cs.Contains('FileAttributes.ReparsePoint')
    pro_accepted_release_and_all_file_hashes_checked = $cs.Contains('ACCEPTED_LOCAL_RELEASE') -and $cs.Contains('RequireReleaseEntry')
    pro_launcher_respects_local_execution_policy = (-not $cs.Contains('-ExecutionPolicy Bypass')) -and $cs.Contains('Arguments = "-NoProfile -STA -WindowStyle Hidden -File "')
    stale_manifest_fails_closed = $cs.Contains('Pinned target manifest SHA-256 does not match this launcher')
    r4_launch_not_implemented = (-not $cs.Contains('Process.Start(new ProcessStartInfo(targets.r4')) -and $cs.Contains('this candidate will not launch it')
    no_broad_ptti_process_name_match = (-not $cs.Contains('PTTI*.exe')) -and (-not $cs.Contains('Name -like'))
    builder_refuses_candidate_overwrite = $ps.Contains('Refusing to overwrite existing candidate')
    builder_pins_san_and_host_commits = $ps.Contains('San HEAD changed') -and $ps.Contains('Host selector source commit changed')
    builder_keeps_dev_preview_default_and_supports_pinned_qa_desktop = $ps.Contains('[string]$CinemaMode = ''DEV_PREVIEW''') -and $ps.Contains("'QA_DESKTOP'") -and $ps.Contains('Cinema QA release identity does not match')
    no_production_shortcut_or_launcher_write = (-not $ps.Contains('Start-PTTI.ps1')) -and (-not $ps.Contains('CreateShortcut'))
}
$failed = @($checks.GetEnumerator() | Where-Object { -not $_.Value })
foreach($entry in $checks.GetEnumerator()){ '{0}={1}' -f $entry.Key,($(if($entry.Value){'PASS'}else{'FAIL'})) }
if($failed.Count){ throw ('GOAL88 source checks failed: ' + ($failed.Name -join ', ')) }
