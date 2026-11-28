"""Exercise the real decoder, gain graph, sliders and fidelity across scene changes without rendering a dive."""
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout

with sync_playwright() as playwright:
    browser = launch(playwright, headless=True)
    page = browser.new_page()
    # Use a small same-origin page so the viewer render loop does not overwrite the test's telemetry.
    page.goto(http_base() + '/audio/voice/index.json')
    page.set_content('<main></main><button>Unlock audio</button>')
    page.evaluate("""async () => {
      const {installAudio, installAudioSettings} = await import('/audio/engine.js');
      const {getFidelity} = await import('/fidelity.js');
      window.prefs = getFidelity();
      prefs.setPreset('real');
      window.world = {scenario: {biome: 'harbor'}};
      window.audio = installAudio({getWorld: () => world});
      installAudioSettings(audio, document.querySelector('main'));
      window.frame = depth => audio.update({pos: [0, 0, depth], t: 1});
      window.beds = [];
      const start = AudioBufferSourceNode.prototype.start;
      AudioBufferSourceNode.prototype.start = function (...args) {
        if (this.loop && this.buffer.duration > 3) {
          const bed = {duration: Math.round(this.buffer.duration), ended: false};
          beds.push(bed);
          this.addEventListener('ended', () => bed.ended = true);
        }
        return start.apply(this, args);
      };
    }""")
    page.get_by_role('button').click()
    page.evaluate('frame(5)')
    assert page.evaluate('beds.length') == 0
    page.evaluate('frame(0)')
    page.wait_for_function('beds[0]?.duration === 32', timeout=timeout(10000))
    page.evaluate("""() => {
      const slider = document.querySelector('input[aria-label="環境"]');
      slider.value = '0';
      slider.dispatchEvent(new Event('input'));
    }""")
    page.wait_for_function('audio.buses.environment.gain.value < 0.001')
    assert page.evaluate('audio.buses.music.gain.value') > 0.1
    page.evaluate("prefs.setPreset('assisted'); frame(5)")
    page.wait_for_function('beds.length === 2 && beds[0].ended')
    for biome, kind, duration in [('aquaculture', '', 6), ('', 'monopile', 12), ('', 'wreck', 30)]:
        page.evaluate("""([biome, kind]) => {
          window.world = {scenario: {biome}, obstacles: [{kind}]};
          frame(5);
        }""", [biome, kind])
        page.wait_for_function('duration => beds.at(-1).duration === duration', arg=duration)
    page.evaluate("prefs.setPreset('real'); frame(5)")
    page.wait_for_function('beds.every(bed => bed.ended)')
    browser.close()
    print('PASS: deck and four underwater loops decoded, crossfaded and stopped; environment slider isolated.')
