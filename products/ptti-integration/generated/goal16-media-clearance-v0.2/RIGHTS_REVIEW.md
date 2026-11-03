# GOAL16.2 — review of the existing nine photos

Reviewed on 2026-10-18. The nine candidates and their original file-page facts are bound to the unchanged v0.1 review manifest SHA-256 `e533ceeae42138a1bcf45099f0ea53180a29a7f21366e5f59d6ce8bebd837a49`. Every source image was opened in the browser at its original Commons resolution and visually inspected. For approved assets, actual downloaded source bytes were locally hashed; the two portraits with GPS EXIF were used only to create EXIF/GPS-stripped derivatives. No Goal15 match was linked to any photo.

The scope distinction is intentional. CC BY-SA permits reuse subject to attribution, share-alike, and no false endorsement. The PTTI use cleared here is factual athlete-profile editorial display with credit, source link, and license. No image is cleared as a homepage promotional hero, sponsor/ad creative, or endorsement. Commons' specific personality-rights warning blocks four candidates. The absence of that specific warning on the other pages is not a general publicity release; clearance is limited to the narrow editorial scope stated in the public manifest.

| Candidate | Original inspection and provenance | Editorial profile | Home promotion | Current-match image | Decision / next step |
|---|---|---:|---:|---:|---|
| Mixed final 098 — Miu Hirano / Tomokazu Harimoto / Sun Yingsha / Wang Chuqin | 3456×5184; visible mixed-doubles scene; Marcus Cyron; CC BY-SA 3.0; direct caption names four players. | NOT_CLEARED | NOT_CLEARED | NOT_CLEARED | Commons has a personality-rights warning. Ask the uploader for model-release/subject-consent evidence or use a different file without this blocker. |
| Women's singles final 061 — Miu Hirano / Sun Yingsha | 5760×3840; table-tennis scene; Marcus Cyron; CC BY-SA 3.0; English caption conflicts with German “Beachhandball” caption. | NOT_CLEARED | NOT_CLEARED | NOT_CLEARED | Personality-rights warning plus unresolved source-description contradiction. Obtain a file-page correction and resolve the warning before reconsidering. |
| Felix Lebrun — Munich 2022 | 5542×3695; clear table-tennis action; Granada / Julia Engel metadata; CC BY-SA 4.0; page names Félix and the event. | NOT_CLEARED | NOT_CLEARED | NOT_CLEARED | Explicit personality-rights warning. Ask photographer/uploader for consent evidence specific to the intended display or choose another candidate. |
| Tomokazu Harimoto — ATTC2017 file | 4138×2759; original shows Harimoto courtside in team kit, not an active rally; XIAOYU TANG, sourced from Crew of China Sports Flickr; CC BY-SA 2.0; original SHA-256 `f420e2bd10788514b33e7fc907ea23cd7a87a3b4ae2a46e8e24e2892e3fdd536`. | CLEARED_SCOPED | NOT_CLEARED | NOT_CLEARED | Profile-only; `athlete:123980`. Exact match/event round not established. |
| Jonathan Groth | 4928×3264; playing at the table; Olav76, own work; CC BY-SA 4.0; original SHA-256 `2598ed51de49a09162cf592527ecd559d65c108c3a9b20694d67c5213574b85e`. | CLEARED_SCOPED | NOT_CLEARED | NOT_CLEARED | Profile-only; `athlete:112409`. Commons description mentions Ready for Rio but does not establish this frame's exact match; label event UNKNOWN. |
| Lin Yun-Ju / Kanak Jha — YOG bronze 544 | 5760×3840; wide match view with scoreboard; Marcus Cyron; CC BY-SA 3.0. | NOT_CLEARED | NOT_CLEARED | NOT_CLEARED | Commons has a personality-rights warning; no consent/release evidence. |
| Chen Xingtong — ACTTC2016 file | 5184×3456; women's table-tennis scene; XIAOYU TANG / Crew of China Sports; CC BY-SA 2.0; source description names Chen. | NOT_CLEARED | NOT_CLEARED | NOT_CLEARED | No canonical athlete ID in current public package; do not join by name. Resolve official athlete identity/ID in the public catalog first. |
| Wang Manyu — ACTTC2016 file | 3456×5184 display orientation; source stored 5184×3456 with EXIF rotation; full-body table-side photo; XIAOYU TANG / Crew of China Sports; CC BY-SA 2.0; original SHA-256 `a8e92964a6538136566c4f0140477f9c3eb986e9f86d50215c21e3a0c740b28f`. | CLEARED_SCOPED | NOT_CLEARED | NOT_CLEARED | Profile-only; `athlete:121411`. Exact opponent/match not established. Orientation was normalized; derivatives strip EXIF/GPS. |
| Liang Jingkun — ACTTC2016 file | 5184×3456; action frame with the ball overlapping part of his face; XIAOYU TANG / Crew of China Sports; CC BY-SA 2.0; original SHA-256 `73525784ec787111dfb83b24db217a8ce54705f5fb8b3c83cd491da332f22e00`. | CLEARED_SCOPED | NOT_CLEARED | NOT_CLEARED | Profile-only; `athlete:119588`. Full 3:2 derivatives preserve context; portrait crop was rejected after visual QA. |

## Rights evidence and limits

- The source page for each asset is the authoritative per-file Commons record. Flickr-derived images state that FlickreviewR confirmed CC BY-SA 2.0; Jonathan's page identifies own work under CC BY-SA 4.0.
- Creative Commons deeds state that commercial sharing/adaptation is permitted when terms are followed, attribution must not imply endorsement, and adaptations follow ShareAlike. The 4.0 deed also says other publicity/privacy/moral rights may still limit a particular use; this review therefore does not create blanket likeness or endorsement permission.
- The 4 cleared decisions are only for factual, attributed athlete-profile/editorial display. Do not extend them to homepage marketing, sponsored content, endorsements, exact-match imagery, or other use without a new review.
- No source image or derivatives are associated with a Goal15 match. Candidate event tags (`ATTC2017`, `ACTTC2016`) do not establish exact match identity or opponent.
- The 5 blocked files were not downloaded and have no computed source SHA. The four approved original images are locally retained in `reviewed-originals/` under a nested `.gitignore`; source copies are not part of the strict-public package or Git commit.

## Reproduction and validation

```powershell
python products/ptti-integration/scripts/build_goal16_public_media.py --build
python products/ptti-integration/scripts/build_goal16_public_media.py --validate
python -m unittest discover -s products/ptti-integration/tests -p test_goal16_media_clearance_v02.py
```
