// The one place where the launch menu loads every module that registers a fidelity item, so the menu's 擬真設定
// tab (fidelity_panel.js) lists the same items as the in-game drawer. A feature that registers a new item adds
// its module here with a side-effect import; nothing else in the menu needs to change. The core items
// (assist, profile, video delay, view, gimbal, third person, HUD) are registered by fidelity.js itself.
import '../procedure/fidelity_item.js';
import '../hud/sensor_view.js';
import '../tether_reel.js';
import '../fx/silt.js';
import '../vision/overlay.js';
import '../fx/beautify.js';
import '../onboard/camera_look.js';
import '../audio/fidelity.js';
import '../story/feel_settings.js';
import '../audio/music_fidelity.js';
import '../input/haptics_fidelity.js';
import '../start_presentation.js';
import '../input/keyboard_layout.js';
import '../prefs/camera_items.js';
import '../career/fidelity_item.js';
import '../brand/chapter_card.js';
