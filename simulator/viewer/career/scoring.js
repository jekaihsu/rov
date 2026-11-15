// Deliverable-based scoring of YX work orders: what each deliverable kind is called, the score of a dive from its
// checklist and penalties, the medal, and the payout (base × quality − penalties) with the "abort but pass" path.
// Pure functions, no DOM; the numbers are game values, not an industry standard.

export const DELIVERABLE_KIND_LABELS = {
  state: '程序',
  checkpoint: '到點',
  station_keep: '懸停',
  inspect: '目視',
  photo: '照片',
  measure: '量測',
  probe: '探測',
  confirm: '確認',
  surface: '回收',
};

// Repeating a contract already completed pays this share of its base pay.
export const REPEAT_RATE = 0.75;
