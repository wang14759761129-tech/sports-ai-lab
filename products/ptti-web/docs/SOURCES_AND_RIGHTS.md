# Source and rights notes

Reviewed 2026-10-12 for PTTI Web MVP v0.3. The MVP stores source metadata and links. It does not store media files, thumbnails, athlete portraits, excerpts from videos, or copied social posts.

## Cinema sample

| Sample | PTTI action / route type | Official source evidence | Content classification | Playback | Territory |
| --- | --- | --- | --- | --- | --- |
| Fan Zhendong vs Wang Chuqin, WTT Finals Men Doha 2023, MS final | [查看官方赛事页面](https://www.worldtabletennis.com/eventInfo?eventId=2866&selectedTab=Overview&innerselectedTab=Completed&subEvt=MSINGLES) · `event-page` | WTT page lists the specifically titled MS Final item in Related Videos and reports the 4–0 result; this PTTI action still opens the event page | Specific match-video tile exists inside the event page; no direct video URL verified for this record | NOT_TESTED | Unknown; no territory result collected |
| Fan Zhendong vs Lin Gaoyuan, WTT Finals Men Doha 2023, MS semifinal | [前往官方视频页面](https://www.youtube.com/watch?v=qIXmFTzXcs0) · `video-page` | [WTT event page](https://www.worldtabletennis.com/eventInfo?eventId=2866&selectedTab=Overview&innerselectedTab=Completed&subEvt=MSINGLES) lists the exact MS SF item; WTT's verified YouTube channel has the matching specific-match video page | Specific match video page, not a highlights compilation | NOT_TESTED | Unknown; no territory result collected |
| Wang Yidi vs Sun Yingsha, WTT Cup Finals Singapore 2021, WS final | [前往官方视频页面](https://www.youtube.com/watch?v=XHGCGiAyKkc) · `video-page` | [WTT event page](https://www.worldtabletennis.com/eventInfo?eventId=2536&selectedTab=Overview) lists the match video; YouTube title and channel are attributed to World Table Tennis | Specific women's singles final video page | NOT_TESTED | Unknown; no territory result collected |
| Sun Yingsha vs Chen Xingtong, WTT Champions Chongqing 2025, WS final | [仅供查看来源](https://www.worldtabletennis.com/description?artId=4731) · `source-only` | WTT article confirms the final and score, and offers generic event-level viewing links; no match-specific watch URL is registered | Source article only; generic event viewing text is not a specific video link | NOT_TESTED; no PTTI watch route | Unknown; no territory result collected |

“Official listing found” means that an official WTT page or WTT’s verified YouTube channel identifies the match/media. It does not prove the video can be played from a user’s location. A web page responding is not a playback test. Region restrictions, logins, subscriptions and player behavior must be checked by the user on the publisher site.

## Pulse and Stars link audit

| Existing item | URL | Verified classification |
| --- | --- | --- |
| Pulse: Top Points of Day 3, WTT Finals Men Doha 2023 | [WTT YouTube video](https://www.youtube.com/watch?v=LA-29LQ0mqM) | WTT-published multi-point highlight reel, not a specific full-match page; publisher attribution is verified; playback NOT_TESTED |
| Pulse: Alvaro Robles feature | [WTT article](https://www.worldtabletennis.com/description?artId=4137) | Article by WTT Team; the page discusses Robles’ WTT Champions debut, not a training video |
| Pulse: France vs China Busan final preview | [WTT article](https://www.worldtabletennis.com/description?artId=3474) | WTT Team event preview; the article has generic event viewing links, not a specific match video |
| Stars: Wang Chuqin / Fan Zhendong | [WTT Finals Doha event page](https://www.worldtabletennis.com/eventInfo?eventId=2866&selectedTab=Overview&innerselectedTab=Completed&subEvt=MSINGLES) | Official event page confirms the event and related match-video listings; it is not itself a match video page |
| Stars: Sun Yingsha | [WTT Cup Finals Singapore event page](https://www.worldtabletennis.com/eventInfo?eventId=2536&selectedTab=Overview) and [WTT Chongqing result article](https://www.worldtabletennis.com/description?artId=4731) | Official WTT event/article pages; neither is claimed to be a specific video page |
| Wang Chuqin candidate social account | [Candidate Weibo profile](https://weibo.com/u/3197845214) | Public profile identifies as Wang Chuqin and says national team player, but platform verification was not confirmed; PTTI retains the “candidate” label |

The listed official links were checked for destination, publisher, and whether the content is an event page, specific match video, highlight compilation, or article. A successful page response does not prove video playback or regional availability.

The curated list is static. It does not claim real-time or automatic updates. Third-party reviews, training videos and additional social accounts are not included in this first sample because a sufficiently clear original publisher/source record was not verified for this build.

## Rights handling

PTTI uses text labels, match facts and links to the original publishers. It does not download, copy, proxy, screen-capture or host official match video. It does not use player likenesses or third-party thumbnails. No embedded player is used because embed permission has not been checked. Users must follow the destination publisher’s own territory, account, subscription and copyright terms.

## Sprint 0.2 route labels

The UI distinguishes three destinations: an official event page, an official video page, and source information only. The action text describes the destination. Every current record remains playback-unverified, and a source-only record has no match-specific watch URL. No media is embedded or hosted.
