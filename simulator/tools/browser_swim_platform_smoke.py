"""Exercise optional launch geometry/lifecycle in Chromium using real meshes and the shared review host."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, timeout
from render_support_assets import start_server


def main():
    server = start_server(Path(__file__).resolve().parents[1] / 'viewer')
    try:
        with sync_playwright() as p:
            browser = launch(p)
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_address[1]}/review.html?asset=intro'
                      '&launchMode=swim-platform&t=0')
            page.wait_for_function('window.__done || window.__error', timeout=timeout(240000))
            assert not page.evaluate('window.__error')
            result = page.evaluate('''async () => {
              const THREE = await import('three');
              const {DeployIntro} = await import('./deploy_intro.js');
              const {SwimPlatformIntro, launchIntroClass} = await import('./swim_platform_intro.js');
              const {createVehicleModel} = await import('./vehicle_models.js');
              const assert = (ok, why) => { if (!ok) throw Error(why); };
              assert(launchIntroClass(null) === DeployIntro, 'default changed');
              assert(launchIntroClass('bad') === DeployIntro, 'invalid mode fallback');
              const scene = new THREE.Scene();
              const assets = await SwimPlatformIntro.loadAssets();
              const intro = new SwimPlatformIntro(scene, {assets, spool:[0,0,0], start:[2,1,3]});
              const rov = (await createVehicleModel('x1')).root;
              scene.add(rov);
              let done = 0;
              intro.play(rov, null, () => done++);
              const deck = rov.position.clone();
              intro.hold();
              intro.update(1);
              intro.skip();
              assert(intro.t === 0 && intro.playing, 'hold/skip');
              intro.release();
              intro.update(2.3);
              assert(rov.position.y > deck.y + .35, 'two-hand lift');
              assert(!intro.rig.group.visible && intro.launchCrew.root.visible && !!intro.launchCrew.b.Torso, 'manual rig');
              for (const at of [0, 2.3, 5.2]) {
                intro.t = at;
                intro.update(0);
                for (const [side, sign] of [['L', 1], ['R', -1]]) {
                  const target = intro._local(new THREE.Vector3(sign * intro.half.x * .8, intro.half.y * .7, 0));
                  const gap = intro.launchCrew.hand(side).distanceTo(target);
                  assert(gap < .1, `hand contact ${side} at ${at}: ${gap}`);
                }
              }
              intro.t = 2.3;
              intro.update(4.1);
              assert(Math.abs(rov.position.y) < .25, 'water entry');
              assert(intro.marker.mesh.visible, 'red end marker');
              const pts = intro.cable.curve.points;
              assert(pts.filter(p => p.y > .005 && p.y < .05).length > 10, 'surface cable');
              const aft = pts.slice(6, 16).map(p => intro.boat.worldToLocal(p.clone()).z);
              assert(Math.min(...aft) < intro.boat.userData.sternZ - 1, 'coil must bow outboard');
              const g = intro.cable.geometry;
              const vertex = n => new THREE.Vector3().fromBufferAttribute(g.attributes.position, n);
              const [a,b,c] = Array.from(g.index.array.slice(0,3));
              const face = vertex(b).sub(vertex(a)).cross(vertex(c).sub(vertex(a)));
              const normal = new THREE.Vector3().fromBufferAttribute(g.attributes.normal, a);
              assert(face.dot(normal) > 0, 'cable outside winding/lighting');
              intro.skip();
              assert(done === 1 && !intro.playing, 'completion');
              assert(rov.position.distanceTo(new THREE.Vector3(-1,-3,2)) < .001, 'handoff');
              assert(!intro.cable.mesh.visible && !intro.marker.mesh.visible, 'cinematic cable cleanup');
              intro.skip();
              assert(done === 1, 'callback called twice');
              intro.dispose();
              assert(scene.children.length === 1, 'scene cleanup');
              return 'Default, hold/release, hand lift, water entry, floating cable, skip/handoff, disposal passed';
            }''')
            print(result)
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
