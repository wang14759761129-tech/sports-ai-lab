# CVAT local research workflow — prepared, service not verified

Decision: **C_LATER / TRIAL**. Lack of dense ball truth is a current bottleneck; CVAT usability/efficiency remains unmeasured.
No Docker command/standard Docker Desktop executable was present. CVAT Community was not deployed.
Frame navigation, task collaboration and actual 100-event annotation time were NOT TESTED.
There is no claim that CVAT is faster than the current workflow. An external annotation workstation is the next prerequisite.

## Prepared material

- Five different RacketVision official TRAIN image tasks: all 125 native sparse ball labels, including 115 visible and 10 absent.
- Three one-second OpenTTGames TRAIN DEV context videos: one sampled unmatched Hit candidate per game.
- Nine sampled Hit-FP still/context entries retained in the mining queue. They are NOT asserted to be ball detector negatives.
- Existing native GT -> CVAT XML -> PTTI adapter round-trip preserved all 125 source frame/time/visibility/coordinate rows.
  This is real-data format engineering QA, not a real CVAT UI export or new human annotation.
- ZIP integrity and 120-frame short-video output checks passed. Scene categories and negative reasons require reviewer confirmation.

Everything remains under `%LOCALAPPDATA%/PTTI-Dev/technology-foundation/benchmark-v0/cvat-tasks/`.
No video, images or dataset labels are packaged, committed or uploaded to a service.

## Minimum acceptance session after deployment

1. Follow [official Community install](https://docs.cvat.ai/docs/administration/community/basics/installation/) on a suitable isolated machine.
2. Create one project, import the label definitions in `research/vision-benchmark/cvat-labels.json`.
3. Start with BALL point/box and HIT event tags. Use BALL_ABSENT only when visually reviewed; no shape is UNKNOWN.
4. Preserve the per-task source frame map, source video SHA, crop/start time and source FPS.
5. Add reviewer identity/status, occlusion/uncertainty and striking-player attributes. Do not guess technique or tactics.
6. Export native CVAT XML and parse using `ptti_benchmark.cvat.read_cvat_xml(xml_path, frame_map)`.
7. Outside track marks remain UNKNOWN; interpolation is not silently converted to manual GT.
8. Time a real 100-event task, review corrections and compare with the present workflow before ADOPT.
9. Confirm permissions/attribution and seal annotation SHA256 before promoting the dataset into a benchmark manifest.

Extended OpenTTGames is CC BY-NC-SA 4.0, research/non-commercial. RacketVision dataset redistribution rights are not separately established;
keep local existing research access and do not distribute those task ZIPs without rights review.
CVAT core MIT code rights do not change dataset rights.

Export schema: [CVAT 1.1](https://docs.cvat.ai/docs/dataset_management/formats/format-cvat/).
