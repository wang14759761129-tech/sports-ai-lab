# Read-only PTTI database inventory — 2026-10-05

Nominal paths can resolve to Codex MSIX private backing files. Distinct NTFS file IDs are listed once; before/final reader snapshots are retained separately under ignored outputs/db-trace. Inspection never restores or cleans a database.

Discovered file identities during this run: 67. Present in final bounded scans: 48. Retained before-scan test files may no longer be present after normal pytest temp retention. Guard regression fixtures containing non-SQLite bytes are labelled by their SQLite error; they are not corrupted user databases.

Scan roots: LocalAppData/PTTI, PTTI-Dev, Codex LocalCache/Local/PTTI, product dist and data, surviving pytest-of-wang temp paths, and the explicit temporary packaged-app QA directory. The Python Store package data scan found no additional PTTI database. This is not a full-disk search.

| Display path | Bytes | Modified UTC | SHA256 | Integrity | Schema / user version | Matches / synthetic | File ID | Final scan |
|---|---:|---|---|---|---|---|---|---|
| `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db` | 40960 | 2026-10-05T10:16:08.714914+00:00 | `710fe918632896b02b6b0efaf68126c217b41848433035f809e128785666362a` | ok | 2 / 0 | 1 / 1 | `0x2000000012c7e1` | present |
| `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db.forensic-backup-20261005-185959` | 40960 | 2026-10-05T10:16:08.714914+00:00 | `710fe918632896b02b6b0efaf68126c217b41848433035f809e128785666362a` | ok | 2 / 0 | 1 / 1 | `0x4000000165ab0` | present |
| `C:\Users\wang\AppData\Local\PTTI\matches.db.forensic-backup-20261005-resume` | 262144 | 2026-10-05T09:32:13.424246+00:00 | `276e7e527e28f07adf0a41d9196665a8383d22ae3b793018e78a33acea6566ec` | ok | 2 / 0 | 4 / 4 | `0x40000001658fe` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-33\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T11:19:20.670873+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x3000000166574` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T11:35:20.437428+00:00 | `652872fdf2f7e828daf1b72291ba10fc389f0025175353a7d77b9d95009491de` | ok | 2 / 0 | 1 / 1 | `0xe00000014ab9a` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T11:35:19.124517+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x1100000014ab6e` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_api_persistence0\matches.db` | 139264 | 2026-10-05T11:35:20.193344+00:00 | `5c6f34e8a0b68a7cf5c5ade82a5d6154b89896af8d745b800ab8b8d9aecc9391` | ok | 2 / 0 | 1 / 0 | `0xf00000014ab7c` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T11:35:20.383519+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0xf00000014ab8f` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T11:35:20.056524+00:00 | `9a2856ccd1efed7c2847511bd8eba57e3a75ba15cc747652ce821b7e5746268c` | ok | 2 / 0 | 2 / 1 | `0x1000000014ab7a` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T11:35:18.676558+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x1200000014ab59` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T11:35:18.724183+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0xf00000014ab5b` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T11:35:18.769693+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0xf00000014ab5d` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T11:35:18.177759+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x1000000014ab54` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T11:37:31.442658+00:00 | `d08ffd7cedc70b769272638b6595223146d8ead82bed0373dd4acbb7dc92b691` | ok | 2 / 0 | 1 / 1 | `0x800000014be88` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T11:37:30.082286+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x900000014be3b` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_api_persistence0\matches.db` | 139264 | 2026-10-05T11:37:31.169751+00:00 | `bba308ef8ae9a5302e59fa72424330cb6f3af863a6a8ca88a5d2bcb33da7686a` | ok | 2 / 0 | 1 / 0 | `0x900000014be46` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T11:37:31.379463+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x800000014be7f` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T11:37:31.001750+00:00 | `3de4f537cbf1110a6fc9ca719fecb2bb357dff7c5dec0763f028414acf44d7a7` | ok | 2 / 0 | 2 / 1 | `0xc00000014be43` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T11:37:29.615834+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x900000014be27` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T11:37:29.669611+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0xa00000014be29` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T11:37:29.715611+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0x900000014be2b` | not in final scan |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T11:37:29.064670+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x900000014be23` | not in final scan |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\dist\vision-smoke.db` | 16384 | 2026-10-05T11:51:12.190844+00:00 | `106f3989fd1111eb25ae40147549d66824719f181af66a971f3c2bd7ddc1f5f9` | ok | 2 / 0 | 0 / 0 | `0x30000001654df` | present |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke\matches.db` | 151552 | 2026-10-05T05:57:02.532868+00:00 | `6e180ded66b3358de12481773eb1fde73df59f73a33abeaffb13d2c0023ba3c0` | ok | 1 / 0 | 3 / 2 | `0xa000000147c98` | present |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke12\matches.db` | 118784 | 2026-10-05T07:09:26.554887+00:00 | `ccac53941ad06177ba2421647e84876d64dee50ed4c6ed665593eee256c30f22` | ok | 2 / 0 | 1 / 1 | `0xd000000149776` | present |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\vision-smoke.db` | 73728 | 2026-10-05T10:08:35.323117+00:00 | `675d94b013097713322fe0705e2a79016ca6eb1e2d698d357b2e10c08a806ed2` | ok | 2 / 0 | 1 / 1 | `0x400000015b63a` | present |
| `C:\Users\wang\AppData\Local\PTTI\matches.db` | 262144 | 2026-10-05T09:32:13.424246+00:00 | `276e7e527e28f07adf0a41d9196665a8383d22ae3b793018e78a33acea6566ec` | ok | 2 / 0 | 4 / 4 | `0xb00000014b6ba` | present |
| `C:\Users\wang\AppData\Local\Temp\PTTI-isolation-qa-593d5bc\matches.db` | 73728 | 2026-10-05T12:52:30.655524+00:00 | `c3d167711e6d44dbab4ac04aedeb9ee112b1558d229bf58d3588e48b26151660` | ok | 2 / 0 | 1 / 1 | `0x40000001664ae` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T12:32:51.477934+00:00 | `af0c0307ad90c9a8b77225faf2c52cff334c9e861f7ae1a5b84a7f905a7da52b` | ok | 2 / 0 | 1 / 1 | `0xf00000012129c` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T12:32:47.450685+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x1100000010b466` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_api_persistence0\matches.db` | 139264 | 2026-10-05T12:32:50.651401+00:00 | `a54fece009c4ddf35463e3699d901e82890b979575c58930ee57702f7aa4cb6e` | ok | 2 / 0 | 1 / 0 | `0x2200000010cd3b` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T12:32:51.031873+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x1600000011f3e9` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_is_rechecked_on_eve0\dev.db` | 9 | 2026-10-05T12:32:42.208138+00:00 | `9b2bbce6c72dd9bbd9c7a9976d5d76d1fcc2bb9832dec246375bb92006beccc3` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x14000000107de8` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_rejects_msix_produc0\dev.db` | 9 | 2026-10-05T12:32:42.197549+00:00 | `9b2bbce6c72dd9bbd9c7a9976d5d76d1fcc2bb9832dec246375bb92006beccc3` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x140000000ece6d` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db` | 7 | 2026-10-05T12:32:42.199110+00:00 | `715dc8493c36579a5b116995100f635e3572fdf8703e708ef1a08d943b36774e` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x3e0000000ee98d` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T12:32:49.411067+00:00 | `e44ff6a9bef98970cc0b4bd7a80bf3aa2f1398a189035c9dd9956541377d724c` | ok | 2 / 0 | 2 / 1 | `0x2200000010cb4c` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T12:32:43.428348+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x1300000010879e` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T12:32:43.951548+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0x1300000010885e` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T12:32:44.481346+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0x1400000010a027` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_startup_banner_and_runtim0\diagnostic.db` | 16384 | 2026-10-05T12:32:42.338176+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x16000000107ea5` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T12:32:42.579206+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x12000000108115` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T12:39:16.379317+00:00 | `d76fbb3b2d8eece3333d554e03068018f22e2c3bc6646bc86a07d21187408b91` | ok | 2 / 0 | 1 / 1 | `0x4000000165935` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T12:39:10.120707+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x7000000165900` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_api_persistence0\matches.db` | 139264 | 2026-10-05T12:39:14.922334+00:00 | `cb57296c83494533ff96944554a53c073224577631f4697833c2bfc2fda5053c` | ok | 2 / 0 | 1 / 0 | `0x4000000165916` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T12:39:15.809460+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x500000016592c` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_is_rechecked_on_eve0\dev.db` | 9 | 2026-10-05T12:39:01.712556+00:00 | `9b2bbce6c72dd9bbd9c7a9976d5d76d1fcc2bb9832dec246375bb92006beccc3` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x5000000165895` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_rejects_msix_produc0\dev.db` | 9 | 2026-10-05T12:39:01.643060+00:00 | `9b2bbce6c72dd9bbd9c7a9976d5d76d1fcc2bb9832dec246375bb92006beccc3` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x400000016588b` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db` | 7 | 2026-10-05T12:39:01.644679+00:00 | `715dc8493c36579a5b116995100f635e3572fdf8703e708ef1a08d943b36774e` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x4000000165891` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T12:39:13.083190+00:00 | `f079d846c62a0de1f32e883a018c81eab3d8176d74b9365b9bc812b182a94c0a` | ok | 2 / 0 | 2 / 1 | `0x5000000165910` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T12:39:03.473214+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x90000001658a8` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T12:39:04.352497+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0x40000001658ce` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T12:39:05.203835+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0x50000001658d9` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_startup_banner_and_runtim0\diagnostic.db` | 16384 | 2026-10-05T12:39:02.015717+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x7000000165897` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T12:39:02.435897+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x50000001658a1` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T12:47:40.757533+00:00 | `1503ccd72ded2c6400d36391ca0bf24c974d828a04be98c84ce6deb9e70f9680` | ok | 2 / 0 | 1 / 1 | `0x5000000165df5` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T12:47:35.407251+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x6000000165dbc` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_api_persistence0\matches.db` | 139264 | 2026-10-05T12:47:39.727659+00:00 | `749972c375207194991d8dd5060a018df21f8d3b6206a9ba0df12938376d5655` | ok | 2 / 0 | 1 / 0 | `0x6000000165dd7` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T12:47:40.221315+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x4000000165deb` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_is_rechecked_on_eve0\dev.db` | 9 | 2026-10-05T12:47:27.555400+00:00 | `9b2bbce6c72dd9bbd9c7a9976d5d76d1fcc2bb9832dec246375bb92006beccc3` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x5000000165d80` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_rejects_msix_produc0\dev.db` | 9 | 2026-10-05T12:47:27.486130+00:00 | `9b2bbce6c72dd9bbd9c7a9976d5d76d1fcc2bb9832dec246375bb92006beccc3` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x6000000165d76` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db` | 7 | 2026-10-05T12:47:27.487692+00:00 | `715dc8493c36579a5b116995100f635e3572fdf8703e708ef1a08d943b36774e` | file is not a database | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | `0x5000000165d7c` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T12:47:38.026594+00:00 | `e4bfb99ade551fa969354850197749c7b7d6d043f85d1e5414a86bae745f5ad5` | ok | 2 / 0 | 2 / 1 | `0x4000000165dcc` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T12:47:29.288127+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x5000000165d93` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T12:47:30.063542+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0x4000000165d98` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T12:47:30.846891+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0x6000000165d9d` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_startup_banner_and_runtim0\diagnostic.db` | 16384 | 2026-10-05T12:47:27.859902+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x6000000165d83` | present |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T12:47:28.315295+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x5000000165d8d` | present |

## Physical identity and record IDs

### `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db`
Reader evidence: native-before.json, native-final2.json, store-before.json, store-final2.json. Stable during inspection: True.

- ID `58b371ff-8231-4ae0-8547-f52b967867f9`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db.forensic-backup-20261005-185959`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db.forensic-backup-20261005-185959`
Reader evidence: native-before.json, native-final2.json, store-before.json, store-final2.json. Stable during inspection: True.

- ID `58b371ff-8231-4ae0-8547-f52b967867f9`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\PTTI\matches.db.forensic-backup-20261005-resume`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\PTTI\matches.db.forensic-backup-20261005-resume`
Reader evidence: native-before.json, native-final2.json, store-before.json, store-final2.json. Stable during inspection: True.

- ID `89466a9f-70ba-42b3-a822-f7f7956d7537`; synthetic=True; created_at=None; updated_at=None
- ID `2639a681-a572-451d-a09a-9bdd35715fd6`; synthetic=True; created_at=None; updated_at=None
- ID `e155c290-907f-4ce9-bb31-db76e04f4983`; synthetic=True; created_at=None; updated_at=None
- ID `5ed624bb-e0d1-4361-9d4b-3f7cf255f4ec`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-33\test_test_db_created_in_temp0\isolated-test.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-33\test_test_db_created_in_temp0\isolated-test.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_absent_models_fail_gracef0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_absent_models_fail_gracef0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `74a23dbd-bea7-48b2-9c9a-639ffa6f4f1e`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_additive_settings_preserv0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_additive_settings_preserv0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `old-match`; synthetic=None; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_api_persistence0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_api_persistence0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `40e33f61-3b7d-4a52-8af9-2b6073c7a6ab`; synthetic=False; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_external_reference_saves_0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_external_reference_saves_0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_historical_api_restart_ex0\data.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_historical_api_restart_ex0\data.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `77c05ae6-f3ef-45fb-b7c1-b945c8eac633`; synthetic=False; created_at=None; updated_at=None
- ID `b8fe8a8c-4a8e-4eee-a4a0-cf0e38048cb9`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_0\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_0\old.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_1\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_1\old.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_2\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_2\old.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_test_db_created_in_temp0\isolated-test.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_test_db_created_in_temp0\isolated-test.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_absent_models_fail_gracef0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_absent_models_fail_gracef0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `570e22d0-d803-4f15-ad88-ec83fbd0c03d`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_additive_settings_preserv0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_additive_settings_preserv0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `old-match`; synthetic=None; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_api_persistence0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_api_persistence0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `3efbeec1-6186-4e7b-abd6-1fe096d526af`; synthetic=False; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_external_reference_saves_0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_external_reference_saves_0\matches.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_historical_api_restart_ex0\data.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_historical_api_restart_ex0\data.db`
Reader evidence: native-before.json. Stable during inspection: True.

