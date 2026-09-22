# Annotation guide

Use the smallest reliable category. If the video cannot support a decision, record `unknown` or `unclear`.

## Serve length

- **short:** second bounce would land on or near the table before the end line.
- **half_long:** second bounce would be near the end line and may invite an attack.
- **long:** ball reaches or passes the end-line region on the first bounce.
- **unclear:** the view does not support a stable classification.

## Serve location

Version 1 uses three broad zones: `forehand`, `middle`, `backhand`. A future version may use 6 or 9 zones after feasibility is tested.

## Serve spin

Use `backspin`, `sidespin`, `topspin`, `no_spin`, or `mixed`. If spin cannot be reliably inferred from the video, use `unknown`; do not infer spin from the score or later outcome.

## Receive type

Use `push`, `flick`, `chiquita` / backhand banana flick, `drive`, `loop`, `long_push`, `short_touch`, `other`, or `unclear`.

## Third-ball attack

Record `yes` when the server's third contact is an intentional attacking action aimed at gaining an advantage, such as a drive or loop. Record `no` when the third contact is clearly non-attacking or no attack is attempted. Use `unclear` when intent or contact cannot be judged. Do not label an action “yes” merely because it looks fast.

## Rally length

Count the serve as ball contact 1. Count each subsequent legal contact until the point ends. Use `unknown` if the video skips or hides contacts.

## Virtual examples

1. **Short backspin to backhand → short push → forehand third-ball flick:** `serve_length=short`, `serve_location=backhand`, `serve_spin=backspin`, `receive_type=short_touch`, `third_ball_attack=yes`, `third_ball_side=forehand`.
2. **Long serve to backhand → receiver loops immediately:** server has no third-ball contact; `receive_type=loop`, `third_ball_attack=not_applicable`, with a note explaining why.
3. **Half-long sidespin to middle → receive unclear in an occluded frame:** record the visible serve fields, `receive_type=unclear`, and a timestamp note.
4. **No-spin short serve → long push → server opens with a loop:** `serve_spin=no_spin`, `receive_type=long_push`, `third_ball_attack=yes`, `third_ball_side=forehand` if visible.
5. **Serve and first contacts visible, but spin cannot be judged:** keep location and length if supported; use `serve_spin=unknown`, never a guessed category.
