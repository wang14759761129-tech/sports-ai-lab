# Read-only PTTI database inventory — 2026-10-05

All files below were inspected using SQLite read-only mode. Nominal paths can represent a Codex MSIX private view; file-ID path evidence is listed separately. This is a bounded scan, not a full-disk search. No cleanup was performed.

Unique file IDs with recorded hashes: 27. Inspection roots: LocalAppData/PTTI, LocalAppData/PTTI-Dev, Codex LocalCache/Local/PTTI, product dist (including nested builds and smoke databases), and surviving pytest-of-wang temp directories. Python Store package data was checked separately; no additional PTTI DB was found there.

| Display path | Bytes | Modified UTC | SHA256 | Integrity | SQLite schema / user version | Match / synthetic count | File ID |
|---|---:|---|---|---|---|---|---|
| `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db` | 40960 | 2026-10-05T10:16:08.714914+00:00 | `710fe918632896b02b6b0efaf68126c217b41848433035f809e128785666362a` | ok | 2 / 0 | 1 / 1 | `0x2000000012c7e1` |
| `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db.forensic-backup-20261005-185959` | 40960 | 2026-10-05T10:16:08.714914+00:00 | `710fe918632896b02b6b0efaf68126c217b41848433035f809e128785666362a` | ok | 2 / 0 | 1 / 1 | `0x4000000165ab0` |
| `C:\Users\wang\AppData\Local\PTTI\matches.db.forensic-backup-20261005-resume` | 262144 | 2026-10-05T09:32:13.424246+00:00 | `276e7e527e28f07adf0a41d9196665a8383d22ae3b793018e78a33acea6566ec` | ok | 2 / 0 | 4 / 4 | `0x40000001658fe` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-33\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T11:19:20.670873+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x3000000166574` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T11:35:20.437428+00:00 | `652872fdf2f7e828daf1b72291ba10fc389f0025175353a7d77b9d95009491de` | ok | 2 / 0 | 1 / 1 | `0xe00000014ab9a` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T11:35:19.124517+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x1100000014ab6e` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_api_persistence0\matches.db` | 139264 | 2026-10-05T11:35:20.193344+00:00 | `5c6f34e8a0b68a7cf5c5ade82a5d6154b89896af8d745b800ab8b8d9aecc9391` | ok | 2 / 0 | 1 / 0 | `0xf00000014ab7c` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T11:35:20.383519+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0xf00000014ab8f` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T11:35:20.056524+00:00 | `9a2856ccd1efed7c2847511bd8eba57e3a75ba15cc747652ce821b7e5746268c` | ok | 2 / 0 | 2 / 1 | `0x1000000014ab7a` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T11:35:18.676558+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x1200000014ab59` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T11:35:18.724183+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0xf00000014ab5b` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T11:35:18.769693+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0xf00000014ab5d` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-34\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T11:35:18.177759+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x1000000014ab54` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_absent_models_fail_gracef0\matches.db` | 73728 | 2026-10-05T11:37:31.442658+00:00 | `d08ffd7cedc70b769272638b6595223146d8ead82bed0373dd4acbb7dc92b691` | ok | 2 / 0 | 1 / 1 | `0x800000014be88` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_additive_settings_preserv0\matches.db` | 16384 | 2026-10-05T11:37:30.082286+00:00 | `c4853cff7645f332092574d5f1c11b9d5b3e12b00aa543830a6f0d784cc97819` | ok | 2 / 0 | 1 / 0 | `0x900000014be3b` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_api_persistence0\matches.db` | 139264 | 2026-10-05T11:37:31.169751+00:00 | `bba308ef8ae9a5302e59fa72424330cb6f3af863a6a8ca88a5d2bcb33da7686a` | ok | 2 / 0 | 1 / 0 | `0x900000014be46` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_external_reference_saves_0\matches.db` | 16384 | 2026-10-05T11:37:31.379463+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x800000014be7f` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_historical_api_restart_ex0\data.db` | 106496 | 2026-10-05T11:37:31.001750+00:00 | `3de4f537cbf1110a6fc9ca719fecb2bb357dff7c5dec0763f028414acf44d7a7` | ok | 2 / 0 | 2 / 1 | `0xc00000014be43` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_0\old.db` | 16384 | 2026-10-05T11:37:29.615834+00:00 | `5cbe5601e986a98eba626d3aaacb15b9993d3a75e04c11f48a548e254076c770` | ok | 2 / 0 | 0 / 0 | `0x900000014be27` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_1\old.db` | 16384 | 2026-10-05T11:37:29.669611+00:00 | `914394db9ed8fc3069c6d4994de6d441f762f705257a725756d0700e2ab512f9` | ok | 2 / 0 | 0 / 0 | `0xa00000014be29` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_settings_persist_restart_2\old.db` | 16384 | 2026-10-05T11:37:29.715611+00:00 | `874f10e9bb2ca6b39dbd804678ce463a8cd278be0c37066667e810a169b1f90c` | ok | 2 / 0 | 0 / 0 | `0x900000014be2b` |
| `C:\Users\wang\AppData\Local\Temp\pytest-of-wang\pytest-35\test_test_db_created_in_temp0\isolated-test.db` | 16384 | 2026-10-05T11:37:29.064670+00:00 | `5d1de79e6180e852cf716e1222dc0967187a90271d1fd380b690861ac3ebd91d` | ok | 2 / 0 | 0 / 0 | `0x900000014be23` |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\dist\vision-smoke.db` | 16384 | 2026-10-05T11:51:12.190844+00:00 | `106f3989fd1111eb25ae40147549d66824719f181af66a971f3c2bd7ddc1f5f9` | ok | 2 / 0 | 0 / 0 | `0x30000001654df` |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke\matches.db` | 151552 | 2026-10-05T05:57:02.532868+00:00 | `6e180ded66b3358de12481773eb1fde73df59f73a33abeaffb13d2c0023ba3c0` | ok | 1 / 0 | 3 / 2 | `0xa000000147c98` |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke12\matches.db` | 118784 | 2026-10-05T07:09:26.554887+00:00 | `ccac53941ad06177ba2421647e84876d64dee50ed4c6ed665593eee256c30f22` | ok | 2 / 0 | 1 / 1 | `0xd000000149776` |
| `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\vision-smoke.db` | 73728 | 2026-10-05T10:08:35.323117+00:00 | `675d94b013097713322fe0705e2a79016ca6eb1e2d698d357b2e10c08a806ed2` | ok | 2 / 0 | 1 / 1 | `0x400000015b63a` |
| `C:\Users\wang\AppData\Local\PTTI\matches.db` | 262144 | 2026-10-05T09:32:13.424246+00:00 | `276e7e527e28f07adf0a41d9196665a8383d22ae3b793018e78a33acea6566ec` | ok | 2 / 0 | 4 / 4 | `0xb00000014b6ba` |