- ID `f52a8e1f-68e9-47a5-a0c3-8eba176919a3`; synthetic=False; created_at=None; updated_at=None
- ID `f42427de-38f0-40b0-9214-f7f3b6a02f66`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_0\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_0\old.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_1\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_1\old.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_2\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_2\old.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_test_db_created_in_temp0\isolated-test.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_test_db_created_in_temp0\isolated-test.db`
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\dist\vision-smoke.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json, native-final2.json. Stable during inspection: True.


### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke\matches.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json, native-final2.json. Stable during inspection: True.

- ID `9410f13e-656d-481f-a48d-9bf4ca1cc593`; synthetic=True; created_at=None; updated_at=None
- ID `76872c32-836f-4c71-8679-74791991f121`; synthetic=False; created_at=None; updated_at=None
- ID `646e2c35-c27f-447c-a337-98cd6da972c0`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke12\matches.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json, native-final2.json. Stable during inspection: True.

- ID `680773a7-4d7d-4813-81f7-f6d90bf61af2`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\vision-smoke.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json, native-final2.json. Stable during inspection: True.

- ID `36e49cd9-2380-445e-ba53-2a0d790e6c0c`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\PTTI\matches.db`
Reader evidence: store-before.json, store-final2.json. Stable during inspection: True.

