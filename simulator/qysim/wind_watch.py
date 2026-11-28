"""Three watches on the annual jacket work order. All values are fictional site conditions."""
from dataclasses import replace

from .world import Cylinder


def inspection_site(index, station):
    from .cold_open import cold_open_jacket
    site = cold_open_jacket()
    # View the projecting bars obliquely so their ends and the gap to the leg are visible.
    target = site.objectives[index]
    target.point = (*station, target.point[2])
    return site


def wind_set():
    site = inspection_site(0, (-9.35, -6.95))
    flow = replace(site.current, surface_kn=.9, mid_kn=.65, bottom_kn=.3, surface_dir=90, mid_dir=90)
    return replace(site, key='wind_set', name='東南放纜位', current=flow,
                   start_pos=(-10, -9, 11.7), start_heading_deg=25)


def wind_shadow():
    site = inspection_site(1, (8.1, -4.85))
    # The outboard cable riser crosses the pilot's sightline before the leg emerges from the silt.
    riser = [
        Cylinder('B riser', (7.3, -7.4, -1), (7.3, -7.4, 28), .18, 'j_tube'),
        Cylinder('B riser bend', (7.3, -7.4, 28), (8.4, -8.5, 31), .18, 'j_tube'),
        Cylinder('B riser bellmouth', (8.4, -8.5, 31), (9.1, -9.2, 31.6), .22, 'j_tube'),
        Cylinder('B export cable sleeve', (9.1, -9.2, 31.6), (14, -14.1, 32), .15, 'cable_protection'),
    ]
    for depth in (6, 11.3, 17, 23):
        centre = 4.8 + (depth + 3) / 30
        riser.append(Cylinder(f'B riser bracket {depth}m', (centre, -centre, depth),
                              (7.3, -7.4, depth), .08, 'j_tube'))
    return replace(site, key='wind_shadow', name='北面 B 腿', visibility_m=5.2,
                   start_pos=(10, -7.9, 11.7), start_heading_deg=147, spool_pos=(24, -18, 0),
                   objectives=[site.objectives[1]], obstacles=[*site.obstacles, *riser])


def wind_return():
    # Fictional worn termination for this season's final watch.
    site = inspection_site(0, (-9.35, -6.95))
    return replace(site, key='wind_return', name='季末 C 腿', tether={'termination_ratio': 0.09})