## Physical file identity and record IDs

### `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db`
Reader evidence: native-before.json, store-before.json. Stable during inspection: True.

- ID `58b371ff-8231-4ae0-8547-f52b967867f9`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db.forensic-backup-20261005-185959`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI\matches.db.forensic-backup-20261005-185959`
Reader evidence: native-before.json, store-before.json. Stable during inspection: True.

- ID `58b371ff-8231-4ae0-8547-f52b967867f9`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\PTTI\matches.db.forensic-backup-20261005-resume`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\PTTI\matches.db.forensic-backup-20261005-resume`
Reader evidence: native-before.json, store-before.json. Stable during inspection: True.

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
Reader evidence: native-before.json. Stable during inspection: True.


### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke\matches.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json. Stable during inspection: True.

- ID `9410f13e-656d-481f-a48d-9bf4ca1cc593`; synthetic=True; created_at=None; updated_at=None
- ID `76872c32-836f-4c71-8679-74791991f121`; synthetic=False; created_at=None; updated_at=None
- ID `646e2c35-c27f-447c-a337-98cd6da972c0`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\smoke12\matches.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json. Stable during inspection: True.

- ID `680773a7-4d7d-4813-81f7-f6d90bf61af2`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\OneDrive\文档\ChatGPT\table tennis intelligent\research-integration\products\ptti\dist\vision-smoke.db`

Physical file-ID query: `UNKNOWN: `
Reader evidence: native-before.json. Stable during inspection: True.

- ID `36e49cd9-2380-445e-ba53-2a0d790e6c0c`; synthetic=True; created_at=None; updated_at=None

### `C:\Users\wang\AppData\Local\PTTI\matches.db`

Physical file-ID query: `A random link name to this file is \\?\C:\Users\wang\AppData\Local\PTTI\matches.db`
Reader evidence: store-before.json. Stable during inspection: True.

- ID `89466a9f-70ba-42b3-a822-f7f7956d7537`; synthetic=True; created_at=None; updated_at=None
- ID `2639a681-a572-451d-a09a-9bdd35715fd6`; synthetic=True; created_at=None; updated_at=None
- ID `e155c290-907f-4ce9-bb31-db76e04f4983`; synthetic=True; created_at=None; updated_at=None
- ID `5ed624bb-e0d1-4361-9d4b-3f7cf255f4ec`; synthetic=True; created_at=None; updated_at=None

