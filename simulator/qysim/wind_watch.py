"""Three watches on the annual jacket work order. All values are fictional site conditions."""
from dataclasses import replace


def wind_set():
    from .cold_open import cold_open_jacket
    site = cold_open_jacket()
    flow = replace(site.current, surface_kn=.9, mid_kn=.65, bottom_kn=.3, surface_dir=90, mid_dir=90)
    return replace(site, key='wind_set', name='東南放纜位', current=flow)


def wind_shadow():
    from .cold_open import cold_open_jacket
    site = cold_open_jacket()
    return replace(site, key='wind_shadow', name='北面 B 腿', visibility_m=3.8,
                   start_pos=(12, -9, 11.5), start_heading_deg=145, spool_pos=(24, -18, 0),
                   objectives=[site.objectives[1]])


def wind_return():
    from .cold_open import cold_open_jacket
    # Remaining strength of this dive's termination is provisional. Sustained thrust on a pinned
    # line loads it even if the line no longer slides and therefore stops accumulating chafe.
    return replace(cold_open_jacket(), key='wind_return', name='季末 C 腿',
                   tether={'termination_ratio': 0.09})
