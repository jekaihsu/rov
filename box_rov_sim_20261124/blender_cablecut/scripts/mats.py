from lib import *

def hexpattern(n, seed):
    # fine tread plate / grip pattern used on rubber & plates
    y, x = np.mgrid[0:n, 0:n] / n
    return 0.12 * (np.sin(x * 2 * math.pi * 48) * np.sin(y * 2 * math.pi * 48) > 0.2)

def yarn_pattern(n, seed):
    y, x = np.mgrid[0:n, 0:n] / n
    # diagonal twisted strands + fibres
    d = np.sin((x * 1.0 + y * 0.45) * 2 * math.pi * 40) * 0.5 + 0.5
    fib = fbm(n, 0.6, seed + 40, aniso=(1.0, 0.06))
    return 0.55 * d + 0.3 * fib

def helix_pattern(n, seed):
    y, x = np.mgrid[0:n, 0:n] / n
    return 0.4 * (np.sin(x * 2 * math.pi * 24) * 0.5 + 0.5)

def sand_pattern(n, seed):
    y, x = np.mgrid[0:n, 0:n] / n
    warp = fbm(n, 2.4, seed + 21) * 0.08
    rip = np.sin((x * 0.8 + y * 0.6 + warp) * 2 * math.pi * 9) * 0.5 + 0.5
    return 0.5 * rip

