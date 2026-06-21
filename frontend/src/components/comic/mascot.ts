/** Captain Ddoski mascot poses, one per recurring product moment. Keep this
 * list in sync with the files actually in /public — used wherever the UI
 * needs to swap a generic icon for the mascot. */
export const MASCOT = {
  standing: "/captain_standing.png", // idle / brand mark
  point: "/captain_point.png", // working / scanning / tool call in flight
  protect: "/captain_protect.png", // shield up / hero banner
  research: "/captain_research.png", // investigating / agent reasoning
  success: "/captain_success.png", // USE / validated / confetti
  warningStop: "/captain_warning_stop.png", // AVOID / blocked / error
  pointForward: "/captain_with_an_arrow_or_sent.png", // CTA / forward nav
  goodLike: "/captain_good_like.png", // trust seal / thumbs up
} as const;

export type MascotPose = keyof typeof MASCOT;