- ID `89466a9f-70ba-42b3-a822-f7f7956d7537`; synthetic=True; created_at=None; updated_at=None
- ID `2639a681-a572-451d-a09a-9bdd35715fd6`; synthetic=True; created_at=None; updated_at=None
- ID `e155c290-907f-4ce9-bb31-db76e04f4983`; synthetic=True; created_at=None; updated_at=None
- ID `5ed624bb-e0d1-4361-9d4b-3f7cf255f4ec`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\PTTI-isolation-qa-593d5bc\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\PTTI-isolation-qa-593d5bc\matches.db`
Reader evidence: native-final2.json, store-final2.json. Stable during inspection: True.

- ID `2c1e0b4f-d7d4-4deb-ba7c-ac89c438c1d4`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_absent_models_fail_gracef0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_absent_models_fail_gracef0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `d63acf9f-24b4-456c-b775-e8d2e2ea5dc7`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_additive_settings_preserv0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_additive_settings_preserv0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `old-match`; synthetic=None; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_api_persistence0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_api_persistence0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `c78583af-ccd9-404e-958a-3e37ad78be97`; synthetic=False; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_external_reference_saves_0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_external_reference_saves_0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_is_rechecked_on_eve0\dev.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_is_rechecked_on_eve0\dev.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_rejects_msix_produc0\dev.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_rejects_msix_produc0\dev.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_historical_api_restart_ex0\data.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_historical_api_restart_ex0\data.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `5b62c5c8-ac24-4233-8dc3-f2a734167d52`; synthetic=False; created_at=None; updated_at=None
- ID `5ac15406-b2e0-48fd-9018-ff74a3510a6f`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_0\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_0\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_1\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_1\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_2\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_settings_persist_restart_2\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_startup_banner_and_runtim0\diagnostic.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_startup_banner_and_runtim0\diagnostic.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_test_db_created_in_temp0\isolated-test.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-39\test_test_db_created_in_temp0\isolated-test.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_absent_models_fail_gracef0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_absent_models_fail_gracef0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `1ff4a17d-a1af-4266-8977-eea7d46113be`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_additive_settings_preserv0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_additive_settings_preserv0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `old-match`; synthetic=None; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_api_persistence0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_api_persistence0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `7d9ded90-d230-4dc5-bc13-a2c956b59eb7`; synthetic=False; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_external_reference_saves_0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_external_reference_saves_0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_is_rechecked_on_eve0\dev.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_is_rechecked_on_eve0\local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_rejects_msix_produc0\dev.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_rejects_msix_produc0\local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_historical_api_restart_ex0\data.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_historical_api_restart_ex0\data.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `d08b5035-f32b-46ab-9ae1-a1a2b154f1cf`; synthetic=False; created_at=None; updated_at=None
- ID `75463457-67b1-4821-8f25-ee2ca4aa8585`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_0\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_0\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_1\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_1\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_2\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_settings_persist_restart_2\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_startup_banner_and_runtim0\diagnostic.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_startup_banner_and_runtim0\diagnostic.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_test_db_created_in_temp0\isolated-test.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-40\test_test_db_created_in_temp0\isolated-test.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_absent_models_fail_gracef0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_absent_models_fail_gracef0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `9ce59a91-46a6-4811-bcb5-4f506f98ba88`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_additive_settings_preserv0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_additive_settings_preserv0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `old-match`; synthetic=None; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_api_persistence0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_api_persistence0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `9dc61b87-52de-440f-bf35-51da097b5d31`; synthetic=False; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_external_reference_saves_0\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_external_reference_saves_0\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_is_rechecked_on_eve0\dev.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_is_rechecked_on_eve0\local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_rejects_msix_produc0\dev.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_rejects_msix_produc0\local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_guard_rejects_msix_produc0\local\Packages\OpenAI.Codex_test\LocalCache\Local\PTTI\matches.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_historical_api_restart_ex0\data.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_historical_api_restart_ex0\data.db`
Reader evidence: native-final2.json. Stable during inspection: True.

- ID `e2274f61-391e-48a1-9b74-5e7080d136e3`; synthetic=False; created_at=None; updated_at=None
- ID `42f128eb-6eb8-4f06-b97e-769778f93205`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_0\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_0\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_1\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_1\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_2\old.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_settings_persist_restart_2\old.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_startup_banner_and_runtim0\diagnostic.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_startup_banner_and_runtim0\diagnostic.db`
Reader evidence: native-final2.json. Stable during inspection: True.


### `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_test_db_created_in_temp0\isolated-test.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-41\test_test_db_created_in_temp0\isolated-test.db`
Reader evidence: native-final2.json. Stable during inspection: True.