def build_mats():
    M = {}
    M["alu"] = make_pbr("alu", (0.55, 0.60, 0.65), 0.34, 1.0, uvscale=1.0, grime=0.22, scratch=0.9, brushed=0.7, bump=0.5, seed=11)
    M["cyan"] = make_pbr("cyan", (0.015, 0.50, 0.58), 0.34, 0.0, grime=0.3, scratch=0.9, bump=0.5, seed=12, grime_col=(0.03, 0.04, 0.035))
    M["cyan_dk"] = make_pbr("cyan_dk", (0.02, 0.28, 0.35), 0.42, 0.0, grime=0.5, scratch=0.7, bump=0.4, seed=13)
    M["slate"] = make_pbr("slate", (0.17, 0.21, 0.25), 0.45, 0.0, grime=0.4, scratch=0.9, bump=0.5, seed=14)
    M["slate_lt"] = make_pbr("slate_lt", (0.30, 0.35, 0.40), 0.40, 0.0, grime=0.5, scratch=0.9, bump=0.5, seed=15)
    M["foam"] = make_pbr("foam", (0.50, 0.64, 0.68), 0.82, 0.0, grime=0.3, scratch=0.5, bump=1.6, seed=16, streak=0.7, rough_var=0.1, grime_col=(0.10, 0.12, 0.08))
    M["rubber"] = make_pbr("rubber", (0.025, 0.027, 0.03), 0.78, 0.0, grime=0.5, scratch=0.3, bump=0.8, seed=17, pattern=hexpattern)
    M["steel"] = make_pbr("steel", (0.55, 0.57, 0.60), 0.33, 1.0, grime=0.55, scratch=1.0, brushed=0.5, bump=0.6, seed=18, grime_col=(0.09, 0.05, 0.03))
    M["steel_dk"] = make_pbr("steel_dk", (0.30, 0.32, 0.35), 0.42, 1.0, grime=0.5, scratch=0.7, brushed=0.3, bump=0.6, seed=19)
    M["blade"] = make_pbr("blade", (0.78, 0.80, 0.83), 0.18, 1.0, grime=0.15, scratch=1.0, brushed=0.9, bump=0.4, seed=20)
    M["chrome"] = make_pbr("chrome", (0.86, 0.87, 0.88), 0.09, 1.0, grime=0.10, scratch=0.6, bump=0.2, seed=21)
    M["prop"] = make_pbr("prop", (0.10, 0.13, 0.15), 0.35, 0.0, grime=0.5, scratch=0.5, bump=0.4, seed=22)
    M["glass"] = make_pbr("glass", (0.02, 0.035, 0.05), 0.04, 0.0, flat=True)
    M["lens_emit"] = make_pbr("lens_emit", (1, 0.97, 0.9), 0.1, 0.0, flat=True, emission=(1.0, 0.96, 0.88), emit_strength=18)
    M["status_led"] = make_pbr("status_led", (0.1, 1, 0.5), 0.2, 0.0, flat=True, emission=(0.1, 1.0, 0.45), emit_strength=6)
    M["decal"] = make_pbr("decal", (0.88, 0.9, 0.9), 0.5, 0.0, flat=True)
    M["hose"] = make_pbr("hose", (0.02, 0.022, 0.026), 0.55, 0.0, grime=0.4, scratch=0.2, bump=0.8, seed=23, pattern=helix_pattern)
    M["hose_cy"] = make_pbr("hose_cy", (0.0, 0.35, 0.42), 0.5, 0.0, grime=0.4, scratch=0.2, bump=0.8, seed=24, pattern=helix_pattern)
    M["brass"] = make_pbr("brass", (0.62, 0.45, 0.2), 0.3, 1.0, grime=0.5, scratch=0.5, bump=0.4, seed=25)
    # cable
    M["yarn"] = make_pbr("yarn", (0.085, 0.088, 0.09), 0.92, 0.0, uvscale=1.0, grime=0.55, scratch=0.0, bump=3.0, seed=31, pattern=yarn_pattern, streak=0.5, grime_col=(0.10, 0.11, 0.07))
    M["armour"] = make_pbr("armour", (0.58, 0.60, 0.62), 0.32, 1.0, grime=0.3, scratch=0.4, bump=0.8, seed=32, brushed=0.6)
    M["armour_cut"] = make_pbr("armour_cut", (0.88, 0.89, 0.9), 0.14, 1.0, grime=0.0, scratch=1.0, bump=0.5, seed=33, brushed=1.0)
    M["sheath"] = make_pbr("sheath", (0.015, 0.016, 0.018), 0.6, 0.0, grime=0.3, scratch=0.2, bump=0.5, seed=34)
    M["bedding"] = make_pbr("bedding", (0.10, 0.10, 0.09), 0.9, 0.0, grime=0.3, scratch=0.0, bump=2.0, seed=35)
    M["copper"] = make_pbr("copper", (0.95, 0.52, 0.34), 0.22, 1.0, grime=0.1, scratch=1.0, bump=1.0, seed=36, brushed=1.0)
    M["xlpe_a"] = make_pbr("xlpe_a", (0.03, 0.14, 0.75), 0.45, 0.0, grime=0.0, scratch=0.0, bump=0.3, seed=37)
    M["xlpe_b"] = make_pbr("xlpe_b", (0.30, 0.15, 0.06), 0.45, 0.0, grime=0.0, scratch=0.0, bump=0.3, seed=38)
    M["xlpe_c"] = make_pbr("xlpe_c", (0.50, 0.52, 0.52), 0.45, 0.0, grime=0.0, scratch=0.0, bump=0.3, seed=39)
    # environment
    M["sand"] = make_pbr("sand", (0.50, 0.46, 0.36), 0.93, 0.0, uvscale=0.25, grime=0.7, scratch=0.0, bump=2.0, seed=41, pattern=sand_pattern, streak=0.2, grime_col=(0.17, 0.16, 0.12))
    M["rock"] = make_pbr("rock", (0.20, 0.21, 0.20), 0.88, 0.0, uvscale=0.6, grime=0.9, scratch=0.0, bump=4.0, seed=42, grime_col=(0.04, 0.10, 0.05))
    M["algae"] = make_pbr("algae", (0.12, 0.30, 0.10), 0.7, 0.0, uvscale=1.0, grime=0.4, scratch=0.0, bump=1.5, seed=43)
    M["sponge"] = make_pbr("sponge", (0.55, 0.30, 0.52), 0.65, 0.0, uvscale=1.0, grime=0.3, scratch=0.0, bump=2.0, seed=44)
    M["shell"] = make_pbr("shell", (0.78, 0.76, 0.70), 0.6, 0.0, uvscale=1.0, grime=0.3, scratch=0.0, bump=1.0, seed=45)
    M["snow"] = make_pbr("snow", (0.85, 0.9, 0.9), 0.5, 0.0, flat=True, emission=(0.6, 0.75, 0.75), emit_strength=0.5)
    return M
